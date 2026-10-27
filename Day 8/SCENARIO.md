# Day 8 — Multi-Stage Build: Rust Toolchain Out, musl Binary In

## Topic / Focus

**Phase 2 (Day 8):** the third multi-stage shape. Day 6 copied a Go static binary out of
a Debian toolchain; Day 7 split a Node build environment from a Node runtime dependency
set. Today the builder is a **Rust toolchain** (`cargo` + `rustc`, well over 1 GB in
`rust:alpine`) and the final image is a **single statically linked musl binary**.

There are two different `target/` directories in play, and both are traps:

- the **stale `target/` already sitting in this folder** — host build artifacts that must
  never enter the build context, let alone the image;
- the **builder's `target/`** — hundreds of MB of intermediate objects, dependency
  metadata, and debug artefacts that must be copied *out of* only as one finished binary.

**Deliberately out of scope today** (they arrive in later phases): dependency/cache mounts
and `ARG` build variables (Phase 3), `tini`/signal wrappers (Phase 5), and
distroless/scratch runtime gymnastics (Phase 6). This crate has **zero dependencies**, so
the entire build must succeed **offline**.

## Scenario & Constraints

You are packaging an internal greeting service as a minimal, non-root, production-shaped
container image.

1. **Two stages, named `builder` and `runtime`.** The final stage must be declared
   `FROM` a *runtime* base image — not `FROM builder` — and may receive files only via
   `COPY --from=builder`.
2. **Pinned musl builder.** Use an official Rust image pinned to an **exact version and
   Alpine distro**, e.g. `rust:<version>-alpine<distro>`. No `latest`, no floating
   `rust:alpine`, no moving minor tag. The version must understand lockfile format v4
   (Rust 1.83+). A Debian-based builder plus an added musl target is allowed, but then
   you must configure the musl target and linker yourself.
3. **Locked, offline build.** The builder must run
   `cargo build --release --locked --offline`. `Cargo.lock` is committed and the crate
   has no dependencies; no `cargo update`, no registry fetch, no network access is
   permitted for the build.
4. **Static musl binary.** The artefact copied into the final stage must be **statically
   linked against musl** (the default for an Alpine-hosted Rust builder). Prove it — see
   verification step 3.
5. **Copy only the binary.** Exactly one `COPY --from=builder`, pulling the compiled
   executable. No `COPY . .`, no source, no `Cargo.toml`/`Cargo.lock`, no `target/`
   directory, no `.rlib`/`.rmeta` files, and no `cargo`/`rustc` in the final image.
6. **Tame the build context.** This folder ships a **stale `target/` (~5 MB)** containing
   a decoy binary, a fake `.rlib`, and incremental junk. Add a `.dockerignore` that
   excludes `target/` (and any VCS directory) so the build context stays tiny. Verify the
   context size reported by `docker build`.
7. **Pinned final base.** Use `alpine:<exact patch>` (e.g. `alpine:3.20.x`). No `latest`,
   no floating distro tag. **No `apk add`** — everything needed must already be in the
   base image.
8. **Non-root, numeric identity.** The container must run as **`10001:10001`**, with no
   login shell and no home directory. Do not run as root, and do not rely on a
   pre-existing account.
9. **Reachable service.** Listen on **`0.0.0.0:8080`** (not `127.0.0.1`). `PORT` and
   `GREETING_NAME` must be runtime-configurable environment variables read by the app —
   no rebuild to change either.
10. **`ENTRYPOINT` in exec form**, pointing at the absolute path of the binary in the
    final stage. The binary must be PID 1: no `sh -c` wrapper and no shell-form entrypoint.
11. **`HEALTHCHECK` is required.** It must probe the app's own `/healthz` endpoint using a
    tool that is **actually present in the final image** — a healthcheck that shells out
    to `curl` fails here. Set an interval, timeout, and retry count.
12. **Cache-friendly layer order.** Copy `Cargo.toml` and `Cargo.lock` in a layer that
    comes **before** `src/`, so a source-only change cannot invalidate the manifest layer.
    (Dependency caching itself is Day 11+; today it is about layer boundaries, not mounts.)
13. **Image size — soft target ≤ 25 MB.** Alpine plus a static binary lands far below this;
    a final stage that still carries the Rust toolchain lands in the gigabytes. Size is a
    best-effort guideline: do not reach for `scratch`/distroless tricks today.
14. **Document shutdown behaviour.** In one sentence with your submission, state what
    `docker stop` does to this image. Rust's standard library does not install a `SIGTERM`
    handler, so the process dies on the default action (exit 143). That is acceptable
    today — do **not** add `tini` or `--init`; signal ownership is Phase 5.
