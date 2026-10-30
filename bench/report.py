#!/usr/bin/env python3
"""Aggregate results files into median and IQR per metric per platform.

  python bench/report.py results/*.json --out results/summary.md [--csv results/summary.csv]

Writes
  * "Table 7.5": one row per variant, one column group per metric (medians, IQR in brackets)
  * one table per platform (macOS arm64, macOS x64, Windows 10, Windows 11, ...)
  * a CSV with every metric of every variant of every platform (long format).

The shape of Table 7.5 is an assumption (the paper text is not in this repository): rows are
the variants, columns follow the metric list of the plan. Change TABLE_75 below to match
the paper; nothing else depends on it."""
import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

MB = 1024 * 1024
ORDER = ["electron", "tauri", "wails", "neutralino", "pyinstaller", "bshell-py", "bshell-node"]
TITLES = {
    "electron": "Electron", "tauri": "Tauri v2", "wails": "Wails v2", "neutralino": "Neutralinojs",
    "pyinstaller": "PyInstaller + pywebview", "bshell-py": "Borrowed Shell (Python)",
    "bshell-node": "Borrowed Shell (Node.js)",
}


# ---- metric extraction: each returns a list of numbers (one per run, or one value) ----------

def _runs(rec, key):
    return [r[key] for r in rec["runs"] if r.get(key) is not None]


def _deps_bytes(run):
    f = run.get("fetched_logged") or {}
    return sum(v for k, v in f.items() if k in ("pip", "npm", "wheel", "tarball"))


def download_present(rec):
    if rec["kind"] == "zip":
        return [rec["artifact_bytes"]]
    return [rec["artifact_bytes"] + _deps_bytes(r) for r in rec["runs"] if r.get("install_ok")]


def download_absent(rec):
    if rec["kind"] == "zip":
        return [rec["artifact_bytes"]]
    a = rec.get("absent") or {}
    if a.get("net_bytes") is not None and a.get("ok"):
        return [rec["artifact_bytes"] + a["net_bytes"]]
    return []


def disk_first(rec):
    if rec["kind"] == "zip":
        return _runs(rec, "disk_install_bytes")
    a = rec.get("absent") or {}
    return [a["disk_first_app_bytes"]] if a.get("disk_first_app_bytes") is not None else []


def disk_marginal(rec):
    if rec["kind"] == "zip":
        return _runs(rec, "disk_install_bytes")
    a = rec.get("absent") or {}
    return [a["disk_marginal_app_bytes"]] if a.get("disk_marginal_app_bytes") is not None else []


def update_bytes(rec):
    out = []
    for r in rec["runs"]:
        if r.get("update_artifact_bytes") is not None and r.get("update_ok", True):
            out.append(r["update_artifact_bytes"] + (r.get("update_net_bytes") or 0))
    return out


def success_rate(rec):
    runs = rec["runs"]
    return [sum(1 for r in runs if r.get("success"))], len(runs)


# key, label, unit, divisor, extractor
METRICS = [
    ("download_present", "Download, runtime present", "MB", MB, download_present),
    ("download_absent", "Download, runtime absent", "MB", MB, download_absent),
    ("disk_first", "Disk, first app", "MB", MB, disk_first),
    ("disk_marginal", "Disk, marginal app", "MB", MB, disk_marginal),
    ("idle_rss", "Idle memory, RSS sum", "MB", MB, lambda rec: _runs(rec, "idle_rss_bytes")),
    ("idle_uss", "Idle memory, USS sum", "MB", MB, lambda rec: _runs(rec, "idle_uss_bytes")),
    ("idle_footprint", "Idle memory, phys. footprint (macOS)", "MB", MB, lambda rec: _runs(rec, "idle_footprint_bytes")),
    ("cold_first", "Cold start, first launch", "ms", 1, lambda rec: _runs(rec, "first_launch_ms")),
    ("cold_next", "Cold start, later launch", "ms", 1, lambda rec: _runs(rec, "second_launch_ms")),
    ("install_time", "Install time", "s", 1, lambda rec: _runs(rec, "install_s")),
    ("update_bytes", "Update cost, bytes", "MB", MB, update_bytes),
    ("update_time", "Update cost, time", "s", 1, lambda rec: _runs(rec, "update_s")),
]
METRIC_BY_KEY = {m[0]: m for m in METRICS}

# Columns of "Table 7.5" (assumed shape, see module docstring).
TABLE_75 = [
    ("download_present", "download_absent"), ("disk_first", "disk_marginal"), ("idle_rss", "idle_footprint"),
    ("cold_first", "cold_next"), ("install_time",), ("update_bytes", "update_time"),
]


def stats(values):
    v = sorted(values)
    if not v:
        return None
    med = statistics.median(v)
    if len(v) >= 2:
        q = statistics.quantiles(v, n=4, method="inclusive")
        q1, q3 = q[0], q[2]
    else:
        q1 = q3 = med
    return {"n": len(v), "median": med, "q1": q1, "q3": q3, "min": v[0], "max": v[-1]}


def fmt(st, div, unit, with_iqr=True):
    if st is None:
        return "-"
    def one(x):
        x = x / div
        if unit == "ms" or x >= 100:
            return "%.0f" % x
        return "%.2f" % x if x < 1 else "%.1f" % x
    if st["n"] < 2 or not with_iqr:
        return one(st["median"])
    return "%s (%s-%s)" % (one(st["median"]), one(st["q1"]), one(st["q3"]))


