FROM python:3.15.0-slim-bookworm

WORKDIR /app

RUN groupadd -g 10001 python && useradd -u 10001 -g 10001 --no-create-home -s /bin/false python

COPY static/ ./static/
COPY config/settings.json ./config/settings.json

COPY app.py ./

USER 10001:10001

EXPOSE 8080
ENTRYPOINT [ "python", "app.py" ]

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; port = os.environ.get('PORT', '8080'); exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2).status == 200 else 1)"]

CMD [ ] 