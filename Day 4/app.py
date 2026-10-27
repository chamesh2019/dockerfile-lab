import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config/settings.json")
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")

with open(CONFIG_PATH, encoding="utf-8") as fh:
    config = json.load(fh)

PORT = int(os.environ.get("PORT", config.get("port", 8080)))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        rel = "index.html" if self.path in ("", "/") else self.path.lstrip("/")
        target = os.path.join(STATIC_DIR, rel)
        if not os.path.isfile(target):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not found")
            return
        with open(target, encoding="utf-8") as fh:
            body = fh.read().replace("{{GREETING}}", config["greeting"]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}", file=sys.stderr, flush=True)


def handle_signal(signum, _frame):
    # Proves the process is PID 1 and receives SIGTERM directly.
    print(f"SHUTDOWN signal={signum}", flush=True)
    threading.Thread(target=server.shutdown, daemon=True).start()


server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

print(f"SERVING port={PORT} greeting={config['greeting']}", flush=True)
server.serve_forever()
print("EXITED cleanly", flush=True)
