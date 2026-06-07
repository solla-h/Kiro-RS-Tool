#!/usr/bin/env python3
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def redacted_headers(headers):
    redacted = {}
    for key, value in headers.items():
        if key.lower() in {"authorization", "x-amz-security-token"}:
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


class CaptureHandler(BaseHTTPRequestHandler):
    server_version = "KiroCapture/1.0"

    def do_POST(self):
        length = int(self.headers.get("content-length", "0") or "0")
        body = self.rfile.read(length)
        record = {
            "method": "POST",
            "path": self.path,
            "headers": redacted_headers(self.headers),
            "body_text": body.decode("utf-8", errors="replace"),
        }
        with open(self.server.capture_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.server.request_count += 1
        target = self.headers.get("x-amz-target", "")
        if target.endswith("ListAvailableProfiles"):
            response = {
                "profiles": [
                    {
                        "arn": "arn:aws:codewhisperer:us-east-1:000000000000:profile/capture",
                        "profileName": "capture",
                    }
                ]
            }
            status = 200
        elif target.endswith("SendTelemetryEvent"):
            response = {}
            status = 200
        else:
            response = {"__type": "CaptureComplete", "message": "captured"}
            status = 400
        self.send_response(status)
        self.send_header("content-type", "application/x-amz-json-1.0")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
        if self.server.request_count >= self.server.max_requests:
            self.server.shutdown_requested.set()

    def do_GET(self):
        self.server.request_count += 1
        record = {
            "method": "GET",
            "path": self.path,
            "headers": redacted_headers(self.headers),
            "body_text": "",
        }
        with open(self.server.capture_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.send_response(404)
        self.end_headers()
        if self.server.request_count >= self.server.max_requests:
            self.server.shutdown_requested.set()

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=39999)
    parser.add_argument("--capture-path", required=True)
    parser.add_argument("--max-requests", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), CaptureHandler)
    server.capture_path = args.capture_path
    server.max_requests = args.max_requests
    server.request_count = 0
    server.shutdown_requested = threading.Event()

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.shutdown_requested.wait(timeout=args.timeout)
    server.shutdown()
    thread.join(timeout=5)


if __name__ == "__main__":
    main()
