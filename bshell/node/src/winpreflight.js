'use strict';
// Windows prerequisite for the web view: the WebView2 runtime. Unlike the
// Python variant there is no .NET dependency. Registry access goes through
// reg.exe because Node has no registry API; execFile is injectable for tests.
const { execFileSync } = require('node:child_process');

const GUID = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
const WEBVIEW2_URL = 'https://developer.microsoft.com/microsoft-edge/webview2/';
const KEYS = [
  'HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\' + GUID,
  'HKLM\\SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\' + GUID,
  'HKCU\\SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\' + GUID,
];

function webview2Version(exec = execFileSync) {
  for (const key of KEYS) {
    try {
      const out = exec('reg.exe', ['query', key, '/v', 'pv'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
      const m = /pv\s+REG_SZ\s+(\S+)/.exec(out);
      if (m && m[1] !== '0.0.0.0') return m[1];
    } catch (e) { /* key missing */ }
  }
  return null;
}

function problems(exec = execFileSync) {
  if (webview2Version(exec)) return [];
  return ['The Microsoft Edge WebView2 Runtime is not installed. Install it from ' + WEBVIEW2_URL + ' and start Bench Notes again.'];
}

module.exports = { problems, webview2Version };
