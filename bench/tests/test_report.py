import csv
import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import report  # noqa: E402
import synthetic  # noqa: E402


class StatsTests(unittest.TestCase):
    def test_median_and_iqr(self):
        st = report.stats([1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(st["median"], 4.5)
        self.assertEqual((st["q1"], st["q3"]), (2.75, 6.25))
        self.assertEqual((st["min"], st["max"], st["n"]), (1, 8, 8))

    def test_single_value_has_no_spread(self):
        st = report.stats([5])
        self.assertEqual((st["q1"], st["q3"]), (5, 5))
        self.assertEqual(report.fmt(st, 1, "ms"), "5")

    def test_empty_is_dash(self):
        self.assertIsNone(report.stats([]))
        self.assertEqual(report.fmt(None, 1, "ms"), "-")

    def test_small_values_keep_two_decimals(self):
        st = report.stats([0.03 * 1024 * 1024])
        self.assertEqual(report.fmt(st, 1024 * 1024, "MB"), "0.03")

    def test_platform_labels(self):
        L = report.platform_label
        self.assertEqual(L({"os": "macos", "arch": "arm64"}), "macOS arm64")
        self.assertEqual(L({"os": "macos", "arch": "x86_64"}), "macOS x64")
        self.assertEqual(L({"os": "windows", "arch": "AMD64", "os_version": "Windows-10-10.0.22631-SP0"}), "Windows 11 x64")
        self.assertEqual(L({"os": "windows", "arch": "AMD64", "os_version": "Windows-10-10.0.19045-SP0"}), "Windows 10 x64")


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = synthetic.main(Path(self.tmp.name) / "in", runs=10)
        self.out = Path(self.tmp.name) / "out" / "summary.md"
        report.main([str(p) for p in sorted(self.dir.glob("*.json"))] + ["--out", str(self.out)])
        self.md = self.out.read_text()

    def test_banner_and_sections(self):
        self.assertIn("SYNTHETIC DATA", self.md)
        self.assertIn("## Table 7.5 - summary", self.md)
        for label in ("macOS arm64", "macOS x64", "Windows 10 x64", "Windows 11 x64"):
            self.assertIn("## " + label, self.md)

    def test_table_shape_one_row_per_variant_with_all_metric_columns(self):
        section = self.md.split("## macOS arm64")[1].split("Toolchain versions")[0]
        rows = [l for l in section.splitlines() if l.startswith("| ") and not l.startswith("| Strategy") and not l.startswith("|---")]
        self.assertEqual(len(rows), 7)
        header = [l for l in section.splitlines() if l.startswith("| Strategy")][0]
        for col in ("Download, runtime present", "Download, runtime absent", "Disk, first app", "Disk, marginal app",
                    "Idle memory, RSS sum", "Cold start, first launch", "Cold start, later launch", "Install time",
                    "Install success", "Update cost, bytes", "Update cost, time"):
            self.assertIn(col, header)
        self.assertEqual(len({len(r.split("|")) for r in rows}), 1, "ragged table")
        self.assertRegex(rows[0], r"\d+ \(\d+-\d+\)")  # median (Q1-Q3)

    def test_csv_has_every_platform_and_variant(self):
        rows = list(csv.DictReader(open(self.out.with_suffix(".csv"))))
        self.assertEqual({r["platform"] for r in rows}, {"macOS arm64", "macOS x64", "Windows 10 x64", "Windows 11 x64"})
        self.assertEqual({r["variant"] for r in rows}, set(synthetic.VARIANTS))
        cold = [r for r in rows if r["metric"] == "cold_first" and r["variant"] == "electron" and r["platform"] == "macOS arm64"][0]
        self.assertEqual(cold["n"], "10")
        self.assertLessEqual(float(cold["q1"]), float(cold["median"]))
        self.assertLessEqual(float(cold["median"]), float(cold["q3"]))

    def test_single_platform_table75(self):
        out2 = Path(self.tmp.name) / "o2.md"
        report.main([str(p) for p in sorted(self.dir.glob("*.json"))] + ["--out", str(out2), "--table75-platform", "macOS arm64"])
        self.assertIn("Table 7.5 - summary (macOS arm64)", out2.read_text())

    def test_unknown_platform_is_an_error(self):
        with self.assertRaises(SystemExit):
            report.main([str(p) for p in sorted(self.dir.glob("*.json"))] + ["--out", str(self.out), "--table75-platform", "BeOS"])


if __name__ == "__main__":
    unittest.main()
