# Day 4 — Build Context Hygiene, Immutable Bases, and Exec-Form Process Supervision

## Topic / Focus
**Phase 1, Day 4:** Pinned base images, build-context isolation (`.dockerignore`), precise `COPY` layering, non-root execution, and `ENTRYPOINT`/`CMD` in **exec (JSON) form** so signals reach the application.

This folder intentionally contains **junk you must not ship**: a decoy `.env` with fake credentials, an 8 MiB `artifacts/build-cache.bin`, a stale `node_modules/` tree, `debug.log`, and a `__pycache__` file. Taming the build context is part of the challenge.

## Scenario & Constraints
You are containerizing a small internal static/config service written in pure Python (standard library only — **no third-party dependencies**). The service must:

1. **Pin the base image exactly.** Use a slim Debian-based Python image pinned to an exact patch version and distro (e.g. a `python:3.12.x-slim-bookworm` style tag). Do **not** use `latest`, a floating major/minor, or a digest-less moving tag. Justify your choice in one sentence when you submit.
2. **Ship a `.dockerignore`.** The build context is polluted. At minimum exclude the decoy secret file, `artifacts/`, `node_modules/`, `debug.log`, and `__pycache__`. Proof: the BuildKit **"transferring context"** figure must be **under 1 MB**.
3. **Copy only what runs.** No `COPY . .`. Copy exactly `app.py`, `static/`, and `config/settings.json` into the image. Put the static assets/config in an earlier layer than `app.py` so editing application code does not invalidate the asset layer.
4. **Set a `WORKDIR`** — do not run from `/`.
5. **Run as a non-root user.** Create a dedicated account with **explicit numeric UID/GID `10001`**, no login shell, no home directory, and switch with `USER 10001:10001` (numeric, not just a name). The process must not need root at runtime.
6. **Supervise the process correctly.** Use exec (JSON) `ENTRYPOINT` and `CMD`/`ENTRYPOINT` wiring so `python app.py` is **PID 1**. The app traps `SIGTERM` and prints `SHUTDOWN signal=15` then `EXITED cleanly`. On `docker stop`, those lines must appear and the container must exit with code `0` well under Docker's 10-second grace period — **not** be SIGKILLed (exit `137`). Shell-form commands (`CMD python app.py`) will fail this test.
7. **Make the port runtime-configurable.** `PORT` must override the default `8080` at `docker run` time without rebuilding.
8. **Add a valid `HEALTHCHECK`.** Exec (JSON) form, explicit `--interval`, `--timeout`, `--start-period`, and `--retries`, and it must actually probe the HTTP endpoint. The container must report `healthy`.
9. **Do not install system packages.** The app is stdlib-only; no `apt-get`/`apk` layer is needed. Adding one is a fail.
10. **Image size — soft target ≤ 200 MB.** Slim base is the main lever here. This is a best-effort sizing guideline, not an absolute minimum — do not resort to distroless/scratch gymnastics.
11. **No production Dockerfile provided** — you must author the Dockerfile (and `.dockerignore`) from these requirements alone.

## Dummy Application Mock (already written to this folder)

`app.py`:
```python
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
            self.send_response(404); self.send_header("Content-Type", "text/plain")
            self.end_headers(); self.wfile.write(b"not found"); return
        with open(target, encoding="utf-8") as fh:
            body = fh.read().replace("{{GREETING}}", config["greeting"]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}", file=sys.stderr, flush=True)

def handle_signal(signum, _frame):
    print(f"SHUTDOWN signal={signum}", flush=True)
    threading.Thread(target=server.shutdown, daemon=True).start()

server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

print(f"SERVING port={PORT} greeting={config['greeting']}", flush=True)
server.serve_forever()
print("EXITED cleanly", flush=True)
```

`config/settings.json`:
```json
{ "greeting": "Hello from Day 4", "port": 8080 }
```

`static/index.html` (contains the `{{GREETING}}` placeholder the app substitutes):
```html
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>Day 4 — Config Service</title></head>
  <body><h1>{{GREETING}}</h1></body>
</html>
```

Decoys present in the build context: `.env`, `debug.log`, `__pycache__`, `node_modules/left-pad/*`, `artifacts/build-cache.bin` (8 MiB).

## Verification Criteria
Run these commands from this folder to validate your build:

1. **Context size:** `docker build --no-cache --progress=plain -t day4-config . 2>&1 | grep -i "transferring context"` → must be **< 1 MB**.
2. **Build:** `docker build -t day4-config .` → succeeds.
3. **Nothing extra shipped:** `docker run --rm day4-config sh -c 'ls -A /app'` → shows only your app files/dirs; no `.env`, `debug.log`, `node_modules`, `__pycache__`, or `artifacts`. Also `docker run --rm day4-config grep -R "supersecret" /app` → no match.
4. **Default run:** `docker run --rm -p 8080:8080 day4-config` then `curl -s http://localhost:8080/` → contains `Hello from Day 4` (the app runs from `/app/config` and `/app/static`, so those paths must exist).
5. **PORT override:** `docker run --rm -e PORT=9090 -p 9090:9090 day4-config` then `curl -s http://localhost:9090/` → same greeting.
6. **Non-root:** `docker run --rm day4-config id -u` → prints `10001`; `docker run --rm day4-config id -un` → not `root`.
7. **Signal handling / exec form:** `docker run -d --name day4-config -p 8080:8080 day4-config && sleep 2 && docker stop day4-config && docker logs day4-config` → logs contain `SHUTDOWN signal=15` and `EXITED cleanly`, and `docker inspect -f '{{.State.ExitCode}}' day4-config` → `0`.
8. **Healthcheck:** with the container running, `docker inspect -f '{{.State.Health.Status}}' day4-config` → `healthy`.
9. **Cache layering:** change `app.py` (e.g. add a comment), rebuild, and confirm the `COPY` layer for `static/`/`config/` is reused (`CACHED`) while the `app.py` layer is rebuilt.
10. **Lint / inspect:** `hadolint Dockerfile` → no DL3006/DL3007 (unpinned/latest base), no DL3008 (unpinned apt), no DL3025 (shell-form CMD/ENTRYPOINT). `dive day4-config` → no wasted bytes from the decoy files.

Submit your `Dockerfile` **and** `.dockerignore` via `/evaluate`.