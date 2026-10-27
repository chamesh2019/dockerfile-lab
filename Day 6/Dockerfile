FROM golang:1.27.3-alpine3.24 AS builder

RUN addgroup -g 10001 greeter && \
    adduser -u 10001 -G greeter -s /bin/false -H -D greeter

WORKDIR /build

COPY go.mod .
COPY main.go .


RUN CGO_ENABLED=0 go build -v -o /build/greeter .

FROM gcr.io/distroless/static-debian12@sha256:d75cdd72874d4790092fcb1b058493ecf6bb5bf2b2b897045b00ff01d91843f2
LABEL org.opencontainers.image.title="Greeter" \
    org.opencontainers.image.version="v1.0.0" \
    org.opencontainers.image.source="local" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.revision="r12-05"

COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group
COPY --from=builder /etc/shadow /etc/shadow

WORKDIR /app
COPY --from=builder /build/greeter .

ENV PORT=8080 
EXPOSE 8080

USER 10001:10001
ENTRYPOINT [ "/app/greeter" ]

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=15s --start-period=5s --retries=3 \
    CMD ["/app/greeter", "-healthcheck"]

