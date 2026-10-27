# Day 5 — One-Shot Job Image: ENTRYPOINT/CMD Split, Exit Codes, and Runtime Arguments

## Topic / Focus

**Phase 1 capstone (Day 5):** base image selection, `COPY` minimization, `WORKDIR`, and — the main event — **`ENTRYPOINT` vs `CMD` semantics**.

Everything before this day built a long-running server image. This one is a **batch job**: it runs, prints a report, and exits. That changes the contract:

- the exit code **is** the product (0 = clean, 3 = violations found),
- arguments supplied at `docker run` must **append** to the executable, not replace it,
- runtime configuration must work through **both** appended arguments and environment variables,
- `HEALTHCHECK` is **wrong** here — there is no long-lived process to probe.

The app is stdlib-only Python. Nothing needs installing, and installing anything is a fail.

## Scenario & Constraints

You are packaging an internal compliance auditor as a portable, non-root, one-shot container image. Requirements:

1. **Pinned base image.** Use a slim Debian-based Python image pinned to an **exact patch version and distro** (a `python:3.12.x-slim-bookworm`-style tag). No `latest`, no floating `3.12-slim`, no digest-less moving tag. State your choice and why in one sentence when you submit.
2. **Set a `WORKDIR`.** Use `/usr/local/audit`. Do not run from `/`, and do not `cd` around it with shell commands.
3. **Copy only what runs — no `COPY . .`.** Copy `audit.py`, `config/rules.json`, `sample/`, and `sample-clean/` **only**. Order the layers so that the rules, sample data, and clean sample land in **earlier layers than `audit.py`** (application code changes most often; changing it must not invalidate the data layers).
4. **`ENTRYPOINT` must be the fixed executable in exec (JSON) form** — `python3` plus the absolute path to `audit.py`. The interpreter + script pair must be baked into `ENTRYPOINT`, not supplied by the caller.
5. **`CMD` must supply only default *arguments*** — the default root (`/usr/local/audit/sample`). `CMD` must **not** embed the interpreter, the script path, or an explicit `--format`, and must be in exec (JSON) form.
   Proof: all of these must work with no `python3` on the command line:
   ```
   docker run --rm <image>                                   # uses CMD default root
   docker run --rm <image> --root /usr/local/audit/sample-clean
   docker run --rm <image> --root /data --format json
   ```
   A shell-form `CMD` will **fail** the second and third commands: appended arguments replace the shell string entirely.
6. **Exit-code contract.** The container's exit status must be the app's exit status:
   - baked sample → **exit `3`**, report lists `2` violations (`dirty.txt:3: api_key`, `dirty.txt:4: TODO`);
   - `--root /usr/local/audit/sample-clean` → **exit `0`**;
   - nonexistent `--root /nope` → **exit `1`** and a diagnostic on stderr;
   - unknown flag → **exit `2`**.
   Do not wrap the entrypoint in anything that swallows or rewrites the status.
7. **Runtime-configurable output format.** `AUDIT_FORMAT=json` at `docker run` time must switch the report to JSON **without rebuilding**, and **without** needing `--format` on the command line. This means your default argument list must not pin `--format`; the app already reads `AUDIT_FORMAT` as its default. Confirm the precedence rule in your submission: an appended `--format` overrides the env var.
8. **Read-only mounted input.** The image must work against a mounted dataset:
   ```
   docker run --rm -v "$PWD/sample:/data:ro" <image> --root /data
   ```
   → exit `3`. Nothing under `/data` is baked into the image.
