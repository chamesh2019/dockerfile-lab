// STALE BUILD ARTIFACT — left over from an earlier `npm run build`.
// If this file ends up in the final image, the container serves the wrong greeting.
const http = require('node:http');

http
  .createServer((req, res) => {
    if (req.url === '/healthz') {
      res.writeHead(200, { 'content-type': 'text/plain' });
      res.end('ok\n');
      return;
    }
    res.writeHead(200, { 'content-type': 'text/plain' });
    res.end('hello, STALE BUILD (v0.0.0)\n');
  })
  .listen(Number(process.env.PORT ?? 8080), '0.0.0.0');
