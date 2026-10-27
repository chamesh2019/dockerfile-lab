# Day 2 — Single-Stage Build Foundations (Node.js)

## Topic / Focus
**Phase 1, Day 2:** Base image selection across languages, `COPY` minimization (dependency-first layering), `WORKDIR`, and `ENTRYPOINT` vs `CMD`.

## Scenario & Constraints
You are containerizing a tiny internal status-check service written in Node.js. The service must:

1. **Run from a slim base image** — do not use a full `node:latest` image. Pick an appropriate `-slim` or Alpine variant and justify it.
2. **Set a `WORKDIR`** — do not rely on the container root `/` as the working directory.
3. **Minimize `COPY` layers** — copy only the files required to run the app. Avoid `COPY . .` (copying the entire build context). Follow dependency-first layering: copy `package.json` (and `package-lock.json` if present) first, install dependencies, then copy application source. This keeps the `node_modules` install layer cached when only source changes.
4. **Demonstrate `ENTRYPOINT` vs `CMD`** — use `ENTRYPOINT` for the executable (`node server.js`) and `CMD` for default arguments, so the container can be overridden with `docker run  <alternate-arg>` at runtime without rewriting the entrypoint.
5. **Image size constraint** — final image must be under **150 MB**.
6. **No production Dockerfile provided** — you must author the Dockerfile from these requirements alone.

## Dummy Application Mock

`package.json`:
```json
{
  "name": "day2-status",
  "version": "1.0.0",
  "description": "Tiny internal status-check service (Node.js)",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.2"
  }
}
```

`server.js`:
```javascript
const express = require('express');

const app = express();
const port = 8080;

const message = process.argv[2] || 'OK';

app.get('/', (req, res) => {
  res.status(200).type('text/plain').send(message);
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Listening on :${port}`);
});
```

## Verification Criteria
Run these commands to validate your build:

1. **Build:** `docker build -t day2-status .`
2. **Size check:** `docker images day2-status` — confirm under 150 MB.
3. **Default run:** `docker run --rm -p 8080:8080 day2-status` then `curl http://localhost:8080/` → expect `OK`.
4. **Override run:** `docker run --rm -p 8080:8080 day2-status "HELLO WORLD"` then `curl http://localhost:8080/` → expect `HELLO WORLD` (proves `ENTRYPOINT` + `CMD` wiring).
5. **WORKDIR check:** `docker run --rm day2-status pwd` → should print your `WORKDIR`, not `/`.
6. **Lint:** `hadolint Dockerfile` — no DL warnings about `latest` tags or `apt-get` misuse.

Submit your `Dockerfile` (only) for evaluation via `/evaluate`.
