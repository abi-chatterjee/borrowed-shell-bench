/* Adapter for Wails v2: bound Go methods on window.go.main.App.
 * Wails injects the runtime and bindings into the served index.html. */
(function () {
  'use strict';
  function app() { return window.go.main.App; }
  window.BenchApi = {
    list: function () { return app().List(); },
    save: function (note) { return app().Save(note); },
    remove: function (id) { return app().Remove(id); },
    ready: function () { return app().Ready(); }
  };
})();
