import json
import os
import tempfile
import unittest
from pathlib import Path

from benchnotes.server import BenchServer
from benchnotes.store import NoteStore

from helpers import make_frontend, request


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ready = os.path.join(self.tmp.name, "ready.txt")
        fe = make_frontend(self.tmp.name)
        self.srv = BenchServer("test", "9.9.9", NoteStore(Path(self.tmp.name) / "data"), str(fe),
                               ready_file=self.ready).start()
        self.addCleanup(self.srv.shutdown)
        self.origin = self.srv.expected_origin
        self.tok = {"X-Bench-Token": self.srv.token}
        self.good_post = dict(self.tok, Origin=self.origin)
        self.good_post["Content-Type"] = "application/json"

    # ---- binding -------------------------------------------------------
    def test_bound_to_loopback_only(self):
        self.assertEqual(self.srv._httpd.server_address[0], "127.0.0.1")

    # ---- Host header ---------------------------------------------------
    def test_static_served_with_exact_host(self):
        status, body = request(self.srv, "GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Bench Notes", body)

    def test_adapter_under_api_dir_is_static_and_needs_no_token(self):
        # Regression: scripts cannot send the token header, and the shared frontend
        # keeps its adapter at api/adapter.js, so the API prefix must not cover it.
        status, body = request(self.srv, "GET", "/api/adapter.js")
        self.assertEqual((status, body), (200, b"// adapter"))

    def test_wrong_host_refused(self):
        for host in ("localhost:%d" % self.srv.port, "127.0.0.1:%d" % (self.srv.port + 1),
                     "127.0.0.1", "evil.example:%d" % self.srv.port, "[::1]:%d" % self.srv.port,
                     "127.0.0.1:%d.evil.example" % self.srv.port, "", None):
            for path, hdrs in (("/", {}), ("/rpc/notes", self.tok)):
                status, _ = request(self.srv, "GET", path, headers=hdrs, host=host)
                self.assertEqual(status, 403, (host, path))

    def test_duplicate_host_refused(self):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.srv.port, timeout=5)
        c.putrequest("GET", "/", skip_host=True)
        c.putheader("Host", "127.0.0.1:%d" % self.srv.port)
        c.putheader("Host", "evil.example")
        c.endheaders()
        self.assertEqual(c.getresponse().status, 403)

    # ---- Origin header -------------------------------------------------
    def test_foreign_origin_refused(self):
        for origin in ("http://evil.example", "http://localhost:%d" % self.srv.port, "null",
                       "https://127.0.0.1:%d" % self.srv.port, self.origin + ".evil.example"):
            status, _ = request(self.srv, "GET", "/rpc/notes", headers=dict(self.tok, Origin=origin))
            self.assertEqual(status, 403, origin)
            status, _ = request(self.srv, "GET", "/", headers={"Origin": origin})
            self.assertEqual(status, 403, origin)

    def test_matching_origin_accepted(self):
        status, _ = request(self.srv, "GET", "/rpc/notes", headers=dict(self.tok, Origin=self.origin))
        self.assertEqual(status, 200)

    def test_state_change_requires_origin(self):
        hdrs = dict(self.tok, **{"Content-Type": "application/json"})
        status, _ = request(self.srv, "POST", "/rpc/notes", headers=hdrs, body={"title": "x"})
        self.assertEqual(status, 403)
        self.assertEqual(self.srv.store.list(), [])

    # ---- token ---------------------------------------------------------
    def test_missing_or_wrong_token_refused(self):
        for hdrs in ({}, {"X-Bench-Token": ""}, {"X-Bench-Token": "wrong"},
                     {"X-Bench-Token": self.srv.token + "x"}, {"X-Bench-Token": self.srv.token[:-1]}):
            self.assertEqual(request(self.srv, "GET", "/rpc/notes", headers=hdrs)[0], 403, hdrs)
            h2 = dict(hdrs, Origin=self.origin)
            h2["Content-Type"] = "application/json"
            self.assertEqual(request(self.srv, "POST", "/rpc/notes", headers=h2, body={"title": "x"})[0], 403)
            self.assertEqual(request(self.srv, "DELETE", "/rpc/notes/" + "a" * 32, headers=h2)[0], 403)
            self.assertEqual(request(self.srv, "POST", "/rpc/ready", headers=h2, body={})[0], 403)
        self.assertEqual(self.srv.store.list(), [])
        self.assertFalse(os.path.exists(self.ready))

    def test_token_in_query_string_does_not_count(self):
        status, _ = request(self.srv, "GET", "/rpc/notes?token=" + self.srv.token)
        self.assertEqual(status, 403)

    def test_token_is_per_server(self):
        other = BenchServer("t", "1", NoteStore(Path(self.tmp.name) / "d2"), str(Path(self.tmp.name) / "frontend"))
        self.assertNotEqual(other.token, self.srv.token)
        self.assertGreaterEqual(len(self.srv.token), 32)
        other._httpd.server_close()

    # ---- API behaviour -------------------------------------------------
    def test_crud_roundtrip(self):
        status, body = request(self.srv, "POST", "/rpc/notes", headers=self.good_post,
                               body={"title": "t1", "body": "b1"})
        self.assertEqual(status, 200)
        note = json.loads(body)
        self.assertRegex(note["id"], r"^[0-9a-f]{32}$")
        status, body = request(self.srv, "GET", "/rpc/notes", headers=self.tok)
        listing = json.loads(body)
        self.assertEqual((listing["variant"], listing["version"]), ("test", "9.9.9"))
        self.assertEqual([n["title"] for n in listing["notes"]], ["t1"])
        note["title"] = "t2"
        request(self.srv, "POST", "/rpc/notes", headers=self.good_post, body=note)
        listing = json.loads(request(self.srv, "GET", "/rpc/notes", headers=self.tok)[1])
        self.assertEqual([n["title"] for n in listing["notes"]], ["t2"])
        status, _ = request(self.srv, "DELETE", "/rpc/notes/" + note["id"], headers=self.good_post)
        self.assertEqual(status, 200)
        listing = json.loads(request(self.srv, "GET", "/rpc/notes", headers=self.tok)[1])
        self.assertEqual(listing["notes"], [])

    def test_ready_writes_epoch_ms_once(self):
        status, _ = request(self.srv, "POST", "/rpc/ready", headers=self.good_post, body={})
        self.assertEqual(status, 200)
        first = Path(self.ready).read_text()
        self.assertTrue(first.isdigit() and len(first) == 13, first)
        request(self.srv, "POST", "/rpc/ready", headers=self.good_post, body={})
        self.assertEqual(Path(self.ready).read_text(), first)

    def test_bad_input_rejected(self):
        h = dict(self.good_post)
        self.assertEqual(request(self.srv, "POST", "/rpc/notes", headers=h, raw_body=b"{nope")[0], 400)
        self.assertEqual(request(self.srv, "POST", "/rpc/notes", headers=h, body={"title": 5})[0], 400)
        self.assertEqual(request(self.srv, "POST", "/rpc/notes", headers=h, body={"id": "../x"})[0], 400)
        self.assertEqual(request(self.srv, "POST", "/rpc/notes", headers=h, body={"body": "x" * 200_000})[0], 400)
        h2 = dict(h, **{"Content-Type": "text/plain"})
        self.assertEqual(request(self.srv, "POST", "/rpc/notes", headers=h2, raw_body=b"{}")[0], 415)
        self.assertEqual(request(self.srv, "PUT", "/rpc/notes", headers=h, body={})[0], 405)

    # ---- static files --------------------------------------------------
    def test_no_path_traversal(self):
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/rpc/../../secret.txt", "//etc/passwd",
                     "/..%2fsecret.txt", "/frontend/../secret.txt"):
            status, body = request(self.srv, "GET", path)
            self.assertIn(status, (403, 404), path)  # /rpc/.. is refused earlier, by the token check
            self.assertNotIn(b"outside the frontend dir", body)

    def test_security_headers(self):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.srv.port)
        c.request("GET", "/", headers={"Host": self.srv.expected_host})
        r = c.getresponse()
        self.assertIn("default-src 'self'", r.getheader("Content-Security-Policy"))
        self.assertEqual(r.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.getheader("Content-Type"), "text/html; charset=utf-8")


if __name__ == "__main__":
    unittest.main()
