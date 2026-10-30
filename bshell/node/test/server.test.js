'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { startServer, raw } = require('./helpers');

async function withServer(fn) {
  const ctx = await startServer();
  try { await fn(ctx); } finally { await ctx.close(); }
}

const req = (ctx, opts = {}) => raw(ctx.srv.port, Object.assign({ hostHeaders: [ctx.srv.expectedHost] }, opts));
const tok = (ctx) => ({ 'X-Bench-Token': ctx.srv.token });
const goodPost = (ctx) => Object.assign(tok(ctx), { Origin: ctx.srv.expectedOrigin, 'Content-Type': 'application/json' });

test('bound to loopback only', () => withServer(async ({ srv }) => {
  assert.equal(srv.server.address().address, '127.0.0.1');
}));

test('static served with exact Host', () => withServer(async (ctx) => {
  const r = await req(ctx);
  assert.equal(r.status, 200);
  assert.match(r.body, /Bench Notes/);
}));

test('adapter under api/ is static and needs no token', () => withServer(async (ctx) => {
  // Regression: scripts cannot send the token header, and the shared frontend
  // keeps its adapter at api/adapter.js, so the API prefix must not cover it.
  const r = await req(ctx, { path: '/api/adapter.js' });
  assert.equal(r.status, 200);
  assert.equal(r.body, '// adapter');
}));

test('wrong, missing or duplicated Host is refused', () => withServer(async (ctx) => {
  const port = ctx.srv.port;
  const bad = [`localhost:${port}`, `127.0.0.1:${port + 1}`, '127.0.0.1', `evil.example:${port}`,
    `[::1]:${port}`, `127.0.0.1:${port}.evil.example`, ''];
  for (const host of bad) {
    for (const [p, h] of [['/', {}], ['/rpc/notes', tok(ctx)]]) {
      const r = await raw(port, { path: p, hostHeaders: [host], headers: h });
      // An empty Host value is rejected by Node's parser (400); every other wrong value reaches our guard (403).
      const allowed = host === '' ? [400, 403] : [403];
      assert.ok(allowed.includes(r.status), `host=${JSON.stringify(host)} path=${p} -> ${r.status}`);
    }
  }
  const missing = await raw(port, { hostHeaders: [] });
  // Node's own parser rejects HTTP/1.1 without Host (400) before our guard runs; either way it is refused.
  assert.ok([400, 403].includes(missing.status), 'no Host header: ' + missing.status);
  const dup = await raw(port, { hostHeaders: [ctx.srv.expectedHost, 'evil.example'] });
  assert.ok([400, 403].includes(dup.status), 'duplicate Host: ' + dup.status);
}));

test('foreign Origin is refused', () => withServer(async (ctx) => {
  const port = ctx.srv.port;
  for (const origin of ['http://evil.example', `http://localhost:${port}`, 'null',
    `https://127.0.0.1:${port}`, ctx.srv.expectedOrigin + '.evil.example']) {
    let r = await req(ctx, { path: '/rpc/notes', headers: Object.assign(tok(ctx), { Origin: origin }) });
    assert.equal(r.status, 403, origin);
    r = await req(ctx, { headers: { Origin: origin } });
    assert.equal(r.status, 403, origin);
  }
  const ok = await req(ctx, { path: '/rpc/notes', headers: Object.assign(tok(ctx), { Origin: ctx.srv.expectedOrigin }) });
  assert.equal(ok.status, 200);
}));

test('state change needs an Origin', () => withServer(async (ctx) => {
  const r = await req(ctx, { method: 'POST', path: '/rpc/notes', headers: Object.assign(tok(ctx), { 'Content-Type': 'application/json' }), body: { title: 'x' } });
  assert.equal(r.status, 403);
  assert.deepEqual(ctx.srv.store.list(), []);
}));

