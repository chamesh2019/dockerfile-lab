# Day 9 — Multi-Stage Build: Wheels in the Builder, Virtualenv in the Runtime

## Topic / Focus

**Phase 2 (Day 9):** the fourth multi-stage shape. Day 6 shipped a Go static binary, Day 7
split a Node build environment from a Node runtime, Day 8 shipped a Rust musl binary out of
a 1.39 GB toolchain. Today the artefact crossing the stage boundary is **not a binary** — it
is an entire **Python virtualenv**.

That changes the failure modes:

- A venv is **path-bound**. Its entry-point scripts bake the interpreter's absolute path into
  their shebang, so the directory must be created at the exact absolute path the runtime will
  use. Create it in one location and copy it to another and the image looks fine until the
  first `docker run`.
- The host folder ships **its own `.venv/` and `__pycache__/`** — 2.1 MB of decoy host
  artefacts that must never enter the build context, let alone the image.

**Deliberately out of scope today** (later phases): BuildKit cache mounts and `ARG` (Phase 3),
`tini`/init wrappers and explicit signal handling (Phase 5), distroless/scratch (Phase 6).
Gunicorn's own master/worker signal behaviour is what it is — you document it, you don't add
an init wrapper.

## Scenario & Constraints

You are packaging a small HTTP greeting service behind Gunicorn. Requirements are numbered
and each one is objectively checkable.

1. **Two stages, named `builder` and `runtime`.** The final stage must be declared `FROM` a
   Python *runtime* base — not `FROM builder` — and may receive files from the builder stage
   only. No other copy source is permitted for the venv.
2. **Identical pinned base in both stages.** Use `python:3.12.16-alpine3.24` for **both** the
   builder and the runtime: exact Python patch version plus the Alpine distro. No `latest`, no
   floating `python:3.12-alpine`, no `python:3-alpine`, and no Debian/glibc base in either
   stage — a venv built against musl must run against the same ABI.
3. **Virtualenv at exactly `/opt/venv`.** The builder creates it with the stdlib `venv` module
   and installs `requirements.txt` into it with pip's download cache disabled. The runtime
   stage receives that venv **as a copied artefact**: it must not create a venv, must not run
   `pip install`, and must not require network access at container start.
4. **Toolchain only in the builder.** If a dependency needs to compile from source, `build-base`,
   `gcc`, `musl-dev` and friends may exist **only** in the builder. The final image must contain
   no C/C++ compiler or `make` executable, and the runtime stage must not use `apk add` — it is
   the bare pinned Python/Alpine image plus the artefacts you copy in.
5. **Cache-friendly layer order.** `requirements.txt` must be copied in a layer that comes
   **before** the application source, so that editing `app.py` alone cannot re-run the dependency
   install. Prove it with a rebuild after touching one source file (see verification 5).
6. **Minimal runtime payload.** The final image carries `/opt/venv` plus exactly the application
   files it needs (`app.py`, `wsgi.py`, `gunicorn.conf.py`). The application directory must
   contain no host `.venv/`, no host `__pycache__/`, and no host `*.pyc` decoy — in other words,
   the 2.1 MB host virtualenv must not appear anywhere under `/app`, and the decoy site-packages
   package `_host_junk` must not exist anywhere in the image. Do not `COPY . .`. (Bytecode that
   pip legitimately generates *inside* `/opt/venv` is expected and not a violation.)
7. **Tame the build context.** Add a `.dockerignore` that excludes `.venv/`, `__pycache__/`,
   `*.pyc`, and `.git/`. The context this folder would otherwise upload is **2.1 MB** of decoys;
   the reported context size must stay in the low kilobytes.
8. **Non-root, numeric identity.** The container runs as **`10001:10001`**, with no home
   directory and no login shell. Do not run as root. Do not depend on an account that already
   exists in the base image.
9. **Gunicorn as PID 1, exec form.** `ENTRYPOINT` must be exec-form JSON, pointing at the
   **absolute path of the gunicorn executable inside `/opt/venv`**. No `sh -c`, no shell-form,
   no wrapper script. Because exec form does not expand variables, the shipped
   `gunicorn.conf.py` — not a hard-coded CLI flag — is what reads `PORT` and `WEB_CONCURRENCY`
   at runtime. Do not override its `bind` with a fixed `--bind` argument.
10. **Reachable on all interfaces.** The service must listen on **`0.0.0.0`**, and both `PORT`
    and `GREETING_NAME` and `WEB_CONCURRENCY` must be changeable at `docker run` time with no
    rebuild.
11. **`HEALTHCHECK` required.** It must probe the app's own `/healthz` endpoint with a tool
    that is actually present in the final image, set an interval, a **timeout shorter than the
    interval**, and a retry count. The container must report `healthy`.
12. **Image size — soft target ≤ 120 MB.** The pinned Python/Alpine base is already most of the
    budget; a venv with these dependencies adds roughly 20 MB. Size is best-effort: do not reach
    for `scratch`/distroless tricks today.
13. **Submission notes.** Include with your submission: (a) the pinned-tag rationale for the base
    you chose, (b) proof that the final image contains no compiler and no pip download cache,
    (c) one sentence stating the exit code `docker stop` produces for this image **and why it
    differs from Day 8's 137**.
14. **No production Dockerfile is provided.** Author it yourself from these requirements. The
    `Dockerfile` in this folder is intentionally empty.

## Dummy Application Mock (already written to this folder)

