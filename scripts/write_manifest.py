#!/usr/bin/env python3
"""Write dist/<platform>/<variant>/manifest.json, the contract with bench/run.py.

usage:
  write_manifest.py --dir DIR --variant V --version X --kind zip --artifact FILE
                    --launch-kind app|exe --launch-path REL [--tool NAME=VERSION ...]
  write_manifest.py --dir DIR --variant V --version X --kind installer
                    --artifact install.sh --artifact foo.whl --installer install.sh
                    --update-artifact new.whl [--tool NAME=VERSION ...]
Files named by --artifact/--update-artifact must already exist in DIR."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_frontend  # noqa: E402
import platform_tag  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--kind", choices=["zip", "installer"], required=True)
    ap.add_argument("--artifact", action="append", default=[])
    ap.add_argument("--update-artifact", action="append", default=[])
    ap.add_argument("--launch-kind", choices=["app", "exe"])
    ap.add_argument("--launch-path")
    ap.add_argument("--installer")
    ap.add_argument("--tool", action="append", default=[])
    a = ap.parse_args()
    d = Path(a.dir)
    for name in a.artifact + a.update_artifact:
        if not (d / name).is_file():
            sys.exit("missing artifact: %s" % (d / name))
    m = {
        "variant": a.variant,
        "version": a.version,
        "platform": platform_tag.tag(),
        "kind": a.kind,
        "artifacts": {n: (d / n).stat().st_size for n in a.artifact},
        "frontend_sha256": check_frontend.shared_hash(check_frontend.SRC),
        "toolchain": dict(t.split("=", 1) for t in a.tool),
    }
    if a.kind == "zip":
        m["launch"] = {"kind": a.launch_kind, "path": a.launch_path}
    else:
        m["installer"] = a.installer
        m["update_artifacts"] = {n: (d / n).stat().st_size for n in a.update_artifact}
    (d / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")
    print(d / "manifest.json")


if __name__ == "__main__":
    main()
