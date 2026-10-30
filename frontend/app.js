/* Bench Notes UI. Identical for every variant; all backend access goes
 * through window.BenchApi (see api/*.js): list(), save(note), remove(id), ready(). */
(function () {
  'use strict';
  var api = window.BenchApi;
  var notes = [];
  var currentId = null;

  var $ = function (id) { return document.getElementById(id); };
  var listEl = $('note-list');
  var titleEl = $('note-title');
  var bodyEl = $('note-body');
  var statusEl = $('status');
  var readySent = false;

  function setStatus(text) { statusEl.textContent = text || ''; }

  function render() {
    listEl.textContent = '';
    notes.forEach(function (n) {
      var li = document.createElement('li');
      if (n.id === currentId) li.className = 'selected';
      var t = document.createElement('div');
      t.className = 'title';
      t.textContent = n.title || '(untitled)';
      var w = document.createElement('div');
      w.className = 'when';
      w.textContent = n.updated ? new Date(n.updated).toLocaleString() : '';
      li.appendChild(t);
      li.appendChild(w);
      li.addEventListener('click', function () { select(n.id); });
      listEl.appendChild(li);
    });
  }

  function select(id) {
    currentId = id;
    var n = notes.filter(function (x) { return x.id === id; })[0];
    titleEl.value = n ? n.title : '';
    bodyEl.value = n ? n.body : '';
    render();
  }

  function applyList(res) {
    notes = res.notes.slice().sort(function (a, b) { return b.updated - a.updated; });
    $('footer').textContent = res.variant + ' ' + res.version;
  }

  async function refresh() {
    applyList(await api.list());
    render();
  }

  async function onSave() {
    var note = { id: currentId, title: titleEl.value, body: bodyEl.value };
    try {
      var saved = await api.save(note);
      currentId = saved.id;
      await refresh();
      select(currentId);
      setStatus('Saved');
    } catch (e) {
      setStatus('Save failed: ' + e.message);
    }
  }

  async function onDelete() {
    if (!currentId) return;
    try {
      await api.remove(currentId);
      currentId = null;
      await refresh();
      select(null);
      setStatus('Deleted');
    } catch (e) {
      setStatus('Delete failed: ' + e.message);
    }
  }

  async function start() {
    $('new-note').addEventListener('click', function () { select(null); titleEl.focus(); });
    $('save-note').addEventListener('click', onSave);
    $('delete-note').addEventListener('click', onDelete);
    try {
      await refresh();
    } catch (e) {
      setStatus('Could not load notes: ' + e.message);
    }
    // First render is done; report readiness exactly once, after the next frame.
    requestAnimationFrame(function () {
      if (readySent) return;
      readySent = true;
      api.ready().catch(function (e) { setStatus('ready() failed: ' + e.message); });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