test('missing or wrong token is refused', () => withServer(async (ctx) => {
  const variants = [{}, { 'X-Bench-Token': '' }, { 'X-Bench-Token': 'wrong' },
    { 'X-Bench-Token': ctx.srv.token + 'x' }, { 'X-Bench-Token': ctx.srv.token.slice(0, -1) }];
  for (const h of variants) {
    assert.equal((await req(ctx, { path: '/rpc/notes', headers: h })).status, 403, JSON.stringify(h));
    const w = Object.assign({}, h, { Origin: ctx.srv.expectedOrigin, 'Content-Type': 'application/json' });
    assert.equal((await req(ctx, { method: 'POST', path: '/rpc/notes', headers: w, body: { title: 'x' } })).status, 403);
    assert.equal((await req(ctx, { method: 'DELETE', path: '/rpc/notes/' + 'a'.repeat(32), headers: w })).status, 403);
    assert.equal((await req(ctx, { method: 'POST', path: '/rpc/ready', headers: w, body: {} })).status, 403);
  }
  assert.deepEqual(ctx.srv.store.list(), []);
  assert.equal(fs.existsSync(ctx.ready), false);
}));

test('token in the query string does not count', () => withServer(async (ctx) => {
  const r = await req(ctx, { path: '/rpc/notes?token=' + ctx.srv.token });
  assert.equal(r.status, 403);
}));

test('CRUD roundtrip and ready file written once', () => withServer(async (ctx) => {
  let r = await req(ctx, { method: 'POST', path: '/rpc/notes', headers: goodPost(ctx), body: { title: 't1', body: 'b1' } });
  assert.equal(r.status, 200);
  const note = JSON.parse(r.body);
  assert.match(note.id, /^[0-9a-f]{32}$/);
  r = await req(ctx, { path: '/rpc/notes', headers: tok(ctx) });
  const listing = JSON.parse(r.body);
  assert.equal(listing.variant, 'test');
  assert.equal(listing.version, '9.9.9');
  assert.deepEqual(listing.notes.map((n) => n.title), ['t1']);
  r = await req(ctx, { method: 'DELETE', path: '/rpc/notes/' + note.id, headers: goodPost(ctx) });
  assert.equal(r.status, 200);
  assert.deepEqual(JSON.parse((await req(ctx, { path: '/rpc/notes', headers: tok(ctx) })).body).notes, []);

  assert.equal((await req(ctx, { method: 'POST', path: '/rpc/ready', headers: goodPost(ctx), body: {} })).status, 200);
  const first = fs.readFileSync(ctx.ready, 'utf8');
  assert.match(first, /^\d{13}$/);
  await req(ctx, { method: 'POST', path: '/rpc/ready', headers: goodPost(ctx), body: {} });
  assert.equal(fs.readFileSync(ctx.ready, 'utf8'), first);
}));

test('bad input is rejected', () => withServer(async (ctx) => {
  const h = goodPost(ctx);
  const post = (body, headers = h) => req(ctx, { method: 'POST', path: '/rpc/notes', headers, body });
  assert.equal((await post('{nope')).status, 400);
  assert.equal((await post({ title: 5 })).status, 400);
  assert.equal((await post({ id: '../x' })).status, 400);
  assert.equal((await post({ body: 'x'.repeat(200000) })).status, 400);
  assert.equal((await post('{}', Object.assign({}, h, { 'Content-Type': 'text/plain' }))).status, 415);
  assert.equal((await req(ctx, { method: 'PUT', path: '/rpc/notes', headers: h, body: {} })).status, 405);
}));

test('no path traversal', () => withServer(async (ctx) => {
  for (const p of ['/../secret.txt', '/%2e%2e/secret.txt', '/rpc/../../secret.txt', '//etc/passwd', '/..%2fsecret.txt']) {
    const r = await req(ctx, { path: p });
    assert.ok([403, 404].includes(r.status), p + ' -> ' + r.status);
    assert.ok(!r.body.includes('outside the frontend dir'), p);
  }
}));

test('security headers', () => withServer(async (ctx) => {
  const r = await req(ctx);
  assert.match(r.headers, /Content-Security-Policy: default-src 'self'/i);
  assert.match(r.headers, /X-Content-Type-Options: nosniff/i);
}));
