#!/usr/bin/env python3
"""
Tiny HTTP listener that captures incoming request headers (especially
Authorization) to a file, then returns a stub SSE response so the client
finishes its request and exits cleanly.

Usage:
    capture_listener.py --port 9999 --log /path/to/captured.txt

Then run the target CLI against it, e.g.:
    cli --base-url http://127.0.0.1:9999 "some prompt"

The CLI's TLS is bypassed (the URL is http://, not https://), so the
Authorization header arrives in plaintext. No CA cert install required.
"""
import argparse
import http.server
import json
import sys


class CaptureHandler(http.server.BaseHTTPRequestHandler):
    log_path: str = ""

    def _capture(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(n) if n else b""
        with open(self.log_path, "a") as f:
            f.write(f"=== {self.command} {self.path} ===\n")
            for k, v in self.headers.items():
                f.write(f"  {k}: {v}\n")
            # Deliberately do NOT log body content: prompts routinely contain
            # secrets, source, and full workspace context. Length is enough to
            # tell a real request from a probe.
            f.write(f"  body-bytes: {len(body)}\n\n")

    def do_POST(self):
        self._capture()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        # Generic OpenAI-Responses-style SSE stub. Replace with a format the
        # target CLI actually accepts if it complains about parsing.
        payload = json.dumps(
            {
                "id": "resp_stub",
                "object": "response",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "ok"}],
                    }
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )
        self.wfile.write(f"data: {payload}\n\ndata: [DONE]\n\n".encode())

    def do_GET(self):
        self._capture()
        # Many CLIs fetch a model catalog before the first prompt request.
        # A bare {"ok":true} makes them abort with "malformed response data",
        # which is harmless for capture but looks like a failure. Returning a
        # catalog-shaped body lets the run proceed to the real POST.
        if "models" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [], "models": []}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *args, **kwargs):
        # Silence the default stderr request log.
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=9999)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--log", required=True, help="Path to capture log file")
    args = p.parse_args()

    CaptureHandler.log_path = args.log
    open(args.log, "w").close()  # truncate
    httpd = http.server.HTTPServer((args.host, args.port), CaptureHandler)
    print(f"capture_listener: listening on {args.host}:{args.port}, logging to {args.log}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()