15. **No production Dockerfile is provided.** Author it yourself from these requirements.

## Dummy Application Mock (already written to this folder)

- `Cargo.toml` — package `greeterd`, edition 2021, **no dependencies**.
- `Cargo.lock` — committed lockfile (format v4) for the zero-dependency build.
- `src/main.rs` — stdlib-only HTTP service. `GET /` → `hello, <GREETING_NAME>`;
  `GET /healthz` → `ok`; listens on `0.0.0.0:$PORT` (default `8080`) and handles each
  connection on its own thread.
- `target/` — **stale host build output** (decoy binary, fake `.rlib`, incremental junk).
  None of it may be shipped.

Core of `src/main.rs`:

```rust
fn main() {
    let port = env::var("PORT").unwrap_or_else(|_| String::from("8080"));
    let greeting = env::var("GREETING_NAME").unwrap_or_else(|_| String::from("world"));

    let listener = TcpListener::bind(format!("0.0.0.0:{port}"))
        .unwrap_or_else(|err| panic!("failed to bind 0.0.0.0:{port}: {err}"));

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                let greeting = greeting.clone();
                thread::spawn(move || respond(stream, &greeting));
            }
            Err(err) => eprintln!("connection error: {err}"),
        }
    }
}
```

Local sanity check (outside Docker, if Rust is installed):

```bash
cd "Day 8"
cargo build --release --locked --offline
PORT=18080 GREETING_NAME=team ./target/release/greeterd &
curl -s localhost:18080/healthz   # ok
curl -s localhost:18080/          # hello, team
kill %1
```

## Verification Criteria

Build with `docker build -t greeterd:day8 "Day 8"`, then:

```bash
# 1. Service reachable, runtime env honoured
docker run --rm -d --name g8 -p 8080:8080 greeterd:day8
curl -s localhost:8080/healthz          # ok
curl -s localhost:8080/                 # hello, world
docker rm -f g8

docker run --rm -d --name g8 -p 8080:8080 -e GREETING_NAME=team -e PORT=8080 greeterd:day8
curl -s localhost:8080/                 # hello, team
docker rm -f g8

# 2. No Rust toolchain, no source, no build artifacts in the final image
docker run --rm --entrypoint sh greeterd:day8 -c \
  'command -v cargo rustc; find / -name "Cargo.toml" -o -name "*.rlib" 2>/dev/null'
# expect: no output

# 3. Static-link proof
# 3a. In the builder: no PT_INTERP segment means no dynamic loader
docker build --target builder -t greeterd:day8-builder "Day 8"
docker run --rm --entrypoint sh greeterd:day8-builder -c \
  'readelf -l target/release/greeterd | grep -c INTERP || true'   # expect 0
# 3b. In the final image (busybox ldd; wording varies by musl version)
docker run --rm --entrypoint sh greeterd:day8 -c \
  'ldd "$(find / -type f -name greeterd 2>/dev/null | head -1)" 2>&1 || true'
# expect: not a dynamic executable

# 4. Non-root numeric identity
docker inspect -f '{{.Config.User}}' greeterd:day8        # 10001:10001
docker run --rm --entrypoint id greeterd:day8

# 5. Exec-form entrypoint, binary as PID 1
docker inspect -f '{{json .Config.Entrypoint}}' greeterd:day8
docker inspect -f '{{json .Config.Cmd}}' greeterd:day8     # empty or default args only

# 6. Healthcheck present, uses the app endpoint, and reports healthy
docker inspect -f '{{json .Config.Healthcheck}}' greeterd:day8
docker run --rm -d --name g8 greeterd:day8; sleep 6
docker inspect -f '{{.State.Health.Status}}' g8            # healthy
docker rm -f g8

# 7. Context hygiene: stale target/ stayed out of the build context
docker build --no-cache -t greeterd:day8 "Day 8" 2>&1 | grep -i "transferring context"
# expect a few hundred KB at most, not ~5 MB

# 8. Size and lint
docker images greeterd:day8 --format '{{.Size}}'           # soft target <= 25 MB
docker run --rm -i hadolint/hadolint < "Day 8/Dockerfile"

# 9. Shutdown behaviour (for your one-sentence note)
docker run -d --name g8 greeterd:day8
docker stop --time 5 g8; docker inspect -f '{{.State.ExitCode}}' g8   # 143 expected
docker rm -f g8
```

Submission must include the pinned-tag choice, the static-link proof, and the
one-sentence `docker stop` note requested in item 14.