def platform_label(host):
    os_name, arch = host.get("os"), host.get("arch", "")
    arch = {"x86_64": "x64", "AMD64": "x64", "amd64": "x64", "aarch64": "arm64"}.get(arch, arch)
    if os_name == "windows":
        m = re.search(r"10\.0\.(\d+)", host.get("os_version", ""))
        ver = "11" if m and int(m.group(1)) >= 22000 else "10"
        return "Windows %s %s" % (ver, arch)
    if os_name == "macos":
        return "macOS %s" % arch
    return "%s %s (test only)" % (os_name, arch)


def load(paths):
    """{platform_label: {variant: merged record}}. Runs from several machines/files of the
    same platform are pooled (each file contributes its own runs)."""
    plats = {}
    synthetic = False
    for p in paths:
        data = json.loads(Path(p).read_text())
        host = data["host"]
        synthetic = synthetic or bool(host.get("synthetic"))
        label = platform_label(host)
        for v, rec in data["variants"].items():
            tgt = plats.setdefault(label, {})
            if v not in tgt:
                tgt[v] = json.loads(json.dumps(rec))
            else:
                tgt[v]["runs"].extend(rec["runs"])
                if rec.get("absent") and not tgt[v].get("absent"):
                    tgt[v]["absent"] = rec["absent"]
    return plats, synthetic


def ordered(variants):
    return sorted(variants, key=lambda v: (ORDER.index(v) if v in ORDER else 99, v))


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def cell(rec, key):
    _k, _label, unit, div, fn = METRIC_BY_KEY[key]
    return fmt(stats(fn(rec)), div, unit)


def success_cell(rec):
    ok, total = success_rate(rec)
    return "%d/%d" % (ok[0], total)


def table_for(variants_map, columns):
    header = ["Strategy"]
    for group in columns:
        for key in group:
            m = METRIC_BY_KEY[key]
            header.append("%s (%s)" % (m[1], m[2]))
        if group == ("install_time",):
            header.append("Install success")
    rows = []
    for v in ordered(variants_map):
        rec = variants_map[v]
        row = [TITLES.get(v, v)]
        for group in columns:
            for key in group:
                row.append(cell(rec, key))
            if group == ("install_time",):
                row.append(success_cell(rec))
        rows.append(row)
    return md_table(header, rows)


def pooled(plats):
    """Pool all platforms into one variant map (Table 7.5 default)."""
    out = {}
    for variants_map in plats.values():
        for v, rec in variants_map.items():
            if v not in out:
                out[v] = json.loads(json.dumps(rec))
            else:
                out[v]["runs"].extend(rec["runs"])
                if rec.get("absent") and not out[v].get("absent"):
                    out[v]["absent"] = rec["absent"]
    return out


def build_markdown(plats, synthetic, table75_platform=None):
    lines = ["# Bench Notes benchmark summary", ""]
    if synthetic:
        lines += ["> **SYNTHETIC DATA.** These numbers were generated by bench/tests/synthetic.py to exercise the "
                  "report; they say nothing about any framework.", ""]
    lines += ["Cells are medians with the interquartile range in brackets (Q1-Q3); a bare number means a single "
              "measurement. See docs/method.md for how each number is produced and how noisy it is.", ""]
    if table75_platform:
        src = {table75_platform: plats[table75_platform]}
        scope = table75_platform
    else:
        src = plats
        scope = "all platforms pooled: " + ", ".join(sorted(plats))
    lines += ["## Table 7.5 - summary (%s)" % scope, "", table_for(pooled(src), TABLE_75), ""]
    if not table75_platform and len(plats) > 1:
        lines += ["*Pooling across operating systems mixes different web views and file systems; use the per-platform "
                  "tables below for any claim, or pass --table75-platform.*", ""]
    for label in sorted(plats):
        vm = plats[label]
        nruns = sum(len(r["runs"]) for r in vm.values())
        lines += ["## %s" % label, "", "%d variants, %d runs in total." % (len(vm), nruns), "",
                  table_for(vm, TABLE_75), ""]
        tool = ["- %s %s: %s" % (TITLES.get(v, v), vm[v]["version"],
                                 ", ".join("%s %s" % kv for kv in vm[v].get("toolchain", {}).items()) or "no toolchain recorded")
                for v in ordered(vm)]
        lines += ["Toolchain versions:", ""] + tool + [""]
    return "\n".join(lines)


def write_csv(plats, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["platform", "variant", "metric", "unit", "n", "median", "q1", "q3", "min", "max"])
        for label in sorted(plats):
            for v in ordered(plats[label]):
                rec = plats[label][v]
                for key, _lbl, unit, div, fn in METRICS:
                    st = stats(fn(rec))
                    if st:
                        w.writerow([label, v, key, unit, st["n"]] + ["%.4f" % (st[k] / div) for k in ("median", "q1", "q3", "min", "max")])
                ok, total = success_rate(rec)
                w.writerow([label, v, "install_success", "runs", total, ok[0], "", "", "", ""])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--out", default="results/summary.md")
    ap.add_argument("--csv", help="CSV path (default: next to --out)")
    ap.add_argument("--table75-platform", help="restrict Table 7.5 to one platform label, e.g. 'macOS arm64'")
    args = ap.parse_args(argv)
    plats, synthetic = load(args.results)
    if not plats:
        sys.exit("no results found")
    if args.table75_platform and args.table75_platform not in plats:
        sys.exit("platform %r not in results: %s" % (args.table75_platform, ", ".join(sorted(plats))))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_markdown(plats, synthetic, args.table75_platform))
    csv_path = Path(args.csv) if args.csv else out.with_suffix(".csv")
    write_csv(plats, csv_path)
    print("wrote %s and %s" % (out, csv_path))


if __name__ == "__main__":
    main()
