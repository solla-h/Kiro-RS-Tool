#!/usr/bin/env python3
import argparse
import base64
import json
import select
import socket
import socketserver
import ssl
import threading
import time


def parse_proxy(proxy):
    if not proxy:
        return None
    proxy = proxy.removeprefix("http://").removeprefix("https://")
    if "/" in proxy:
        proxy = proxy.split("/", 1)[0]
    host, port = proxy, 80
    if ":" in proxy:
        host, port_s = proxy.rsplit(":", 1)
        port = int(port_s)
    return host, port


def connect_via_parent(parent_proxy, host, port, timeout=20):
    if parent_proxy is None:
        return socket.create_connection((host, port), timeout=timeout)

    proxy_host, proxy_port = parent_proxy
    sock = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    sock.sendall(
        (
            f"CONNECT {host}:{port} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Proxy-Connection: keep-alive\r\n"
            "\r\n"
        ).encode("ascii")
    )

    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            raise OSError("parent proxy closed during CONNECT")
        response += chunk
        if len(response) > 65536:
            raise OSError("parent proxy CONNECT response too large")

    status = response.split(b"\r\n", 1)[0]
    if b" 200 " not in status:
        raise OSError(f"parent proxy CONNECT failed: {status.decode(errors='replace')}")
    return sock


def redact_text(text):
    lines = []
    for line in text.splitlines():
        low = line.lower()
        if low.startswith("authorization:") or low.startswith("x-amz-security-token:"):
            key = line.split(":", 1)[0]
            lines.append(f"{key}: <redacted>")
        else:
            lines.append(line)
    return "\n".join(lines)


def redact_http_bytes(data):
    split = data.find(b"\r\n\r\n")
    if split < 0:
        return redact_text(data.decode("utf-8", errors="replace")).encode("utf-8")

    header = data[:split].decode("utf-8", errors="replace")
    body = data[split + 4 :]
    redacted_header = redact_text(header).encode("utf-8")
    return redacted_header + b"\r\n\r\n" + body


def redact_headers_dict(headers):
    redacted = {}
    for key, value in headers.items():
        if key.lower() in {"authorization", "x-amz-security-token"}:
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


class HttpRequestAccumulator:
    def __init__(self, log_record, target):
        self.log_record = log_record
        self.target = target
        self.buffer = b""

    def feed(self, data):
        self.buffer += data
        while True:
            header_end = self.buffer.find(b"\r\n\r\n")
            if header_end < 0:
                return

            header_bytes = self.buffer[:header_end]
            header_text = header_bytes.decode("iso-8859-1", errors="replace")
            header_lines = header_text.split("\r\n")
            request_line = header_lines[0] if header_lines else ""
            headers = {}
            for line in header_lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip()] = value.strip()

            try:
                content_length = int(headers.get("content-length", "0") or "0")
            except ValueError:
                content_length = 0

            total_length = header_end + 4 + content_length
            if len(self.buffer) < total_length:
                return

            body = self.buffer[header_end + 4 : total_length]
            self.buffer = self.buffer[total_length:]
            self.log_record(
                {
                    "event": "http_request",
                    "target": self.target,
                    "request_line": request_line,
                    "headers": redact_headers_dict(headers),
                    "body_text": body.decode("utf-8", errors="replace"),
                    "body_bytes": len(body),
                }
            )


