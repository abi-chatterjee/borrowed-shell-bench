"""What the harness needs to know about each variant: manifests, installer profiles,
launch targets and log parsing."""
import json
import os
import re
from pathlib import Path

# Installer-kind variants. Zip-kind variants need no profile: the manifest says what to launch.
#   env_*       environment variables the installer reads
#   app_name    name of the .app / .lnk the installer creates
#   runtime_dirs  directories under the install home that hold the language runtime
PROFILES = {
    "bshell-py": {
        "env_home": "BENCHNOTES_HOME", "env_apps": "BENCHNOTES_APPS_DIR", "env_artifact": "BENCHNOTES_WHEEL",
        "artifact_suffix": ".whl", "app_name": "Bench Notes (bshell-py)", "runtime_dirs": ["python", "uv"],
    },
    "bshell-node": {
        "env_home": "BENCHNOTES_HOME", "env_apps": "BENCHNOTES_APPS_DIR", "env_artifact": "BENCHNOTES_TARBALL",
        "artifact_suffix": ".tgz", "app_name": "Bench Notes (bshell-node)", "runtime_dirs": ["node"],
    },
    # Test double used by bench/tests (see bench/tests/fake_app).
    "fake-installer": {
        "env_home": "BENCHNOTES_HOME", "env_apps": "BENCHNOTES_APPS_DIR", "env_artifact": "BENCHNOTES_WHEEL",
        "artifact_suffix": ".whl", "app_name": "Fake Installer App", "runtime_dirs": ["runtime"],
    },
}

ORDER = ["electron", "tauri", "wails", "neutralino", "pyinstaller", "bshell-py", "bshell-node"]


def load_manifest(dist_root, variant):
    path = Path(dist_root) / variant / "manifest.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def available(dist_root):
    out = []
    for d in sorted(Path(dist_root).iterdir()) if Path(dist_root).is_dir() else []:
        if (d / "manifest.json").is_file():
            out.append(d.name)
    return sorted(out, key=lambda v: (ORDER.index(v) if v in ORDER else 99, v))


def select(dist_root, spec):
    have = available(dist_root)
    if spec == "all":
        return have, []
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    return [v for v in wanted if v in have], [v for v in wanted if v not in have]


_FETCHED_LOOSE = re.compile(r"^fetched: (.+?) (\d+) bytes", re.M)


def parse_install_log(text):
    """Pull the machine-readable lines out of an installer's log."""
    info = {"fetched": {}, "runtime_downloaded": None, "install_seconds": None,
            "interpreter": None, "cli": None, "launch": None}
    for m in _FETCHED_LOOSE.finditer(text):
        name = m.group(1).split(" ")[0]
        info["fetched"][name] = info["fetched"].get(name, 0) + int(m.group(2))
    for key in ("runtime_downloaded", "install_seconds", "interpreter", "cli", "launch"):
        m = re.search(r"^%s: (.+)$" % key, text, re.M)
        if m:
            info[key] = m.group(1).strip()
    if info["runtime_downloaded"] is not None:
        info["runtime_downloaded"] = info["runtime_downloaded"] == "yes"
    if info["install_seconds"] is not None:
        info["install_seconds"] = int(info["install_seconds"])
    return info


def find_runtime_bin(home, profile):
    """Directory holding the interpreter the installer provisioned under `home`, or None."""
    for sub in profile["runtime_dirs"]:
        base = Path(home) / sub
        if not base.is_dir():
            continue
        for root, _dirs, files in os.walk(base):
            for f in files:
                if f in ("python3.12", "python3", "python.exe", "node", "node.exe", "fakepy"):
                    p = Path(root) / f
                    if os.access(p, os.X_OK) or f.endswith(".exe"):
                        return str(root)
    return None


def installer_target(profile, apps_dir, platform, log_info):
    """How to launch what the installer built."""
    name = profile["app_name"]
    if platform == "macos":
        return {"kind": "app", "path": str(Path(apps_dir) / (name + ".app"))}
    if platform == "windows":
        return {"kind": "lnk", "path": str(Path(apps_dir) / (name + ".lnk"))}
    if not log_info.get("launch"):
        raise RuntimeError("installer log has no 'launch:' line (Linux test runs need it)")
    return {"kind": "cmd", "cmd": log_info["launch"].split()}


def update_command(variant, log_info, artifact_path):
    """argv that applies the update artifact to an existing install."""
    interp = log_info["interpreter"]
    if variant == "bshell-py":
        return [interp, "-m", "benchnotes", "update", "--wheel", str(artifact_path)]
    if variant == "bshell-node":
        return [interp, log_info["cli"], "update", "--tarball", str(artifact_path)]
    if variant == "fake-installer":
        return [interp, "update", str(artifact_path)]
    raise KeyError(variant)


def version_command(variant, log_info):
    interp = log_info["interpreter"]
    if variant == "bshell-py":
        return [interp, "-m", "benchnotes", "version"]
    if variant == "bshell-node":
        return [interp, log_info["cli"], "version"]
    if variant == "fake-installer":
        return [interp, "version"]
    raise KeyError(variant)
