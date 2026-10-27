import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        message = sys.argv[1] if len(sys.argv) > 1 else "OK"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(message.encode())

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
