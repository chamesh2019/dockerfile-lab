# Day 7 — Multi-Stage Build: TypeScript Compiler Out, Production Node In

## Topic / Focus

**Phase 2 (Day 7):** a second multi-stage exercise, with a different shape from Day 6. Day 6 copied a single static binary into a toolchain-free stage. Here the runtime stage still needs **Node.js and real production dependencies**, so the split is not "binary vs nothing" — it is **build-time toolchain vs run-time dependency set**.

The app is a small TypeScript HTTP service. Building it requires the TypeScript compiler, `@types/*`, and the full dependency tree. Running it requires `express`, the compiled JavaScript, and nothing else. The whole exercise is about drawing that line precisely and proving it.

## Scenario & Constraints

You are packaging an internal greeting service for production. The build context in this folder is deliberately dirty: it contains a **stale `dist/`** build and a **leftover local `node_modules/`** with a dev-only tool.Neither may reach the final image.

1. **Two stages, named.** A **builder stage** (`AS builder` or similar) and a
   **final runtime stage**. The final stage must be declared `FROM` a runtime base
   image — not `FROM builder` — and must pull artifacts only via `COPY --from=`.
2. **The builder does the whole compile.** It installs the *full* dependency tree
   from the provided `package-lock.json` and runs the TypeScript build
   (`npm run build`). The compiled output is `dist/server.js`.
3. **Production dependencies are installed, not inherited.** The final stage must
   run its own install of **production dependencies only** from the lockfile
   (`npm ci --omit=dev` or equivalent). Copying the builder's `node_modules/`
   into the final stage is a flaw: it carries the compiler and `@types/*` with
   it. State in one sentence why you chose install-in-runtime over
   copy-from-builder.
4. **What must NOT exist in the final image:**
   - no `src/` TypeScript sources, no `tsconfig.json`
   - no `typescript`, no `@types/node`, no `@types/express`
   - no npm cache (`/root/.npm` or `/home/node/.npm`)
   - no stale `dist/` content from the build context, and no
     `node_modules/stale-dev-only`
5. **What must exist in the final image:** the compiled `dist/server.js`, the
   production `node_modules/` (including `express`), and `package.json`.
6. **Dependency-first layering.** In each stage, copy `package.json` and
   `package-lock.json` and install **before** copying `src/`. A source-only edit
   must not invalidate the dependency-install layer. A lockfile, not a floating
   install, is required: `npm ci`, never `npm install` with an unconstrained range.
7. **Build context hygiene.** A `.dockerignore` is part of your deliverable (do
   not rely on `COPY` file lists alone). It must keep `node_modules/`, `dist/`,
   and npm debug logs out of the context. No `COPY . .` in the final stage.
8. **Pinned runtime base.** Use an exact-patch **Node.js LTS slim** tag
   (e.g. a `24.x.y-bookworm-slim` tag). No `latest`, no floating major, no full
   (non-slim) image. Justify the tag choice in one sentence.
9. **Non-root, numeric identity.** The container must run as **UID/GID
   `10001`**. Use the base image's existing `node` user as a starting point or
   create a dedicated user, but the effective user must be numeric and not root.
   The app directory must be readable by that user.
10. **Exec-form entrypoint, no npm wrapper.** `ENTRYPOINT` must be exec form
    invoking `node` directly on the compiled entry point
    (e.g. `["node", "dist/server.js"]`). Do **not** use `npm start`, `npm run`,
    `sh -c`, or a shell-form `ENTRYPOINT`/`CMD` — those fork a child process and
    swallow `SIGTERM`, so `docker stop` degrades to a timeout kill.
11. **Correct signal handling.** Node must be PID 1 and receive `SIGTERM`
    directly. `docker stop` must return promptly with exit status 0. Set
    `STOPSIGNAL SIGTERM` explicitly even though it is the default.
12. **Healthcheck with no package install.** The slim Node image ships no
    `curl` and no `wget`. The `HEALTHCHECK` must probe the app's `/healthz`
    endpoint using something that is actually present in the final image (Node's
    built-in `fetch` via `node -e` is the intended route). State how your
    healthcheck works without adding a package.
13. **Runtime configuration without rebuild.** `PORT`, `GREETING_NAME`, and
    `APP_VERSION` must be read from the environment at startup and change
    behaviour with no image rebuild.
