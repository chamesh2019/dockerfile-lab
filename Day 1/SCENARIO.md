# Day 1 — Single-Stage Build Foundations

## Topic / Focus
**Phase 1, Day 1:** Base image selection, `WORKDIR`, `COPY` minimization, and `ENTRYPOINT` vs `CMD`.

## Scenario & Constraints
You are containerizing a tiny internal status-check service. The service must:

1. **Run from a slim base image** — do not use a full `python:latest` or `node:latest` image. Pick an appropriate `-slim` or Alpine variant and justify it.
2. **Set a `WORKDIR`** — do not rely on the container root `/` as the working directory.
3. **Minimize `COPY` layers** — copy only the files required to run the app. Avoid `COPY . .` (copying the entire build context).
4. **Demonstrate `ENTRYPOINT` vs `CMD`** — use `ENTRYPOINT` for the executable and `CMD` for default arguments, so the container can be overridden with `docker run  <alternate-arg>` at runtime without rewriting the entrypoint.
5. **Image size constraint** — final image must be under **100 MB**.
6. **No production Dockerfile provided** — you must author the Dockerfile from these requirements alone.

## Dummy Application Mock

`app.py`:
```python
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
```

`requirements.txt`:
```
# No external dependencies; standard library only
```

## Verification Criteria
Run these commands to validate your build:

1. **Build:** `docker build -t day1-status .`
2. **Size check:** `docker images day1-status` — confirm under 100 MB.
3. **Default run:** `docker run --rm -p 8080:8080 day1-status` then `curl http://localhost:8080/` → expect `OK`.
4. **Override run:** `docker run --rm -p 8080:8080 day1-status "HELLO WORLD"` then `curl http://localhost:8080/` → expect `HELLO WORLD` (proves `ENTRYPOINT` + `CMD` wiring).
5. **WORKDIR check:** `docker run --rm day1-status pwd` → should print your `WORKDIR`, not `/`.
6. **Lint:** `hadolint Dockerfile` — no DL warnings about `latest` tags or `apt-get` misuse.

Submit your `Dockerfile` (only) for evaluation via `/evaluate`.