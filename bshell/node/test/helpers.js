'use strict';
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { BenchServer } = require('../src/server');
const { NoteStore } = require('../src/store');

function makeFrontend(tmp) {
  const d = path.join(tmp, 'frontend');
  fs.mkdirSync(path.join(d, 'api'), { recursive: true });
  fs.writeFileSync(path.join(d, 'index.html'), '<html><title>Bench Notes</title></html>');
  fs.writeFileSync(path.join(d, 'app.js'), '// app');
  fs.writeFileSync(path.join(d, 'api', 'adapter.js'), '// adapter');
  fs.writeFileSync(path.join(tmp, 'secret.txt'), 'outside the frontend dir');
  return d;
}

async function startServer() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'bn-test-'));
  const ready = path.join(tmp, 'ready.txt');
  const srv = await new BenchServer({
    variant: 'test', version: '9.9.9', store: new NoteStore(path.join(tmp, 'data')),
    frontendDir: makeFrontend(tmp), readyFile: ready,
  }).start();
  return { srv, tmp, ready, close: async () => { await srv.close(); fs.rmSync(tmp, { recursive: true, force: true }); } };
}

// Raw HTTP/1.1 request over a socket, so tests control the Host header fully
// (missing, duplicated, wrong). hostHeaders: array of values (each sent as a Host line).
function raw(port, { method = 'GET', path: p = '/', hostHeaders = [], headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const lines = [`${method} ${p} HTTP/1.1`];
    for (const h of hostHeaders) lines.push(`Host: ${h}`);
    for (const [k, v] of Object.entries(headers)) lines.push(`${k}: ${v}`);
    let payload = '';
    if (body !== undefined) {
      payload = typeof body === 'string' ? body : JSON.stringify(body);
      lines.push(`Content-Length: ${Buffer.byteLength(payload)}`);
    }
    lines.push('Connection: close', '', payload);
    const sock = net.connect(port, '127.0.0.1');
    const chunks = [];
    sock.on('data', (c) => chunks.push(c));
    sock.on('error', reject);
    sock.on('close', () => {
      const text = Buffer.concat(chunks).toString('utf8');
      const status = Number((/^HTTP\/1\.\d (\d+)/.exec(text) || [])[1]);
      const idx = text.indexOf('\r\n\r\n');
      resolve({ status, headers: text.slice(0, idx), body: text.slice(idx + 4) });
    });
    sock.write(lines.join('\r\n'));
  });
}

module.exports = { startServer, raw };
