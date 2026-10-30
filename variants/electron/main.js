'use strict';
// Bench Notes - Electron variant. Backend = ipcMain handlers; the renderer talks
// to them through the contextBridge API in preload.js (frontend/api/electron.js).
const { app, BrowserWindow, ipcMain } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { NoteStore, dataDir } = require('./store'); // copied from bshell/node/src by build.*

const VARIANT = 'electron';
const store = new NoteStore(dataDir(VARIANT));

function writeReady() {
  const file = process.env.BENCH_READY_FILE;
  if (!file) return;
  fs.writeFileSync(file + '.tmp', String(Date.now()));
  fs.renameSync(file + '.tmp', file);
}

// Headless smoke check: exercise the store, print one line, exit. No window.
function selfTest() {
  const tmp = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'bn-electron-'));
  const s = new NoteStore(tmp);
  const n = s.save({ title: 'smoke', body: 'ok' });
  const ok = s.list().length === 1 && s.remove(n.id) && s.list().length === 0;
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(ok ? 'OK ' + VARIANT + ' ' + app.getVersion() : 'FAILED store round trip');
  app.exit(ok ? 0 : 1);
}

ipcMain.handle('list', () => ({ variant: VARIANT, version: app.getVersion(), notes: store.list() }));
ipcMain.handle('save', (_e, note) => store.save(note));
ipcMain.handle('remove', (_e, id) => ({ ok: store.remove(id) }));
ipcMain.handle('ready', () => { writeReady(); return { ok: true }; });

app.whenReady().then(() => {
  if (process.env.BENCH_SELFTEST) return selfTest();
  const win = new BrowserWindow({
    width: 960, height: 640, title: 'Bench Notes',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.loadFile(path.join(__dirname, 'frontend', 'index.html'));
});

app.on('window-all-closed', () => app.quit());
