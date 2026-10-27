# Day 6 — Multi-Stage Build: Go Toolchain Out, Static Binary In

## Topic / Focus

**Phase 2 opener (Day 6):** multi-stage builds. Days 1–5 produced images where the
base image *was* the runtime. From here on, the runtime image is assembled by
**copying artifacts out of a builder stage**, and the toolchain that produced them
must never appear in the final image.

The app is a stdlib-only Go HTTP service. The Go toolchain is ~800 MB installed;
the resulting static binary is ~7 MB. The entire point of the exercise is that
gap.

## Scenario & Constraints

You are packaging an internal greeting service as a minimal, non-root,
production-shaped container image.

1. **Two stages, named.** Use a **builder stage** and a **final stage**, with the
   final stage declared `FROM` the builder's output context. Name the stages
   (e.g. `AS builder`) so the `COPY --from=` reference is legible.
2. **The Go toolchain must not survive.** The final stage must contain **no Go
   toolchain, no Go module cache, no `go.mod`/`go.sum`, and no source files**. Only
   the compiled binary and the files it needs at runtime may be present.
3. **Build a static binary.** The builder must produce a **statically linked**
   binary (no libc dependency): use `CGO_ENABLED=0` and, if you set
   `GOOS`/`GOARCH`, set them explicitly. Cross-compiling for `linux/amd64` is
   expected.
4. **Copy only the binary.** Use `COPY --from=builder` to copy the single
   executable into the final stage. No `COPY . .`, no copying the whole source
   tree, no copying `$GOPATH` or the module cache.
5. **Final base image.** Use a **pinned slim Debian** tag (e.g. a `bookworm-slim`
   tag with an exact patch version) or `gcr.io/distroless/static` (pinned). No
   `latest`, no floating tag. If you use a Debian-slim base, it needs a `ca-certificates`
   package for outbound TLS — and if you install it, you must clean up the apt
   lists in the same `RUN` layer.
6. **No package installation is required.** The app has no external Go module
   dependencies (`go.mod` has no `require` block). If your solution runs
   `go mod download`, it should be a no-op — but the network call is still
   unnecessary; prefer a build that works with the vendored-free stdlib.
7. **Non-root, numeric identity.** The final image must run as a **numeric
   UID/GID `10001`**, with no login shell and no home directory. If your base image
   has no such account (distroless has no shell and no `useradd`), create it
   explicitly in a `RUN` step — that requires a base that has `useradd`/`groupadd`,
   which means Debian-slim rather than distroless. State which trade-off you chose
   and why in one sentence.
8. **The service must be reachable.** The container must listen on `0.0.0.0:8080`
   (not `127.0.0.1`), so it is reachable via published ports.
9. **`ENTRYPOINT` in exec form** pointing at the absolute path of the binary in
   the final stage. No shell form, no `sh -c` wrapper.
10. **Correct signal handling.** The service is a long-running server, so it must
    receive `SIGTERM` and shut down cleanly. Verify that `docker stop` returns
    promptly and the process exits 0. Use `STOPSIGNAL SIGTERM` (the default, but
    state it explicitly) and make sure the binary is PID 1 or is wrapped in an
    init that forwards signals.
11. **`HEALTHCHECK` is required here.** Unlike Day 5's one-shot job, this process
    stays alive, so a healthcheck is appropriate. It must hit the app's own
    `/healthz` endpoint using a tool that is **actually present in the final
    image** — a healthcheck that shells out to `curl` or `wget` will fail on a
    distroless or minimal image. State how your healthcheck probes the service
    without a package install.
12. **`PORT` and `GREETING_NAME` are runtime-configurable** via environment
    variables read by the app, with no rebuild required.
13. **OCI metadata labels.** Add `org.opencontainers.image.title`, `...version`,
    `...source`, `...licenses`, and `...revision` as `LABEL` instructions with
    literal values.
14. **Image size — soft target ≤ 50 MB.** A Debian-slim final stage with a static
    binary lands well under this; a Go-toolchain-in-the-final-stage image lands
    in the hundreds of MB. This is a best-effort guideline; do not reach for
    scratch gymnastics beyond the standards above.
15. **No production Dockerfile is provided.** Author the Dockerfile yourself from
    these requirements alone.

## Dummy Application Mock (already written to this folder)

`main.go` — stdlib-only HTTP server. `GET /` → `hello, <GREETING_NAME>`;
`GET /healthz` → `ok`; listens on `$PORT` (default `8080`).

`go.mod`:
```
module example.com/greeter

go 1.22
```

Local sanity check (outside Docker), if Go is installed:
```bash
go run . ; curl -s localhost:8080/healthz
```

## Verification Criteria

Build with `docker build -t greeter:day6 "Day 6"`, then:

```bash
# 1. Service reachable, greeting honours the env var
docker run --rm -d --name g6 -p 8080:8080 greeter:day6
curl -s localhost:8080/                       # hello, world
docker rm -f g6
docker run --rm -d --name g6 -p 8080:8080 -e GREETING_NAME=team greeter:day6
curl -s localhost:8080/                       # hello, team
docker rm -f g6

# 2. Listening on 0.0.0.0, not loopback only
docker run --rm greeter:day6 & sleep 2; docker exec $! sh -c 'cat /proc/net/tcp' 2>/dev/null | head
# or: docker inspect -f '{{json .NetworkSettings}}' greeter:day6

# 3. No Go toolchain, no source, no module cache in the final image
docker run --rm --entrypoint ls greeter:day6 -la /          # no /usr/local/go
docker run --rm --entrypoint find greeter:day6 / -name 'go.mod' 2>/dev/null   # no results
docker run --rm --entrypoint find greeter:day6 / -name 'main.go' 2>/dev/null  # no results

# 4. Non-root numeric identity
docker run --rm --entrypoint id greeter:day6
docker inspect -f '{{.Config.User}}' greeter:day6     # 10001:10001 (or 10001)

# 5. Exec-form entrypoint, binary as PID 1
docker inspect -f '{{json .Config.Entrypoint}}' greeter:day6
docker inspect -f '{{json .Config.Cmd}}' greeter:day6  # empty or default args only

# 6. Healthcheck present and healthy
docker inspect -f '{{json .Config.Healthcheck}}' greeter:day6
docker run --rm -d --name g6 greeter:day6; sleep 5
docker inspect -f '{{.State.Health.Status}}' g6        # healthy
docker rm -f g6

# 7. Signal handling: SIGTERM shuts down promptly, exit status 0
docker run --rm --name g6 greeter:day6 &
docker stop --time 5 g6; echo "stop exit=$?"     # expect 0, prompt
docker wait g6 2>/dev/null; echo "container exit=$?"

# 8. Labels
docker inspect -f '{{json .Config.Labels}}' greeter:day6 | python3 -m json.tool

# 9. Size and lint
docker images greeter:day6 --format '{{.Size}}'    # soft target <= 50 MB
docker run --rm -i hadolint/hadolint < "Day 6/Dockerfile"
```

Submission must include the one-sentence justifications requested in items 7 and 11.
