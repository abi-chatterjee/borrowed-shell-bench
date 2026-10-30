'use strict';
// Note storage: one JSON file in a per-user data directory. Mirrors benchnotes/store.py.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');

const MAX_TITLE = 200;
const MAX_BODY = 100000;
const ID_RE = /^[0-9a-f]{32}$/;

function dataDir(variant, env = process.env, platform = process.platform, home = os.homedir()) {
  if (env.BENCH_DATA_DIR) return env.BENCH_DATA_DIR;
  let base;
  if (platform === 'darwin') {
    base = path.posix.join(home, 'Library', 'Application Support', 'BenchNotes');
  } else if (platform === 'win32') {
    base = path.win32.join(env.LOCALAPPDATA || path.win32.join(home, 'AppData', 'Local'), 'BenchNotes');
  } else {
    base = path.posix.join(env.XDG_DATA_HOME || path.posix.join(home, '.local', 'share'), 'BenchNotes');
  }
  return (platform === 'win32' ? path.win32 : path.posix).join(base, variant);
}

class NoteStore {
  constructor(directory) {
    this.directory = directory;
    this.file = path.join(directory, 'notes.json');
  }

  _load() {
    let raw;
    try {
      raw = fs.readFileSync(this.file, 'utf8');
    } catch (e) {
      if (e.code === 'ENOENT') return [];
      throw e;
    }
    try {
      const data = JSON.parse(raw);
      return Array.isArray(data.notes) ? data.notes : [];
    } catch (e) {
      try { fs.renameSync(this.file, path.join(this.directory, 'notes.corrupt')); } catch (_) { /* best effort */ }
      return [];
    }
  }

  _write(notes) {
    fs.mkdirSync(this.directory, { recursive: true });
    const tmp = this.file + '.tmp';
    const fd = fs.openSync(tmp, 'w');
    try {
      fs.writeSync(fd, JSON.stringify({ notes }));
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.renameSync(tmp, this.file);
  }

  list() { return this._load(); }

  save(note) {
    if (note === null || typeof note !== 'object' || Array.isArray(note)) throw new Error('note must be an object');
    const title = note.title === undefined ? '' : note.title;
    const body = note.body === undefined ? '' : note.body;
    if (typeof title !== 'string' || typeof body !== 'string') throw new Error('title and body must be strings');
    if (title.length > MAX_TITLE || body.length > MAX_BODY) throw new Error('note too large');
    let id = note.id;
    if (id !== undefined && id !== null && !(typeof id === 'string' && ID_RE.test(id))) throw new Error('bad id');
    id = id || crypto.randomBytes(16).toString('hex');
    const notes = this._load();
    const saved = { id, title, body, updated: Date.now() };
    const i = notes.findIndex((n) => n.id === id);
    if (i >= 0) notes[i] = saved; else notes.push(saved);
    this._write(notes);
    return saved;
  }

  remove(id) {
    const notes = this._load();
    const kept = notes.filter((n) => n.id !== id);
    if (kept.length === notes.length) return false;
    this._write(kept);
    return true;
  }
}

module.exports = { NoteStore, dataDir };
