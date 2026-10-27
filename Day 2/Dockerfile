FROM node:24-alpine AS base

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm install --omit=dev


FROM alpine:3.24 AS runner

WORKDIR /app

RUN apk add --no-cache nodejs curl

COPY --from=base /app/node_modules ./node_modules
COPY server.js ./

USER nobody:nobody
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD [ "curl", "-f", "http://localhost:8080/" ]

ENTRYPOINT [ "node", "server.js" ]

CMD [ "OK" ]