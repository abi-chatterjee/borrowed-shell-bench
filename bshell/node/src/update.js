'use strict';
// Update path: npm install --offline <tarball>, online as fallback.
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function prefixDir() {
  const nm = path.resolve(__dirname, '..', '..');
  if (path.basename(nm) !== 'node_modules') return null;
  return path.dirname(nm);
}

function npmCommand(execPath = process.execPath, exists = require('node:fs').existsSync) {
  // Use the npm that ships next to the node running this app (the private runtime the
  // installer chose). A bare 'npm' resolves through PATH and can belong to an older system
  // Node, which installs the update and then fails.
  const name = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const sibling = path.join(path.dirname(execPath), name);
  return exists(sibling) ? sibling : name;
}

function update({ tarball, run = spawnSync, out = console.log, prefix = prefixDir() } = {}) {
  if (!prefix) { out('not installed under a node_modules directory; cannot update in place'); return 1; }
  if (!tarball) { out('update needs --tarball <path>'); return 2; }
  const base = ['install', '--no-audit', '--no-fund', '--prefix', prefix, tarball];
  const opts = { stdio: 'inherit', shell: process.platform === 'win32' };
  let r = run(npmCommand(), ['--offline', ...base], opts);
  if (r.status === 0) { out('updated from local tarball (offline)'); return 0; }
  out('offline install failed (exit ' + r.status + '); retrying with the registry');
  r = run(npmCommand(), base, opts);
  return r.status === 0 ? 0 : (r.status || 1);
}

module.exports = { update, prefixDir, npmCommand };
