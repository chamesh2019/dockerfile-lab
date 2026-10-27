FROM python:3.11.0-slim

RUN groupadd -g 10001 python && useradd -g python -u 10001 python --no-create-home -s /bin/false
ENV STATUS_MESSAGE=OK

WORKDIR /app
COPY --chown=python:python requirements.txt ./
RUN pip install -r requirements.txt --no-cache-dir
COPY --chown=python:python app.py ./

USER 10001:10001

HEALTHCHECK --interval=60s --timeout=30s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/', timeout=2).status == 200 else 1)"]

EXPOSE 8080

ENTRYPOINT [ "python", "app.py" ]

CMD [ ] 