9. **Run as non-root with a numeric identity.** Create a dedicated account with explicit **UID/GID `10001`**, no login shell, no home directory, and switch with `USER 10001:10001` (numeric). The process must not need root at runtime.
10. **No package installation.** No `apt-get`, `apk`, `pip install`, or `curl | sh`. The app is stdlib-only; any package layer is a fail.
11. **Add OCI metadata labels.** At minimum `org.opencontainers.image.title`, `...version`, `...source`, `...licenses`, and `...revision`, all as `LABEL` instructions with literal values (no `ARG` plumbing required today).
12. **Do not define a `HEALTHCHECK`.** A one-shot job has no long-lived process to probe. Adding one is a fail; explain in one sentence why it does not belong here.
13. **Image size — soft target ≤ 120 MB.** Slim base is the entire lever. This is a best-effort guideline; do not reach for distroless/scratch.
14. **No production Dockerfile is provided.** Author the Dockerfile yourself from these requirements alone.

## Dummy Application Mock (already written to this folder)

`audit.py` — stdlib-only CLI. Reads `--root` (default `/usr/local/audit/sample`), `--format` (`text`|`json`, defaults to `$AUDIT_FORMAT`, then `text`), and `--rules` (default `/usr/local/audit/config/rules.json`, overridable via `$AUDIT_RULES`). Exit codes: `0` clean, `1` I/O or rules error, `2` usage error, `3` violations.

```python
import argparse, json, os, sys

EXIT_CLEAN, EXIT_IO, EXIT_USAGE, EXIT_VIOLATIONS = 0, 1, 2, 3
DEFAULT_RULES = os.environ.get("AUDIT_RULES", "/usr/local/audit/config/rules.json")
# scan() walks --root, matches rules["banned_tokens"] case-insensitively
# in files matching rules["extensions"], and returns hit records.
# main() returns EXIT_VIOLATIONS if any hit, else EXIT_CLEAN.
```

`config/rules.json`:
```json
{
  "banned_tokens": ["password", "api_key", "secret", "TODO"],
  "extensions": [".txt", ".md"]
}
```

`sample/` (dirty — 2 violations):
```
clean.txt    deployment notes, no hits
dirty.txt    line 3 contains "api_key"; line 4 contains "TODO"
```

`sample-clean/` (clean — 0 violations):
```
clean.txt    no hits
```

Local sanity check (outside Docker) before you build:
```bash
python3 audit.py --root sample --rules config/rules.json; echo "exit=$?"
# root=sample violations=2
# dirty.txt:3: api_key
# dirty.txt:4: TODO
# exit=3
```

## Verification Criteria

Run these after building (`docker build -t audit:day5 "Day 5"`):

```bash
# 1. Default CMD arguments, exec-form entrypoint → exit 3, 2 violations
docker run --rm audit:day5; echo "exit=$?"

# 2. Appended arguments override CMD, interpreter stays in ENTRYPOINT → exit 0
docker run --rm audit:day5 --root /usr/local/audit/sample-clean; echo "exit=$?"

# 3. Env var switches format without rebuild; appended flag wins over env
docker run --rm -e AUDIT_FORMAT=json audit:day5 --root /usr/local/audit/sample-clean
docker run --rm -e AUDIT_FORMAT=json audit:day5 --root /usr/local/audit/sample --format text

# 4. Exit codes propagate unchanged
docker run --rm audit:day5 --root /nope; echo "exit=$?"      # expect 1
docker run --rm audit:day5 --bogus-flag; echo "exit=$?"      # expect 2

# 5. Read-only mounted input
docker run --rm -v "$PWD/sample:/data:ro" audit:day5 --root /data; echo "exit=$?"   # expect 3

# 6. Non-root numeric identity at runtime
docker run --rm --entrypoint id audit:day5        # uid=10001 gid=10001, no root
docker inspect -f '{{.Config.User}}' audit:day5   # 10001:10001

# 7. Labels present; no Healthcheck config
docker inspect -f '{{json .Config.Labels}}' audit:day5 | python3 -m json.tool
docker inspect -f '{{json .Config.Healthcheck}}' audit:day5   # null

# 8. Size and lint
docker images audit:day5 --format '{{.Size}}'     # soft target <= 120 MB
hadolint "Day 5/Dockerfile"
dive audit:day5
```

Submission must include the one-sentence justifications requested in items 1, 7, and 12.
