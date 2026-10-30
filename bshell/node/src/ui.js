'use strict';
const fs = require('node:fs');
const http = require('node:http');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { BenchServer } = require('./server');
const { NoteStore, dataDir } = require('./store');
const { version } = require('./version');
const winpreflight = require('./winpreflight');
const { loadBinding, openWindow } = require('./webview');
const { logPath } = require('./logs');

const frontendDir = path.join(__dirname, '..', 'frontend');

function waitForSocket(port, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve) => {
    (function attempt() {
      const s = net.connect(port, '127.0.0.1');
      s.once('connect', () => { s.destroy(); resolve(true); });
      s.once('error', () => {
        s.destroy();
        if (Date.now() > deadline) return resolve(false);
        setTimeout(attempt, 50);
      });
    })();
  });
}

function get(server, pathname, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port: server.port, path: pathname, headers }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString('utf8') }));
    });
    req.on('error', reject);
  });
}

async function makeServer(variant, { directory, readyFile } = {}) {
  const store = new NoteStore(directory || dataDir(variant));
  return new BenchServer({
    variant, version, store, frontendDir,
    readyFile: readyFile || process.env.BENCH_READY_FILE,
  }).start();
}

async function selfTest(variant, { skipBackend = false, out = console.log } = {}) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'benchnotes-check-'));
  const server = await makeServer(variant, { directory: tmp, readyFile: null });
  try {
    if (!(await waitForSocket(server.port))) throw new Error('server did not accept connections');
    const page = await get(server, '/');
    if (page.status !== 200 || !page.body.includes('Bench Notes')) throw new Error('unexpected response for /');
    const noToken = await get(server, '/rpc/notes');
    if (noToken.status !== 403) throw new Error('expected 403 without token, got ' + noToken.status);
    const withToken = await get(server, '/rpc/notes', { 'X-Bench-Token': server.token });
    if (withToken.status !== 200) throw new Error('API refused a valid token');
    out('server ok on port ' + server.port);
  } finally {
    await server.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  if (skipBackend) {
    out('window backend check skipped (--skip-backend, test only)');
  } else {
    if (process.platform === 'win32') {
      const p = winpreflight.problems();
      if (p.length) throw new Error(p.join(' '));
    }
    loadBinding();
    out('window backend ok: @webviewjs/webview');
  }
  out('OK benchnotes ' + version + ' (' + variant + ')');
}

async function run(variant) {
  if (process.platform === 'win32') {
    const p = winpreflight.problems();
    if (p.length) {
      console.error(p.join(' '));
      return 3;
    }
  }
  const server = await makeServer(variant);
  if (!(await waitForSocket(server.port))) {
    console.error('server did not start');
    return 1;
  }
  openWindow(server.url + '/#token=' + server.token, {
    onClose: () => { server.close().then(() => process.exit(0)); },
  });
  return null; // keep running until the window closes
}

// Windows: node.exe is a console program. The shortcut starts it minimised and
// this re-launches it hidden and detached with output going to the log file.
function detach(argv) {
  const log = fs.openSync(logPath(process.env.BENCH_VARIANT || 'bshell-node'), 'a');
  const child = spawn(process.execPath, [path.join(__dirname, '..', 'bin', 'benchnotes.js'), ...argv],
    { detached: true, windowsHide: true, stdio: ['ignore', log, log] });
  child.unref();
}

module.exports = { selfTest, run, detach, makeServer, waitForSocket };
