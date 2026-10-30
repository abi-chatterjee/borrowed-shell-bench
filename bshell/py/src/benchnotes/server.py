"""Loopback HTTP server for Bench Notes (standard library only).

Hardening, applied to every request:
  * bound to 127.0.0.1 only, on a free port;
  * the Host header must be exactly 127.0.0.1:<port> (stops DNS rebinding);
  * if an Origin header is present it must be exactly http://127.0.0.1:<port>;
  * every /rpc/ request needs the per-launch token in X-Bench-Token
    (constant-time comparison); state-changing requests also need an Origin
    and a JSON content type, so a cross-site form cannot trigger them.
Static files come from an allow-list built at start-up (no path traversal).
"""
import hmac
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY_BYTES = 1_000_000
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def write_ready_file(path):
    """Write the current epoch milliseconds to path (atomically)."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="ascii") as f:
        f.write(str(int(time.time() * 1000)))
    os.replace(tmp, path)


def _static_map(frontend_dir):
    root = Path(frontend_dir)
    files = {}
    for p in root.rglob("*"):
        if p.is_file():
            files["/" + p.relative_to(root).as_posix()] = p
    if "/index.html" in files:
        files["/"] = files["/index.html"]
    return files


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class BenchServer:
    def __init__(self, variant, version, store, frontend_dir, token=None, ready_file=None):
        self.variant = variant
        self.version = version
        self.store = store
        self.token = token or secrets.token_urlsafe(32)
        self.ready_file = ready_file
        self._ready_written = False
        self._static = _static_map(frontend_dir)
        outer = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "BenchNotes"
            sys_version = ""

            def log_message(self, fmt, *args):  # keep stderr quiet (pythonw has none)
                pass

            # ---- helpers -------------------------------------------------
            def _send(self, status, body=b"", ctype="application/json", head=False):
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                for k, v in SECURITY_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()
                if not head:
                    self.wfile.write(body)

            def _json(self, status, obj, head=False):
                self._send(status, json.dumps(obj).encode("utf-8"), head=head)

            def _refuse(self, status, reason, head=False):
                self._json(status, {"error": reason}, head=head)

            def _guard(self, api, head=False):
                """Return True if the request may proceed."""
                hosts = self.headers.get_all("Host") or []
                if len(hosts) != 1 or hosts[0] != outer.expected_host:
                    self._refuse(403, "bad host", head)
                    return False
                origin = self.headers.get("Origin")
                if origin is not None and origin != outer.expected_origin:
                    self._refuse(403, "bad origin", head)
                    return False
                if api:
                    supplied = self.headers.get("X-Bench-Token") or ""
                    if not hmac.compare_digest(supplied.encode("utf-8"), outer.token.encode("utf-8")):
                        self._refuse(403, "bad token", head)
                        return False
                    if self.command not in ("GET", "HEAD") and origin is None:
                        self._refuse(403, "origin required", head)
                        return False
                return True

            def _read_json(self):
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype != "application/json":
                    self._refuse(415, "json required")
                    return None
                try:
                    length = int(self.headers.get("Content-Length") or "0")
                except ValueError:
                    length = -1
                if length < 0 or length > MAX_BODY_BYTES:
                    self._refuse(413, "bad length")
                    return None
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    return json.loads(raw.decode("utf-8"))
                except ValueError:
                    self._refuse(400, "bad json")
                    return None

            # ---- verbs ---------------------------------------------------
            def do_GET(self):
                self._get(head=False)

            def do_HEAD(self):
                self._get(head=True)

            def _get(self, head):
                path = self.path.split("?", 1)[0]
                api = path.startswith("/rpc/")
                if not self._guard(api, head):
                    return
                if api:
                    if path == "/rpc/notes":
                        self._json(200, {"variant": outer.variant, "version": outer.version,
                                         "notes": outer.store.list()}, head)
                    else:
                        self._refuse(404, "not found", head)
                    return
                f = outer._static.get(path)
                if f is None:
                    self._refuse(404, "not found", head)
                    return
                self._send(200, f.read_bytes(), CONTENT_TYPES.get(f.suffix, "application/octet-stream"), head)

            def do_POST(self):
                path = self.path.split("?", 1)[0]
                if not self._guard(path.startswith("/rpc/")):
                    return
                if path == "/rpc/notes":
                    note = self._read_json()
                    if note is None:
                        return
                    try:
                        self._json(200, outer.store.save(note))
                    except ValueError as e:
                        self._refuse(400, str(e))
                elif path == "/rpc/ready":
                    if self._read_json() is None:
                        return
                    outer.mark_ready()
                    self._json(200, {"ok": True})
                else:
                    self._refuse(404, "not found")

            def do_DELETE(self):
                path = self.path.split("?", 1)[0]
                if not self._guard(path.startswith("/rpc/")):
                    return
                if path.startswith("/rpc/notes/"):
                    ok = outer.store.remove(path[len("/rpc/notes/"):])
                    self._json(200 if ok else 404, {"ok": ok})
                else:
                    self._refuse(404, "not found")

            def _method_not_allowed(self):
                if self._guard(self.path.startswith("/rpc/")):
                    self._refuse(405, "method not allowed")

            do_PUT = do_PATCH = do_OPTIONS = _method_not_allowed

        self._httpd = _Server(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self.expected_host = f"127.0.0.1:{self.port}"
        self.expected_origin = f"http://{self.expected_host}"
        self.url = self.expected_origin
        self._thread = None

    def mark_ready(self):
        if self._ready_written:
            return
        self._ready_written = True
        if self.ready_file:
            write_ready_file(self.ready_file)

    def start(self):
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="benchnotes-http", daemon=True)
        self._thread.start()
        return self

    def shutdown(self):
        self._httpd.shutdown()
        self._httpd.server_close()
