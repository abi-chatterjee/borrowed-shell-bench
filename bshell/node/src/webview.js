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

function openWindow(url, { title = 'Bench Notes', width = 960, height = 640, onClose } = {}) {
  const { Application } = loadBinding();
  const app = new Application();
  const win = app.createBrowserWindow({ title, width, height });
  win.createWebview({ url });
  app.on('application-close-requested', () => {
    app.exit();
    if (onClose) onClose();
  });
  app.run();
  return app;
}

module.exports = { loadBinding, openWindow };
