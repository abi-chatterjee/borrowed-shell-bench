'use strict';
// The one place that touches the native web view binding (@webviewjs/webview,
// a napi-rs addon that wraps Rust wry/tao). Loading it is a real test: on
// Windows with Smart App Control, or with antivirus that blocks unsigned DLLs,
// require() throws here. No fallback to a browser.

function loadBinding() {
  try {
    return require('@webviewjs/webview');
  } catch (e) {
    const hint = process.platform === 'win32'
      ? ' Windows (Smart App Control or antivirus) may have blocked the unsigned native library.'
      : '';
    const err = new Error('Could not load the native web view library: ' + e.message + hint);
    err.cause = e;
    throw err;
  }
}

// On Windows the taskbar shows the window's icon, or the owning executable's (node.exe) when
// the window has none. macOS takes the icon from the .app bundle instead, so nothing is set there.
function windowsIcon() {
  if (process.platform !== 'win32') return null;
  try {
    return { data: require('fs').readFileSync(require('path').join(__dirname, '..', 'icon-64.rgba')), width: 64, height: 64 };
  } catch (e) {
    return null; // a missing icon is cosmetic; the app still runs
  }
}

function openWindow(url, { title = 'Bench Notes', width = 960, height = 640, onClose } = {}) {
  const { Application } = loadBinding();
  const app = new Application();
  const icon = windowsIcon();
  const win = app.createBrowserWindow(icon ? { title, width, height, windowsTaskbarIcon: icon } : { title, width, height });
  if (icon) win.setWindowIcon(icon.data, icon.width, icon.height);
  win.createWebview({ url });
  app.on('application-close-requested', () => {
    app.exit();
    if (onClose) onClose();
  });
  app.run();
  return app;
}

module.exports = { loadBinding, openWindow };
