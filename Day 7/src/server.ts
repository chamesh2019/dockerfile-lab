import express, { Request, Response } from 'express';

const app = express();
const port = Number(process.env.PORT ?? 8080);
const greetingName = process.env.GREETING_NAME ?? 'world';
const version = process.env.APP_VERSION ?? '1.0.0';

app.get('/', (_req: Request, res: Response) => {
  res.type('text/plain').send(`hello, ${greetingName} (v${version})\n`);
});

app.get('/healthz', (_req: Request, res: Response) => {
  res.status(200).type('text/plain').send('ok\n');
});

const server = app.listen(port, '0.0.0.0', () => {
  console.log(`listening on 0.0.0.0:${port}`);
});

function shutdown(signal: string): void {
  console.log(`${signal} received, shutting down`);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 5000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
