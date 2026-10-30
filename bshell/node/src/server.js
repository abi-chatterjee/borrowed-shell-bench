'use strict';
// Loopback HTTP server for Bench Notes (node:http only). Same hardening as the
// Python server: 127.0.0.1 only, exact Host, exact Origin when present, per-launch
// token on /rpc/ (constant-time compare), Origin + JSON required for writes,
// static files from an allow-list built at start-up.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const MAX_BODY_BYTES = 1000000;
const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};
const SECURITY_HEADERS = {
  'Content-Security-Policy': "default-src 'self'; frame-ancestors 'none'",
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Cache-Control': 'no-store',
};

function writeReadyFile(file) {
  const tmp = file + '.tmp';
  fs.writeFileSync(tmp, String(Date.now()));
  fs.renameSync(tmp, file);
}

function staticMap(root) {
  const files = new Map();
  (function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(p);
      else if (entry.isFile()) files.set('/' + path.relative(root, p).split(path.sep).join('/'), p);
    }
  })(root);
  if (files.has('/index.html')) files.set('/', files.get('/index.html'));
  return files;
}

function safeEqual(a, b) {
  const ba = Buffer.from(a, 'utf8');
  const bb = Buffer.from(b, 'utf8');
  // Compare equal-length digests so length differences do not short-circuit.
  const ha = crypto.createHash('sha256').update(ba).digest();
  const hb = crypto.createHash('sha256').update(bb).digest();
  return crypto.timingSafeEqual(ha, hb) && ba.length === bb.length;
}

class BenchServer {
  constructor({ variant, version, store, frontendDir, token, readyFile }) {
    this.variant = variant;
    this.version = version;
    this.store = store;
    this.token = token || crypto.randomBytes(32).toString('base64url');
    this.readyFile = readyFile || null;
    this.readyWritten = false;
    this.files = staticMap(frontendDir);
    this.server = http.createServer((req, res) => this._handle(req, res));
    this.server.keepAliveTimeout = 1000;
  }

  start() {
    return new Promise((resolve, reject) => {
      this.server.once('error', reject);
      this.server.listen(0, '127.0.0.1', () => {
        this.port = this.server.address().port;
        this.expectedHost = '127.0.0.1:' + this.port;
        this.expectedOrigin = 'http://' + this.expectedHost;
        this.url = this.expectedOrigin;
        resolve(this);
      });
    });
  }

  close() {
    return new Promise((resolve) => {
      this.server.close(() => resolve());
      this.server.closeAllConnections();
    });
  }

  markReady() {
    if (this.readyWritten) return;
    this.readyWritten = true;
    if (this.readyFile) writeReadyFile(this.readyFile);
  }

  _send(res, status, body, type, head) {
    const buf = Buffer.isBuffer(body) ? body : Buffer.from(body);
    res.writeHead(status, Object.assign({ 'Content-Type': type, 'Content-Length': buf.length }, SECURITY_HEADERS));
    res.end(head ? undefined : buf);
  }

  _json(res, status, obj, head) { this._send(res, status, JSON.stringify(obj), 'application/json', head); }

  _guard(req, res, api, head) {
    const hostHeaders = [];
    for (let i = 0; i < req.rawHeaders.length; i += 2) {
      if (req.rawHeaders[i].toLowerCase() === 'host') hostHeaders.push(req.rawHeaders[i + 1]);
    }
    if (hostHeaders.length !== 1 || hostHeaders[0] !== this.expectedHost) {
      this._json(res, 403, { error: 'bad host' }, head);
      return false;
    }
    const origin = req.headers.origin;
    if (origin !== undefined && origin !== this.expectedOrigin) {
      this._json(res, 403, { error: 'bad origin' }, head);
      return false;
    }
    if (api) {
      const supplied = req.headers['x-bench-token'];
      if (typeof supplied !== 'string' || !safeEqual(supplied, this.token)) {
        this._json(res, 403, { error: 'bad token' }, head);
        return false;
      }
      if (req.method !== 'GET' && req.method !== 'HEAD' && origin === undefined) {
        this._json(res, 403, { error: 'origin required' }, head);
        return false;
      }
    }
    return true;
  }

  _readJson(req, res) {
    return new Promise((resolve) => {
      const type = String(req.headers['content-type'] || '').split(';')[0].trim().toLowerCase();
      if (type !== 'application/json') { this._json(res, 415, { error: 'json required' }); return resolve(null); }
      const length = Number(req.headers['content-length'] || 0);
      if (!Number.isInteger(length) || length < 0 || length > MAX_BODY_BYTES) {
        this._json(res, 413, { error: 'bad length' });
        return resolve(null);
      }
      const chunks = [];
      let size = 0;
      req.on('data', (c) => {
        size += c.length;
        if (size > MAX_BODY_BYTES) { this._json(res, 413, { error: 'too large' }); req.destroy(); return resolve(null); }
        chunks.push(c);
      });
      req.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}')); }
        catch (e) { this._json(res, 400, { error: 'bad json' }); resolve(null); }
      });
      req.on('error', () => resolve(null));
    });
  }

  async _handle(req, res) {
    try {
      const pathname = (req.url || '/').split('?')[0];
      const api = pathname.startsWith('/rpc/');
      const head = req.method === 'HEAD';
      if (!this._guard(req, res, api, head)) return;
      if (req.method === 'GET' || head) {
        if (api) {
          if (pathname === '/rpc/notes') {
            return this._json(res, 200, { variant: this.variant, version: this.version, notes: this.store.list() }, head);
          }
          return this._json(res, 404, { error: 'not found' }, head);
        }
        const file = this.files.get(pathname);
        if (!file) return this._json(res, 404, { error: 'not found' }, head);
        return this._send(res, 200, fs.readFileSync(file), CONTENT_TYPES[path.extname(file)] || 'application/octet-stream', head);
      }
      if (req.method === 'POST' && pathname === '/rpc/notes') {
        const note = await this._readJson(req, res);
        if (note === null) return;
        try { return this._json(res, 200, this.store.save(note)); }
        catch (e) { return this._json(res, 400, { error: e.message }); }
      }
      if (req.method === 'POST' && pathname === '/rpc/ready') {
        if ((await this._readJson(req, res)) === null) return;
        this.markReady();
        return this._json(res, 200, { ok: true });
      }
      if (req.method === 'DELETE' && pathname.startsWith('/rpc/notes/')) {
        const ok = this.store.remove(pathname.slice('/rpc/notes/'.length));
        return this._json(res, ok ? 200 : 404, { ok });
      }
      if (['POST', 'DELETE'].includes(req.method)) return this._json(res, 404, { error: 'not found' });
      return this._json(res, 405, { error: 'method not allowed' });
    } catch (e) {
      if (!res.headersSent) this._json(res, 500, { error: 'internal error' });
    }
  }
}

module.exports = { BenchServer, writeReadyFile };