class MitmProxyHandler(socketserver.StreamRequestHandler):
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
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        parts = request_line.split()
        method = parts[0] if parts else ""
        target = parts[1] if len(parts) > 1 else ""
        self.log_record({"event": "connect", "method": method, "target": target, "headers": headers})

        if method.upper() != "CONNECT":
            self.wfile.write(b"HTTP/1.1 501 Not Implemented\r\nContent-Length: 0\r\n\r\n")
            return

        host, port = target, 443
        if ":" in target:
            host, port_s = target.rsplit(":", 1)
            port = int(port_s)

        if host not in self.server.mitm_hosts:
            return self.tunnel_raw(host, port, target)
        return self.tunnel_mitm(host, port, target)

    def tunnel_raw(self, host, port, target):
        try:
            upstream = connect_via_parent(self.server.parent_proxy, host, port, timeout=20)
        except Exception as exc:
            self.log_record({"event": "connect_error", "target": target, "error": str(exc)})
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return

        self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self.connection.setblocking(False)
        upstream.setblocking(False)
        sockets = [self.connection, upstream]
        counts = {"client_to_upstream": 0, "upstream_to_client": 0}
        try:
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 60)
                if exceptional or not readable:
                    break
                for sock in readable:
                    data = sock.recv(65536)
                    if not data:
                        return
                    if sock is self.connection:
                        counts["client_to_upstream"] += len(data)
                        upstream.sendall(data)
                    else:
                        counts["upstream_to_client"] += len(data)
                        self.connection.sendall(data)
        finally:
            self.log_record({"event": "raw_tunnel_closed", "target": target, **counts})
            upstream.close()

    def relay_with_log(self, src, dst, target, direction):
        total = 0
        request_accumulator = (
            HttpRequestAccumulator(self.log_record, target)
            if direction == "client_to_upstream"
            else None
        )
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                total += len(data)
                if request_accumulator is not None:
                    request_accumulator.feed(data)
                text = data.decode("utf-8", errors="replace")
                if direction == "client_to_upstream":
                    text = redact_text(text)
                    logged_data = redact_http_bytes(data)
                else:
                    logged_data = data
                record = {
                    "event": "plaintext",
                    "target": target,
                    "direction": direction,
                    "bytes": len(data),
                    "text": text,
                }
                if self.server.log_base64:
                    record["base64"] = base64.b64encode(logged_data).decode("ascii")
                self.log_record(
                    record
                )
                dst.sendall(data)
        except Exception as exc:
            self.log_record(
                {
                    "event": "relay_error",
                    "target": target,
                    "direction": direction,
                    "error": str(exc),
                    "bytes": total,
                }
            )
        finally:
            try:
                dst.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                dst.close()
            except Exception:
                pass

    def tunnel_mitm(self, host, port, target):
        self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        try:
            client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            client_context.load_cert_chain(self.server.cert_path, self.server.key_path)
            client_context.set_alpn_protocols(["http/1.1"])
            client_tls = client_context.wrap_socket(self.connection, server_side=True)
        except Exception as exc:
            self.log_record({"event": "client_tls_error", "target": target, "error": str(exc)})
            return

        try:
            upstream_raw = connect_via_parent(self.server.parent_proxy, host, port, timeout=20)
            upstream_context = ssl.create_default_context()
            upstream_context.set_alpn_protocols(["http/1.1"])
            upstream_tls = upstream_context.wrap_socket(upstream_raw, server_hostname=host)
        except Exception as exc:
            self.log_record({"event": "upstream_tls_error", "target": target, "error": str(exc)})
            try:
                client_tls.close()
            except Exception:
                pass
            return

        self.log_record(
            {
                "event": "mitm_established",
                "target": target,
                "client_alpn": client_tls.selected_alpn_protocol(),
                "upstream_alpn": upstream_tls.selected_alpn_protocol(),
            }
        )

        t1 = threading.Thread(
            target=self.relay_with_log,
            args=(client_tls, upstream_tls, target, "client_to_upstream"),
            daemon=True,
        )
        t2 = threading.Thread(
            target=self.relay_with_log,
            args=(upstream_tls, client_tls, target, "upstream_to_client"),
            daemon=True,
        )
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.log_record({"event": "mitm_closed", "target": target})


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=40081)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--mitm-host", action="append", required=True)
    parser.add_argument("--cert-path", required=True)
    parser.add_argument("--key-path", required=True)
    parser.add_argument("--upstream-proxy")
    parser.add_argument(
        "--log-base64",
        action="store_true",
        help="include base64 plaintext chunks in logs; client request headers are redacted first",
    )
    args = parser.parse_args()

    with ThreadingTCPServer(("127.0.0.1", args.port), MitmProxyHandler) as server:
        server.log_path = args.log_path
        server.mitm_hosts = {
            host.strip()
            for item in args.mitm_host
            for host in item.split(",")
            if host.strip()
        }
        server.cert_path = args.cert_path
        server.key_path = args.key_path
        server.parent_proxy = parse_proxy(args.upstream_proxy)
        server.log_base64 = args.log_base64
        server.serve_forever()


if __name__ == "__main__":
    main()
