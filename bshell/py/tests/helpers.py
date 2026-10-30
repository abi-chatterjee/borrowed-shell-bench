import http.client
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def make_frontend(tmp):
    """A tiny stand-in frontend so server tests do not depend on a staged build."""
    d = Path(tmp) / "frontend"
    (d / "api").mkdir(parents=True)
    (d / "index.html").write_text("<html><title>Bench Notes</title></html>")
    (d / "app.js").write_text("// app")
    (d / "api" / "adapter.js").write_text("// adapter")
    (Path(tmp) / "secret.txt").write_text("outside the frontend dir")
    return d


def request(srv, method, path, headers=None, body=None, host="__default__", raw_body=None):
    """Send a request with full control of the Host header."""
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    if host == "__default__":
        host = "127.0.0.1:%d" % srv.port
    if host is not None:
        conn.putheader("Host", host)
    for k, v in (headers or {}).items():
        conn.putheader(k, v)
    data = raw_body
    if body is not None:
        data = json.dumps(body).encode()
    if data is not None:
        conn.putheader("Content-Length", str(len(data)))
    conn.endheaders(data)
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    return resp.status, payload
