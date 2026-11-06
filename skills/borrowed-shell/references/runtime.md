# Runtime: loopback server, window, logging, preflight

Placeholders: `<pkg>` Python package / npm name, `<App Name>` display name, `<APP>` env-var prefix.

## Process model

```
main thread:   preflight -> start server thread -> wait for socket -> open window (blocks) -> shutdown server
server thread: ThreadingHTTPServer / http.createServer on 127.0.0.1:0 (daemon)
```

## Python skeleton (stdlib server + pywebview)

```python
# <pkg>/ui.py
import secrets, socket, sys, time
FORCED_GUI = {"darwin": "cocoa", "win32": "edgechromium"}          # never let pywebview pick a fallback
BACKEND_MODULE = {"darwin": "webview.platforms.cocoa", "win32": "webview.platforms.edgechromium"}

def wait_for_socket(host, port, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False

def run():
    if sys.platform == "win32":
        problems = winpreflight.problems()            # see below; BEFORE importing webview
        if problems:
            winpreflight.show_message_box(" ".join(problems)); return 3
    import webview                                     # late import: --check and update need no display
    srv = make_server().start()                        # binds 127.0.0.1:0, daemon thread
    try:
        if not wait_for_socket("127.0.0.1", srv.port):
            return 1
        webview.create_window("<App Name>", f"{srv.url}/#token={srv.token}", width=960, height=640)
        webview.start(gui=FORCED_GUI.get(sys.platform), icon=windows_icon_or_none())
    finally:
        srv.shutdown()
    return 0
```

`main()` must begin with the stdout fix, before any import that may print:

```python
def redirect_std_streams_if_missing(log_path):
    if sys.stdout is not None and sys.stderr is not None:
        return
    stream = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
    if sys.stdout is None: sys.stdout = stream
    if sys.stderr is None: sys.stderr = stream
```

## Server guard (port this logic exactly; it is what the tests check)

```python
expected_host   = f"127.0.0.1:{port}"
expected_origin = f"http://{expected_host}"
token = secrets.token_urlsafe(32)

def guard(handler, is_api):
    hosts = handler.headers.get_all("Host") or []
    if len(hosts) != 1 or hosts[0] != expected_host:          return refuse(403, "bad host")    # DNS rebinding
    origin = handler.headers.get("Origin")
    if origin is not None and origin != expected_origin:      return refuse(403, "bad origin")
    if is_api:
        supplied = handler.headers.get("X-<App>-Token") or ""
        if not hmac.compare_digest(supplied.encode(), token.encode()): return refuse(403, "bad token")
        if handler.command not in ("GET", "HEAD") and origin is None:  return refuse(403, "origin required")
    return True
# POST/PUT bodies: require Content-Type application/json (415 otherwise), cap length (413).
# Static: build {"/path": file} from the frontend dir at start-up; 404 anything not in the map.
# Every response: Content-Security-Policy "default-src 'self'; frame-ancestors 'none'",
#   X-Content-Type-Options nosniff, Referrer-Policy no-referrer, Cache-Control no-store.
# Override log_message() to do nothing (pythonw has no stderr).
```

Frontend: read the token once from `location.hash`, then `history.replaceState(null, '', location.pathname)` to drop it from the URL, and send it as the header on every API call.

Tests to write (one each): wrong Host -> 403; foreign Origin -> 403; API without token -> 403; POST without Origin -> 403; POST with text/plain -> 415; path traversal (`/../x`) -> 404; valid token -> 200.

## Node.js equivalents

- Server: `http.createServer` listening on `('127.0.0.1', 0)`; same guard; `crypto.timingSafeEqual` on equal-length buffers.
- Window: `@webviewjs/webview`:
  ```js
  const { Application } = require('@webviewjs/webview');   // wrap in try/catch -> actionable error
  const app = new Application();
  const win = app.createBrowserWindow({ title: '<App Name>', width: 960, height: 640 /*, windowsTaskbarIcon */ });
  win.createWebview({ url: `${url}/#token=${token}` });
  app.on('application-close-requested', () => { app.exit(); server.close(); });
  app.run();
  ```
- Requires Node >= 24 (platform packages declare `engines.node >= 24`; older npm skips them without an error). Check `process.versions.node` in the self-test.
- Windows: `node.exe` is a console program. The shortcut starts it minimised; the app re-spawns itself `{ detached: true, windowsHide: true, stdio: ['ignore', log, log] }` and the parent exits.

## Windows preflight (before importing the backend)

pywebview's Edge backend needs the WebView2 Runtime and .NET Framework 4.7.2+. Importing the backend without them flips pywebview to the legacy engine **and writes a registry key**, so check first:

```python
WEBVIEW2 = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"   # value "pv", not "0.0.0.0"
# check HKLM\SOFTWARE\WOW6432Node\<WEBVIEW2>, HKLM\SOFTWARE\<WEBVIEW2>, HKCU\SOFTWARE\<WEBVIEW2>
NET = r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"                            # value "Release" >= 461808
```

Return a list of sentences ("Install the Microsoft Edge WebView2 Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and start <App Name> again."). Show them in a native message box (`ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)`) because there is no console.

The Node binding uses WebView2 too; run the WebView2 check there as well.

## Packaging

- Python: pure wheel (`py3-none-any`). Ship the frontend inside the package (hatchling: list it under `artifacts` if it is generated and git-ignored). Keep dependencies minimal; pin `pywebview` exactly.
- Node: npm tarball with `bin/<pkg>.js`; frontend under the package dir.
- Ship `icon.icns` (macOS) and `icon.ico` (Windows) inside the package; the installer copies the `.ico` out of the environment so shortcuts survive upgrades.