- `app.py` — Flask app, two routes: `GET /` → `hello, <GREETING_NAME>` (default `world`),
  `GET /healthz` → `ok`. Plain text, no templates, no database.
- `wsgi.py` — exposes the app as `wsgi:app` for Gunicorn.
- `gunicorn.conf.py` — reads `PORT` (default `8080`) and `WEB_CONCURRENCY` (default `2`) from
  the environment at startup. This is the only place the bind address is decided.
- `requirements.txt` — eight pinned dependencies (Flask, Gunicorn and their transitive pins).
- `.venv/`, `__pycache__/` — **decoys**. A fake host virtualenv (1.5 MB blob, fake interpreter
  script, `pyvenv.cfg`) and a 12 KB fake `.pyc`. None of it may ship.

Core of `app.py`:

```python
@app.get("/")
def index():
    name = os.environ.get("GREETING_NAME", "world")
    return f"hello, {name}\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.get("/healthz")
def healthz():
    return "ok\n", 200, {"Content-Type": "text/plain; charset=utf-8"}
```

Core of `gunicorn.conf.py`:

```python
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
```

Local sanity check (keeps the venv **outside** this folder so it does not pollute the context):

```bash
cd "Day 9"
python3 -m venv /tmp/day9-venv
/tmp/day9-venv/bin/pip install -r requirements.txt
PORT=18080 GREETING_NAME=team /tmp/day9-venv/bin/gunicorn --config gunicorn.conf.py wsgi:app
# in another shell:
curl -s localhost:18080/healthz   # ok
curl -s localhost:18080/          # hello, team
```

## Verification Criteria

Build with `docker build -t greeterd:day9 "Day 9"`, then:

```bash
# 1. Service reachable, runtime env honoured, no rebuild
docker run --rm -d --name g9 -p 18090:8080 greeterd:day9
curl -s localhost:18090/healthz          # ok
curl -s localhost:18090/                 # hello, world
docker rm -f g9

docker run --rm -d --name g9 -p 18091:9090 -e PORT=9090 -e GREETING_NAME=team greeterd:day9
curl -s localhost:18091/                 # hello, team
docker rm -f g9

# 2. Worker count is runtime-configurable
docker run --rm -d --name g9 -e WEB_CONCURRENCY=4 greeterd:day9
docker exec g9 ps | grep -c "[g]unicorn"   # master + 4 workers
docker rm -f g9

# 3. No compiler, no pip download cache in the final image
docker run --rm --entrypoint sh greeterd:day9 -c \
  'command -v gcc; command -v cc; command -v make; ls -d /root/.cache/pip 2>/dev/null; echo scan-done'

# 4. Venv is path-correct and usable in the runtime stage
docker run --rm --entrypoint sh greeterd:day9 -c 'head -1 /opt/venv/bin/gunicorn'
# expect the shebang to point at /opt/venv/bin/python
docker run --rm --entrypoint /opt/venv/bin/python greeterd:day9 -c 'import flask, gunicorn; print(flask.__version__)'

# 5. Cache layering: an app-only change must not re-run pip
docker build -t day9-cache "Day 9" >/dev/null
printf '\n# cache probe\n' >> "Day 9/app.py"     # content change, not just mtime
docker build -t day9-cache "Day 9" 2>&1 | grep -E "pip install|CACHED|COPY app" | head -20
git checkout -- "Day 9/app.py" 2>/dev/null || sed -i '/# cache probe/d' "Day 9/app.py"
# expect the requirements/pip layer to be CACHED and only the source copy to rebuild

# 6. Host artefacts stayed out of the image and the context
docker run --rm --entrypoint sh greeterd:day9 -c \
  'ls -la /app; find / -name "_host_junk" -o -name "blob.bin" 2>/dev/null; echo scan-done'
# expect: /app holds only app.py, wsgi.py, gunicorn.conf.py; no decoy package or blob anywhere
# note: /opt/venv/pyvenv.cfg is the venv's own metadata and is expected
docker build --no-cache -t greeterd:day9 "Day 9" 2>&1 | grep -i "transferring context"
# expect low kilobytes, not ~2.1 MB

# 7. Non-root numeric identity, no home, no login shell
docker inspect -f '{{.Config.User}}' greeterd:day9        # 10001:10001
docker run --rm --entrypoint id greeterd:day9
docker run --rm --entrypoint sh greeterd:day9 -c 'ls -ld /home/* 2>/dev/null || echo "no home dirs"'

# 8. Exec-form entrypoint, gunicorn as PID 1
docker inspect -f '{{json .Config.Entrypoint}}' greeterd:day9
docker inspect -f '{{json .Config.Cmd}}' greeterd:day9     # empty

# 9. Healthcheck present and green
docker inspect -f '{{json .Config.Healthcheck}}' greeterd:day9
docker run -d --name g9 greeterd:day9; sleep 8
docker inspect -f '{{.State.Health.Status}}' g9            # healthy
docker rm -f g9

# 10. Shutdown behaviour (for the one-sentence note in requirement 13)
docker run -d --name g9 greeterd:day9; sleep 3
docker stop --time 5 g9; docker inspect -f '{{.State.ExitCode}}' g9
docker rm -f g9

# 11. Size and lint
docker images greeterd:day9 --format '{{.Size}}'           # soft target <= 120 MB
docker run --rm -i hadolint/hadolint < "Day 9/Dockerfile"
```

Submission must include the pinned-tag rationale, the no-compiler/no-cache proof, the
`docker stop` sentence, and a screenshot-free paste of the context-size line and the cache-hit
line from verification 5 and 6.
