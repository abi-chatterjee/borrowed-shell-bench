"""End-to-end harness test on Linux/POSIX against fake apps: no GUI, no frameworks."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(HERE))

import psutil  # noqa: E402


@unittest.skipIf(os.name == "nt", "fake apps are POSIX shell scripts")
class HarnessEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dist = Path(cls.tmp.name) / "dist"
        subprocess.run([sys.executable, str(HERE / "fake_app" / "make_dist.py"), str(cls.dist)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_harness(self, variants, runs=2, extra=(), env=None):
        out = Path(self.tmp.name) / ("out-%d.json" % time.monotonic_ns())
        cmd = [sys.executable, str(ROOT / "bench" / "run.py"), "--dist", str(self.dist), "--variants", variants,
               "--runs", str(runs), "--idle-seconds", "1", "--no-quiet-check", "--out", str(out),
               "--scratch", str(Path(self.tmp.name) / "scratch")] + list(extra)
        r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, **(env or {})), timeout=300)
        return r, (json.loads(out.read_text()) if out.exists() else None)

    def test_zip_and_installer_variants_end_to_end(self):
        r, data = self.run_harness("fake-zip,fake-installer")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for v in ("fake-zip", "fake-installer"):
            rec = data["variants"][v]
            self.assertEqual(len(rec["runs"]), 2)
            for run in rec["runs"]:
                self.assertTrue(run["success"], run)
                self.assertGreater(run["first_launch_ms"], 250)   # fake app waits 300 ms
                self.assertLess(run["first_launch_ms"], 5000)
                self.assertGreater(run["second_launch_ms"], 250)
                self.assertGreater(run["idle_rss_bytes"], 30 * 1024 * 1024)   # 30 MB blob + interpreters
                self.assertGreaterEqual(run["idle_process_count"], 2)         # app + its helper
                self.assertEqual(run["leftover_procs"], 0)
                self.assertTrue(run["update_ok"], run)
        inst = data["variants"]["fake-installer"]
        self.assertEqual(inst["runs"][0]["update_model"], "package-update")
        self.assertEqual(data["variants"]["fake-zip"]["runs"][0]["update_model"], "full-replace")
        a = inst["absent"]
        self.assertTrue(a["ok"] and a["second_app_shared_runtime"], a)
        self.assertGreater(a["disk_first_app_bytes"], 5_000_000)      # includes the 5 MB fake runtime
        self.assertLess(a["disk_marginal_app_bytes"], 100_000)        # the second app shares it
        self.assertEqual(inst["runs"][0]["fetched_logged"].get("pip"), 123456)

    def test_app_that_never_becomes_ready_fails_loudly_and_leaves_nothing_behind(self):
        before = {p.pid for p in psutil.process_iter()}
        r, data = self.run_harness("fake-zip", runs=1, extra=["--ready-timeout", "2"], env={"FAKE_READY_DELAY_MS": "60000"})
        run = data["variants"]["fake-zip"]["runs"][0]
        self.assertFalse(run["success"])
        self.assertTrue(any("no ready file" in e for e in run["errors"]), run["errors"])
        self.assertEqual(r.returncode, 1)  # no successful run for the variant
        time.sleep(1)
        stray = [p for p in psutil.process_iter(["cmdline"]) if p.pid not in before and "fake_app.py" in " ".join(p.info["cmdline"] or [])]
        self.assertEqual(stray, [], "fake app processes were left running")

    def test_missing_variants_are_reported_not_fatal(self):
        r, data = self.run_harness("fake-zip,does-not-exist", runs=1)
        self.assertEqual(data["skipped"], ["does-not-exist"])
        self.assertIn("fake-zip", data["variants"])

    def test_smoke_mode_is_short(self):
        t0 = time.time()
        r, data = self.run_harness("fake-zip", runs=5, extra=["--smoke"])
        self.assertEqual(len(data["variants"]["fake-zip"]["runs"]), 1)
        self.assertLess(time.time() - t0, 60)

    def test_report_runs_on_harness_output(self):
        r, data = self.run_harness("fake-zip,fake-installer", runs=2)
        out = Path(self.tmp.name) / "rep"
        results = sorted(Path(self.tmp.name).glob("out-*.json"))[-1]
        import report
        report.main([str(results), "--out", str(out / "summary.md")])
        md = (out / "summary.md").read_text()
        self.assertIn("## Table 7.5", md)
        self.assertNotIn("SYNTHETIC", md)


if __name__ == "__main__":
    unittest.main()
