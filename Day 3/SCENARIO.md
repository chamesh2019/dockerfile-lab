# Day 3 — Single-Stage Build Foundations (Python + dependency)

## Topic / Focus
**Phase 1, Day 3:** Base image selection, dependency-first `COPY` layering, `WORKDIR`, and `ENTRYPOINT` vs `CMD` — now with a real external dependency.

## Scenario & Constraints
You are containerizing a tiny internal status-check service written in Python using Flask. The service must:

1. **Run from a slim base image** — do not use a full `python:latest` image. Pick an appropriate `-slim` variant and justify it.
2. **Set a `WORKDIR`** — do not rely on the container root `/` as the working directory.
3. **Minimize `COPY` layers** — copy only the files required to run the app. Avoid `COPY . .` (copying the entire build context). Follow **dependency-first layering**: copy `requirements.txt` first, install dependencies, then copy `app.py`. This keeps the `pip install` layer cached when only application source changes.
4. **Demonstrate `ENTRYPOINT` vs `CMD`** — use `ENTRYPOINT` for the executable (`python app.py`) and `CMD` for default arguments, so the container can be overridden with `docker run <alternate-arg>` at runtime without rewriting the entrypoint.
5. **Provide a default message via `ENV`** — allow the response message to be overridden with `STATUS_MESSAGE` at runtime, falling back to `"OK"`.
6. **Image size — baseline real-world target (soft).** Final image should follow standard real-world deployment sizing (target **≤ 200 MB**). Use a `-slim` base, `--no-cache-dir` for pip, and clean up build artifacts. This is a **best-effort sizing guideline, not an absolute minimum** — do not resort to distroless/scratch gymnastics; prioritize correct, maintainable, production-baseline practices.
7. **No production Dockerfile provided** — you must author the Dockerfile from these requirements alone.

## Dummy Application Mock

`app.py`:
```python
import os
import sys
from flask import Flask

app = Flask(__name__)

message = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STATUS_MESSAGE", "OK")

@app.get("/")
def index():
    return message, 200, {"Content-Type": "text/plain"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

`requirements.txt`:
```
flask==3.0.0
```

## Verification Criteria
Run these commands to validate your build:

1. **Build:** `docker build -t day3-status .`
2. **Size check:** `docker images day3-status` — confirm it follows baseline sizing (target ≤ 200 MB) with obvious optimizations; this is best-effort, not an absolute minimum.
3. **Default run:** `docker run --rm -p 8080:8080 day3-status` then `curl http://localhost:8080/` → expect `OK`.
4. **Env override run:** `docker run --rm -p 8080:8080 -e STATUS_MESSAGE=HELLO day3-status` then `curl http://localhost:8080/` → expect `HELLO`.
5. **Arg override run:** `docker run --rm -p 8080:8080 day3-status "HELLO WORLD"` then `curl http://localhost:8080/` → expect `HELLO WORLD` (proves `ENTRYPOINT` + `CMD` wiring).
6. **WORKDIR check:** `docker run --rm day3-status pwd` → should print your `WORKDIR`, not `/`.
7. **Lint:** `hadolint Dockerfile` — no DL warnings about `latest` tags or `apt-get` misuse.

Submit your `Dockerfile` (only) for evaluation via `/evaluate`.
