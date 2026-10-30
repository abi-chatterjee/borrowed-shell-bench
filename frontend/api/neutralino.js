/* Adapter for Neutralinojs. The client library is loaded here (index.html is
 * shared and cannot carry it). Persistence uses the native filesystem/os API
 * directly - there is no backend process - in the same notes.json format as
 * the other variants. */
document.write('<script src="/js/neutralino.js"><\/script>');
(function () {
  'use strict';
  var VARIANT = 'neutralino';
  var inited = false;
  var dirPromise = null;

  function init() {
    if (!inited) { Neutralino.init(); inited = true; }
  }

  async function dataDir() {
    if (!dirPromise) {
      dirPromise = (async function () {
        init();
        var dir = await Neutralino.os.getEnv('BENCH_DATA_DIR');
        if (!dir) {
          var base = await Neutralino.os.getPath('data');
          dir = base + '/BenchNotes/' + VARIANT;
        }
        // createDirectory is not recursive on every platform: create each level.
        var parts = dir.split(/[\\/]/);
        var acc = parts[0] === '' ? '' : parts[0];
        for (var i = 1; i < parts.length; i++) {
          acc += '/' + parts[i];
          try { await Neutralino.filesystem.createDirectory(acc); } catch (e) { /* exists */ }
        }
        return dir;
      })();
    }
    return dirPromise;
  }

  async function load() {
    var dir = await dataDir();
    try {
      var data = JSON.parse(await Neutralino.filesystem.readFile(dir + '/notes.json'));
      return Array.isArray(data.notes) ? data.notes : [];
    } catch (e) {
      return [];
    }
  }

  async function store(notes) {
    var dir = await dataDir();
    await Neutralino.filesystem.writeFile(dir + '/notes.json', JSON.stringify({ notes: notes }));
  }

  function newId() {
    var a = new Uint8Array(16);
    crypto.getRandomValues(a);
    return Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
  }

  window.BenchApi = {
    list: async function () {
      return { variant: VARIANT, version: window.NL_APPVERSION || 'unknown', notes: await load() };
    },
    save: async function (note) {
      var notes = await load();
      var saved = { id: note.id || newId(), title: String(note.title || ''), body: String(note.body || ''), updated: Date.now() };
      var i = notes.findIndex(function (n) { return n.id === saved.id; });
      if (i >= 0) notes[i] = saved; else notes.push(saved);
      await store(notes);
      return saved;
    },
    remove: async function (id) {
      var notes = await load();
      await store(notes.filter(function (n) { return n.id !== id; }));
      return { ok: true };
    },
    ready: async function () {
      init();
      var path = await Neutralino.os.getEnv('BENCH_READY_FILE');
      if (path) await Neutralino.filesystem.writeFile(path, String(Date.now()));
      return { ok: true };
    }
  };
})();
