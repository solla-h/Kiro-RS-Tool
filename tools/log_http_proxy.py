#!/usr/bin/env python3
import argparse
import json
import select
import socket
import socketserver
import time


class ProxyHandler(socketserver.StreamRequestHandler):
    timeout = 30

    def log_record(self, record):
        record["ts"] = time.time()
        with open(self.server.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def handle(self):
        request_line = self.rfile.readline(65536).decode("iso-8859-1", errors="replace").strip()
        if not request_line:
            return
        headers = {}
        while True:
            line = self.rfile.readline(65536).decode("iso-8859-1", errors="replace")
            if line in ("\r\n", "\n", ""):
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        parts = request_line.split()
        method = parts[0] if parts else ""
        target = parts[1] if len(parts) > 1 else ""
        self.log_record({"event": "request", "method": method, "target": target, "headers": headers})

        if method.upper() != "CONNECT":
            self.wfile.write(b"HTTP/1.1 501 Not Implemented\r\nContent-Length: 0\r\n\r\n")
            return

        host, port = target, 443
        if ":" in target:
            host, port_s = target.rsplit(":", 1)
            port = int(port_s)

        try:
            upstream = socket.create_connection((host, port), timeout=20)
        except Exception as exc:
            self.log_record({"event": "connect_error", "target": target, "error": str(exc)})
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return

        self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self.connection.setblocking(False)
        upstream.setblocking(False)
        sockets = [self.connection, upstream]
        byte_counts = {"client_to_upstream": 0, "upstream_to_client": 0}

        try:
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 60)
                if exceptional:
                    break
                if not readable:
                    break
                for sock in readable:
                    try:
                        data = sock.recv(65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        return
                    if sock is self.connection:
                        byte_counts["client_to_upstream"] += len(data)
                        upstream.sendall(data)
                    else:
                        byte_counts["upstream_to_client"] += len(data)
                        self.connection.sendall(data)
        finally:
            self.log_record({"event": "tunnel_closed", "target": target, **byte_counts})
            upstream.close()


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=40080)
    parser.add_argument("--log-path", required=True)
    args = parser.parse_args()

    with ThreadingTCPServer(("127.0.0.1", args.port), ProxyHandler) as server:
        server.log_path = args.log_path
        server.serve_forever()


if __name__ == "__main__":
    main()
