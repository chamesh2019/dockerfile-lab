# named tag given in scenerio
FROM python:3.12.16-alpine3.24 AS builder
WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12.16-alpine3.24 AS runtime
WORKDIR /app

RUN addgroup -g 10001 appgroup && adduser -u 10001 appuser -s /bin/false -D -H -G appgroup

COPY --from=builder /opt/venv /opt/venv

COPY app.py gunicorn.conf.py wsgi.py ./
ENV PORT=8080
EXPOSE 8080

USER 10001:10001
ENTRYPOINT ["/opt/venv/bin/gunicorn", "-c", "/app/gunicorn.conf.py", "wsgi:app"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --spider --tries=1 -q http://127.0.0.1:$PORT/healthz || exit 1