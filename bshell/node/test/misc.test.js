'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { NoteStore, dataDir } = require('../src/store');
const winpreflight = require('../src/winpreflight');
const update = require('../src/update');
const shell = require('../src/shell-macos');
const { parse } = require('../src/cli');

test('dataDir per platform and override', () => {
  const env = { LOCALAPPDATA: 'C:\\L' };
  assert.equal(dataDir('v', env, 'darwin', '/h'), '/h/Library/Application Support/BenchNotes/v');
  assert.equal(dataDir('v', env, 'win32', 'C:\\U'), 'C:\\L\\BenchNotes\\v');
  assert.equal(dataDir('v', {}, 'linux', '/h'), '/h/.local/share/BenchNotes/v');
  assert.equal(dataDir('v', { BENCH_DATA_DIR: '/x' }, 'darwin', '/h'), '/x');
});

test('store save/list/remove and corrupt file', () => {
  const t = fs.mkdtempSync(path.join(os.tmpdir(), 'bn-store-'));
  const s = new NoteStore(t);
  const n = s.save({ title: 'a', body: 'b' });
  assert.deepEqual(s.list(), [n]);
  assert.equal(s.remove(n.id), true);
  assert.equal(s.remove(n.id), false);
  fs.writeFileSync(path.join(t, 'notes.json'), '{broken');
  assert.deepEqual(s.list(), []);
  assert.ok(fs.existsSync(path.join(t, 'notes.corrupt')));
  fs.rmSync(t, { recursive: true, force: true });
});

test('winpreflight: present, placeholder and missing', () => {
  const present = () => 'HKLM\\...\n    pv    REG_SZ    120.0.1\n';
  assert.deepEqual(winpreflight.problems(present), []);
  const placeholder = () => '    pv    REG_SZ    0.0.0.0\n';
  assert.equal(winpreflight.problems(placeholder).length, 1);
  const missing = () => { throw new Error('not found'); };
  const p = winpreflight.problems(missing);
  assert.equal(p.length, 1);
  assert.match(p[0], /WebView2/);
});

test('update: offline first, online fallback', () => {
  const calls = [];
  const run = (cmd, args) => { calls.push(args); return { status: args.includes('--offline') ? 1 : 0 }; };
  assert.equal(update.update({ tarball: '/t/x.tgz', run, out: () => {}, prefix: '/p' }), 0);
  assert.equal(calls.length, 2);
  assert.ok(calls[0].includes('--offline'));
  assert.ok(!calls[1].includes('--offline'));
});

test('update refuses when not installed under node_modules', () => {
  assert.equal(update.update({ tarball: '/t/x.tgz', prefix: null, out: () => {} }), 1);
});

test('macOS shell: plist, launcher and layout', () => {
  assert.match(shell.infoPlist(), /com\.gritsa\.benchnotes\.bshellnode/);
  assert.match(shell.infoPlist(), /<key>CFBundleExecutable<\/key><string>launch<\/string>/);
  const script = shell.launcherScript("/p/it's/cli.js");
  assert.match(script, /^#!\/bin\/sh/);
  assert.match(script, /exec "\$here\/BenchNotes" '\/p\/it'\\''s\/cli\.js' ui "\$@"/);
  const t = fs.mkdtempSync(path.join(os.tmpdir(), 'bn-app-'));
  const app = path.join(t, 'A.app');
  shell.assemble(app, { nodeBinary: process.execPath, cli: '/x/cli.js' });
  const exe = path.join(app, 'Contents', 'MacOS', 'BenchNotes');
  assert.ok(fs.lstatSync(exe).isSymbolicLink());
  assert.equal(fs.readlinkSync(exe), process.execPath);
  assert.ok((fs.statSync(path.join(app, 'Contents', 'MacOS', 'launch')).mode & 0o111) !== 0);
  fs.rmSync(t, { recursive: true, force: true });
});

test('cli argument parsing', () => {
  const a = parse(['shell', 'build', '--apps-dir', '/a', '--skip-backend']);
  assert.deepEqual(a._, ['shell', 'build']);
  assert.equal(a.opts['apps-dir'], '/a');
  assert.ok(a.flags.has('skip-backend'));
});