14. **OCI metadata labels.** Add `org.opencontainers.image.title`, `...version`,
    `...source`, `...licenses`, and `...revision` with literal values.
15. **Image size — soft target ≤ 180 MB.** A `node:*` slim runtime plus `express`
    lands comfortably under this. This is best-effort; do not chase
    distroless/scratch gymnastics. What *is* graded is that the compiler,
    `@types/*`, sources, and stale artifacts are absent.
16. **No production Dockerfile is provided.** Author the `Dockerfile` (and
    `.dockerignore`) yourself from these requirements alone.

## Dummy Application Mock (already written to this folder)

`src/server.ts` — `express` HTTP server:

- `GET /` → `hello, <GREETING_NAME> (v<APP_VERSION>)`
- `GET /healthz` → `ok`
- listens on `0.0.0.0:$PORT` (default `8080`)
- handles `SIGTERM`/`SIGINT` with a graceful `server.close()`

Defaults: `GREETING_NAME=world`, `APP_VERSION=1.0.0`.

`package.json` scripts:

```
"build": "tsc -p tsconfig.json",
"start": "node dist/server.js"
```

`tsconfig.json` compiles `src/` → `dist/` (CommonJS output, `strict: true`).

Local sanity check (outside Docker), if Node 22+ is installed:

```bash
npm ci
npm run build
node dist/server.js & curl -s localhost:8080/healthz
```

Also present as traps:

- `dist/server.js` — **stale** earlier build; it prints `hello, STALE BUILD (v0.0.0)`.
- `node_modules/stale-dev-only/` — leftover local dev tool.

## Verification Criteria

Build with `docker build -t greeter:day7 "Day 7"`, then:

```bash
# 1. Service reachable and correct build (not the stale one)
docker run --rm -d --name g7 -p 8080:8080 greeter:day7
curl -s localhost:8080/                 # hello, world (v1.0.0)
docker rm -f g7

# 2. Runtime env config, no rebuild
docker run --rm -d --name g7 -p 8080:8080 \
  -e GREETING_NAME=team -e APP_VERSION=2.0.0 greeter:day7
curl -s localhost:8080/                 # hello, team (v2.0.0)
docker rm -f g7

# 3. Healthcheck present and healthy, no curl/wget anywhere
docker inspect -f '{{json .Config.Healthcheck}}' greeter:day7
docker run --rm -d --name g7 greeter:day7; sleep 5
docker inspect -f '{{.State.Health.Status}}' g7     # healthy
docker rm -f g7
docker run --rm --entrypoint sh greeter:day7 -c 'command -v curl; command -v wget'

# 4. No compiler, types, sources, npm cache, or stale artifacts
docker run --rm --entrypoint sh greeter:day7 -c \
  'ls node_modules | grep -E "^(typescript|@types)$" || echo "no devDeps"'
docker run --rm --entrypoint find greeter:day7 /app -name '*.ts' -o -name 'tsconfig.json'
docker run --rm --entrypoint find greeter:day7 /app -name 'stale-dev-only'
docker run --rm --entrypoint ls greeter:day7 -la /root/.npm /home/node/.npm 2>&1
docker run --rm --entrypoint cat greeter:day7 /app/dist/server.js | grep -c 'STALE BUILD'  # 0

# 5. Non-root numeric identity
docker run --rm --entrypoint id greeter:day7
docker inspect -f '{{.Config.User}}' greeter:day7     # 10001 or 10001:10001

# 6. Exec-form entrypoint, nobody forking for the app
docker inspect -f '{{json .Config.Entrypoint}}' greeter:day7
docker inspect -f '{{json .Config.Cmd}}' greeter:day7

# 7. Signal handling: SIGTERM shuts down promptly, exit status 0
docker run --rm --name g7 greeter:day7 &
docker stop --time 5 g7; echo "stop exit=$?"          # 0, prompt
docker wait g7 2>/dev/null; echo "container exit=$?"

# 8. Labels
docker inspect -f '{{json .Config.Labels}}' greeter:day7 | python3 -m json.tool

# 9. Size and lint
docker images greeter:day7 --format '{{.Size}}'       # soft target <= 180 MB
docker run --rm -i hadolint/hadolint < "Day 7/Dockerfile"

# 10. Context hygiene
cat "Day 7/.dockerignore"
```

Submission must include the one-sentence justifications requested in items 3, 8, and 12.
