/* Adapter for Tauri v2: commands via the global invoke
 * (app.withGlobalTauri = true in tauri.conf.json). */
(function () {
  'use strict';
  function invoke(cmd, args) { return window.__TAURI__.core.invoke(cmd, args || {}); }
  window.BenchApi = {
    list: function () { return invoke('list_notes'); },
    save: function (note) { return invoke('save_note', { note: note }); },
    remove: function (id) { return invoke('remove_note', { id: id }); },
    ready: function () { return invoke('ready'); }
  };
})();
