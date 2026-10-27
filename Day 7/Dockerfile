# latest build image for node 26
FROM node:26.12.1-trixie-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./ 

RUN npm ci

COPY tsconfig.json .
COPY src/  ./src

RUN npm run build

FROM node:26.12.1-trixie-slim AS runner

LABEL org.opencontainers.image.title="Node Greeter" \
    org.opencontainers.image.version="v1.0.0" \
    org.opencontainers.image.source="local" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.revision="43-r13-beta"

RUN groupadd -g 10001 runner && \
    useradd -g 10001 -u 10001 -s /bin/false --no-create-home runner
WORKDIR /app

COPY package.json package-lock.json* ./

RUN --mount=type=cache,target=/root/.npm/ \
    npm ci --omit=dev
    
COPY --from=builder /app/dist ./dist

ENV PORT=8080
ENV NODE_ENV=production

USER 10001:10001
EXPOSE 8080
ENTRYPOINT [ "node", "./dist/server.js" ]

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=15s --start-period=5s --retries=3 \
    CMD [ "node", "-e", "fetch(`http://localhost:${process.env.PORT}/healthz`).then(r => r.ok ? process.exit(0) : process.exit(1)).catch(() => process.exit(1))" ]