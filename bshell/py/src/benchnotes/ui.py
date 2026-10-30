"""Start the loopback server and show it in the OS web view (pywebview)."""
import socket
import sys
import time
import urllib.error
import urllib.request

from . import winpreflight
from ._version import __version__
from .server import BenchServer
from .store import NoteStore, data_dir

BACKEND_MODULE = {
    "darwin": "webview.platforms.cocoa",
    "win32": "webview.platforms.edgechromium",
}
# Force the real web view per OS so pywebview can never fall back to a legacy
# engine or a browser silently. None = let pywebview choose (Linux: GTK or Qt).
FORCED_GUI = {"darwin": "cocoa", "win32": "edgechromium"}


def frontend_dir():
    import importlib.resources as r
    return r.files("benchnotes") / "frontend"


def wait_for_socket(host, port, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def make_server(variant, ready_file=None, directory=None):
    import os
    store = NoteStore(directory or data_dir(variant))
    return BenchServer(variant, __version__, store, str(frontend_dir()),
                       ready_file=ready_file or os.environ.get("BENCH_READY_FILE"))


def import_backend():
    """Import the platform window backend; raise on failure (no fallback)."""
    import importlib
    if sys.platform == "win32":
        problems = winpreflight.problems()
        if problems:
            raise RuntimeError(" ".join(problems))
    name = BACKEND_MODULE.get(sys.platform, "webview.platforms.gtk")
    importlib.import_module("webview")
    return importlib.import_module(name)


def self_test(variant, skip_backend=False, out=print):
    """Start the server, fetch /, check the guards, import the window backend."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        srv = make_server(variant, ready_file=None, directory=tmp).start()
        try:
            if not wait_for_socket("127.0.0.1", srv.port):
                raise RuntimeError("server did not accept connections")
            with urllib.request.urlopen(srv.url + "/", timeout=5) as r:
                page = r.read().decode("utf-8")
            if r.status != 200 or "Bench Notes" not in page:
                raise RuntimeError("unexpected response for /")
            req = urllib.request.Request(srv.url + "/rpc/notes")
            try:
                urllib.request.urlopen(req, timeout=5)
                raise RuntimeError("API answered without a token")
            except urllib.error.HTTPError as e:
                if e.code != 403:
                    raise RuntimeError(f"expected 403 without token, got {e.code}")
            req = urllib.request.Request(srv.url + "/rpc/notes", headers={"X-Bench-Token": srv.token})
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status != 200:
                    raise RuntimeError("API refused a valid token")
            out("server ok on port %d" % srv.port)
        finally:
            srv.shutdown()
    if skip_backend:
        out("window backend check skipped (--skip-backend, test only)")
    else:
        mod = import_backend()
        out("window backend ok: " + mod.__name__)
    out("OK benchnotes %s (%s)" % (__version__, variant))


def run(variant):
    if sys.platform == "win32":
        problems = winpreflight.problems()
        if problems:
            text = " ".join(problems)
            print(text, file=sys.stderr)
            winpreflight.show_message_box(text)
            return 3
    import webview  # imported late so --check / update never need a display
    srv = make_server(variant).start()
    try:
        if not wait_for_socket("127.0.0.1", srv.port):
            print("server did not start", file=sys.stderr)
            return 1
        webview.create_window("Bench Notes", f"{srv.url}/#token={srv.token}", width=960, height=640)
        webview.start(gui=FORCED_GUI.get(sys.platform))
    finally:
        srv.shutdown()
    return 0
