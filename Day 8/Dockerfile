FROM rust:1.99.1-alpine3.24 AS builder

WORKDIR /app

COPY Cargo.lock Cargo.toml ./

COPY src ./src

RUN cargo build --release --locked --offline

FROM alpine:3.24.3 AS runtime

WORKDIR /app
RUN addgroup -g 10001 runner && \
    adduser -u 10001 -G runner -s /bin/false -H -D runner

COPY --from=builder --chown=10001:10001 /app/target/release/greeterd /app/greeterd

ENV PORT=8080
EXPOSE 8080

USER 10001:10001
ENTRYPOINT [ "/app/greeterd" ]

HEALTHCHECK --interval=30s --timeout=15s --start-period=5s --retries=3 \
    CMD wget --tries=1 --spider -q http://127.0.0.1:${PORT}/healthz || exit 1

