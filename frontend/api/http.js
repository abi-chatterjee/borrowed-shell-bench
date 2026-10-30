/* Adapter for the loopback-HTTP variants (pyinstaller, bshell-py, bshell-node).
 * The per-launch token arrives in the URL fragment (never sent to the server in
 * a request line), is moved into memory/sessionStorage, and is sent on every
 * API call as the X-Bench-Token header. */
(function () {
  'use strict';
  var token = '';
  try {
    var m = /(?:^#|&)token=([^&]+)/.exec(window.location.hash || '');
    if (m) {
      token = decodeURIComponent(m[1]);
      try { window.sessionStorage.setItem('bench-token', token); } catch (e) { /* optional */ }
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    } else {
      try { token = window.sessionStorage.getItem('bench-token') || ''; } catch (e) { /* optional */ }
    }
  } catch (e) { /* no token: calls will be refused by the server */ }

  async function call(method, path, body) {
    var opts = { method: method, headers: { 'X-Bench-Token': token } };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    var res = await fetch(path, opts);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  window.BenchApi = {
    list: function () { return call('GET', '/rpc/notes'); },
    save: function (note) { return call('POST', '/rpc/notes', note); },
    remove: function (id) { return call('DELETE', '/rpc/notes/' + encodeURIComponent(id)); },
    ready: function () { return call('POST', '/rpc/ready', {}); }
  };
})();
