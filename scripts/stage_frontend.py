#!/usr/bin/env python3
"""Copy the shared frontend into DEST for one variant.

Every non-adapter file is copied byte for byte. Of frontend/api/*.js only the
variant's transport adapter is copied, and it is renamed to api/adapter.js
(index.html loads that fixed name). The result is verified with
check_frontend.check_dir before returning.

usage: stage_frontend.py VARIANT DEST
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_frontend  # noqa: E402


def transport_of(variant):
    return json.loads((ROOT / "variants" / "variants.json").read_text())[variant]["transport"]


def stage(variant, dest):
    dest = Path(dest)
    src = ROOT / "frontend"
    if dest.exists():
        shutil.rmtree(dest)
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if p.is_dir() or rel.parts[0] == "api":
            continue
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest / rel)
    (dest / "api").mkdir(exist_ok=True)
    shutil.copyfile(src / "api" / (transport_of(variant) + ".js"), dest / "api" / "adapter.js")
    check_frontend.check_dir(dest, transport_of(variant))
    return dest


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(stage(sys.argv[1], sys.argv[2]))
