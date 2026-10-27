FROM python:3.14.8-slim-bookworm

LABEL org.opencontainers.image.title="Audit App" \
    org.opencontainers.image.version="v1.0.0" \
    org.opencontainers.image.source="local" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.revision="r12-05"


RUN groupadd -g 10001 python && useradd -g 10001 -u 10001 --no-create-home -s /bin/false python
WORKDIR /usr/local/audit

COPY sample/ ./sample/
COPY sample-clean/ ./sample-clean/
COPY config/rules.json ./config/rules.json
COPY audit.py .

USER 10001:10001

ENTRYPOINT [ "python3", "/usr/local/audit/audit.py" ]
CMD [ "--root","/usr/local/audit/sample" ]
