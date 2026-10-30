/* Adapter for Electron: window.benchBridge is exposed by preload.js through
 * contextBridge and forwards to ipcMain handlers. */
(function () {
  'use strict';
  var b = window.benchBridge;
  window.BenchApi = {
    list: function () { return b.list(); },
    save: function (note) { return b.save(note); },
    remove: function (id) { return b.remove(id); },
    ready: function () { return b.ready(); }
  };
})();
