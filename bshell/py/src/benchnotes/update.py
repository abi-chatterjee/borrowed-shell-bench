"""Update path: pip install --no-index --upgrade <wheel>, online as fallback."""
import subprocess
import sys

PIP = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"]


def update(wheel=None, spec="benchnotes", run=subprocess.run, out=print):
    if wheel:
        r = run(PIP + ["--no-index", "--upgrade", wheel])
        if r.returncode == 0:
            out("updated from local wheel (offline)")
            return 0
        out("offline install failed (exit %d); retrying with the package index" % r.returncode)
        r = run(PIP + ["--upgrade", wheel])
        return r.returncode
    r = run(PIP + ["--upgrade", spec])
    return r.returncode
