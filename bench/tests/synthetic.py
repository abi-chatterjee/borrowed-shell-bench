#!/usr/bin/env python3
"""Generate SYNTHETIC results files (random numbers, fixed seed) to exercise bench/report.py.
Every file is flagged host.synthetic = true and the report prints a banner. The numbers
mean nothing.

usage: synthetic.py OUT_DIR"""
import json
import random
import sys
from pathlib import Path

VARIANTS = ["electron", "tauri", "wails", "neutralino", "pyinstaller", "bshell-py", "bshell-node"]
MB = 1024 * 1024
HOSTS = [
    {"name": "synthetic-mac-arm", "os": "macos", "arch": "arm64", "os_version": "macOS-15.0-arm64"},
    {"name": "synthetic-mac-intel", "os": "macos", "arch": "x86_64", "os_version": "macOS-14.7-x86_64"},
    {"name": "synthetic-win11", "os": "windows", "arch": "AMD64", "os_version": "Windows-10-10.0.22631-SP0"},
    {"name": "synthetic-win10", "os": "windows", "arch": "AMD64", "os_version": "Windows-10-10.0.19045-SP0"},
]


def jitter(rng, base, pct=0.08):
    return base * (1 + rng.uniform(-pct, pct))


def variant_record(rng, v, runs):
    installer = v.startswith("bshell")
    art = {"electron": 120, "tauri": 6, "wails": 9, "neutralino": 1.2, "pyinstaller": 14, "bshell-py": 0.03, "bshell-node": 0.02}[v] * MB
    rec = {"version": "1.0.0", "kind": "installer" if installer else "zip", "toolchain": {"example": "0.0"},
           "frontend_sha256": "0" * 64, "artifact_bytes": int(art), "artifacts": {"artifact": int(art)}, "runs": [], "absent": None}
    if installer:
        rec["absent"] = {"ok": True, "net_bytes": int(jitter(rng, 60 * MB)), "disk_first_app_bytes": int(jitter(rng, 150 * MB)),
                         "disk_marginal_app_bytes": int(jitter(rng, 25 * MB)), "install_s": jitter(rng, 40)}
    for i in range(1, runs + 1):
        run = {"run": i, "errors": [], "install_ok": True, "ready_ok": True, "success": rng.random() > 0.05,
               "install_s": jitter(rng, 25 if installer else 1.5, 0.3),
               "disk_install_bytes": int(jitter(rng, art * (1 if not installer else 800))),
               "first_launch_ms": jitter(rng, 1500 if installer else 700, 0.25),
               "second_launch_ms": jitter(rng, 900 if installer else 500, 0.25),
               "idle_rss_bytes": int(jitter(rng, {"electron": 260, "tauri": 90, "wails": 95, "neutralino": 85}.get(v, 150) * MB, 0.1)),
               "idle_uss_bytes": None, "idle_footprint_bytes": int(jitter(rng, 120 * MB, 0.1)) if rng.random() > 0.5 else None,
               "leftover_procs": 0}
        if installer:
            run["fetched_logged"] = {"pip": int(jitter(rng, 8 * MB))}
            run["update_artifact_bytes"], run["update_net_bytes"] = int(art), 0
            run["update_s"], run["update_ok"] = jitter(rng, 3, 0.3), True
        else:
            run["update_artifact_bytes"], run["update_net_bytes"] = int(art), None
            run["update_s"], run["update_ok"] = jitter(rng, 1.5, 0.3), True
        rec["runs"].append(run)
    return rec


def main(out_dir, runs=10):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    for h in HOSTS:
        data = {"schema": 1, "host": dict(h, synthetic=True, ram_bytes=16 * 1024 ** 3, cpu_count=8, python="3.12.0", date="2000-01-01"),
                "settings": {"runs": runs}, "variants": {v: variant_record(rng, v, runs) for v in VARIANTS}, "skipped": []}
        (out / (h["name"] + ".json")).write_text(json.dumps(data, indent=1))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(main(sys.argv[1]))
