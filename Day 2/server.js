const express = require('express');

const app = express();
const port = 8080;

const message = process.argv[2] || 'OK';

app.get('/', (req, res) => {
  res.status(200).type('text/plain').send(message);
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Listening on :${port}`);
});
