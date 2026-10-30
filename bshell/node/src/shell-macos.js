'use strict';
// Native macOS shell for the Node variant: a minimal .app whose executable is a
// symlink to the real node binary, plus a launcher script. Built in a staging
// directory, self-tested, then swapped in.
//
//   Bench Notes (bshell-node).app/Contents/
//     Info.plist
//     MacOS/launch                  shell script: logs, then execs BenchNotes
//     MacOS/BenchNotes -> <real node binary>
//     Resources/icon.icns
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { version } = require('./version');

const APP_NAME = 'Bench Notes (bshell-node)';
const BUNDLE_ID = 'com.gritsa.benchnotes.bshellnode';
const EXE = 'BenchNotes';
const CLI = path.resolve(__dirname, '..', 'bin', 'benchnotes.js');

function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function infoPlist() {
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Bench Notes</string>
  <key>CFBundleDisplayName</key><string>Bench Notes</string>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleVersion</key><string>${esc(version)}</string>
  <key>CFBundleShortVersionString</key><string>${esc(version)}</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
`;
}

function shQuote(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }

function launcherScript(cli = CLI) {
  return `#!/bin/sh
# Bench Notes (bshell-node) launcher. stdout/stderr go to a log file because a
# GUI app launched from Finder has no terminal.
here=$(cd "$(dirname "$0")" && pwd)
log_dir="\${BENCHNOTES_LOG_DIR:-$HOME/Library/Logs/BenchNotes}"
mkdir -p "$log_dir"
exec "$here/${EXE}" ${shQuote(cli)} ui "$@" >>"$log_dir/bshell-node.log" 2>&1
`;
}

function assemble(appDir, { nodeBinary = fs.realpathSync(process.execPath), icon, cli } = {}) {
  const macos = path.join(appDir, 'Contents', 'MacOS');
  const res = path.join(appDir, 'Contents', 'Resources');
  fs.mkdirSync(macos, { recursive: true });
  fs.mkdirSync(res, { recursive: true });
  fs.writeFileSync(path.join(appDir, 'Contents', 'Info.plist'), infoPlist());
  fs.writeFileSync(path.join(macos, 'launch'), launcherScript(cli), { mode: 0o755 });
  fs.symlinkSync(nodeBinary, path.join(macos, EXE));
  const packaged = path.resolve(__dirname, '..', 'icon.icns');
  const src = icon || (fs.existsSync(packaged) ? packaged : null);
  if (src) fs.copyFileSync(src, path.join(res, 'icon.icns'));
}

function selfTest(appDir, skipBackend) {
  const logDir = path.join(path.dirname(appDir), '.selftest-logs');
  const args = ['--check'].concat(skipBackend ? ['--skip-backend'] : []);
  const r = spawnSync(path.join(appDir, 'Contents', 'MacOS', 'launch'), args,
    { env: Object.assign({}, process.env, { BENCHNOTES_LOG_DIR: logDir }), timeout: 120000 });
  const logFile = path.join(logDir, 'bshell-node.log');
  const tail = fs.existsSync(logFile) ? fs.readFileSync(logFile, 'utf8').slice(-2000) : '(no log)';
  fs.rmSync(logDir, { recursive: true, force: true });
  if (r.status !== 0) throw new Error('shell self-test failed (exit ' + r.status + '). Log tail:\n' + tail);
}

function build(appsDir, { skipBackend = false, nodeBinary, icon, cli } = {}) {
  const apps = appsDir || process.env.BENCHNOTES_APPS_DIR || path.join(os.homedir(), 'Applications');
  fs.mkdirSync(apps, { recursive: true });
  const final = path.join(apps, APP_NAME + '.app');
  const staging = path.join(apps, '.' + APP_NAME + '.app.staging');
  fs.rmSync(staging, { recursive: true, force: true });
  try {
    assemble(staging, { nodeBinary, icon, cli });
    selfTest(staging, skipBackend);
    let old = null;
    if (fs.existsSync(final)) {
      old = path.join(apps, '.' + APP_NAME + '.app.old-' + Math.floor(Date.now() / 1000));
      fs.renameSync(final, old);
    }
    fs.renameSync(staging, final);
    if (old) fs.rmSync(old, { recursive: true, force: true });
  } finally {
    fs.rmSync(staging, { recursive: true, force: true });
  }
  return final;
}

module.exports = { build, assemble, infoPlist, launcherScript, APP_NAME, BUNDLE_ID };
