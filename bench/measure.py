"""Measurement primitives: disk size, process snapshots and memory, network bytes."""
import os
import shutil
import subprocess
import sys
import time

import psutil


# ---- disk -----------------------------------------------------------------------

def dir_bytes(path):
    """(apparent_bytes, allocated_bytes) of a file tree. Symlinks are counted as links
    (their own size), never followed, so a symlinked interpreter is not double counted.
    allocated = st_blocks * 512 where the OS reports it (POSIX), else equals apparent."""
    apparent = allocated = 0
    path = str(path)
    if not os.path.lexists(path):
        return 0, 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            st = os.lstat(cur)
        except OSError:
            continue
        apparent += st.st_size
        allocated += getattr(st, "st_blocks", None) * 512 if hasattr(st, "st_blocks") else st.st_size
        if os.path.isdir(cur) and not os.path.islink(cur):
            try:
                stack.extend(os.path.join(cur, n) for n in os.listdir(cur))
            except OSError:
                pass
    return apparent, allocated


# ---- processes ------------------------------------------------------------------

def snapshot():
    """Set of (pid, create_time) for every process visible now."""
    out = set()
    for p in psutil.process_iter(["pid", "create_time"]):
        try:
            out.add((p.info["pid"], p.info["create_time"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out


def new_processes(before, exclude_pids=()):
    """psutil.Process objects that did not exist in `before` (by pid + create_time)."""
    found = []
    for p in psutil.process_iter(["pid", "create_time", "name"]):
        try:
            key = (p.info["pid"], p.info["create_time"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if key not in before and p.info["pid"] not in exclude_pids:
            found.append(p)
    return found


def macos_footprint(pid):
    """Physical footprint in bytes from /usr/bin/footprint, or None."""
    if sys.platform != "darwin" or not shutil.which("footprint"):
        return None
    try:
        out = subprocess.run(["footprint", "-p", str(pid), "--noCategories"], capture_output=True, text=True, timeout=20).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    return parse_footprint(out)


_UNITS = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}


def parse_footprint(text):
    """Parse the 'Footprint: 12 MB' style total out of `footprint` output."""
    for line in text.splitlines():
        low = line.strip().lower()
        if "phys_footprint" in low or low.startswith("footprint:") or " footprint: " in low:
            parts = line.replace(",", "").split()
            for i, tok in enumerate(parts):
                try:
                    val = float(tok)
                except ValueError:
                    continue
                unit = parts[i + 1].upper() if i + 1 < len(parts) else "B"
                if unit in _UNITS:
                    return int(val * _UNITS[unit])
    return None


def memory_of(processes):
    """Sum memory over psutil.Process objects. Returns a dict with rss, uss (None if
    unreadable for any process), footprint (macOS only) and the process list."""
    rss = 0
    uss = 0
    uss_ok = True
    fp = 0
    fp_ok = sys.platform == "darwin"
    names = []
    for p in processes:
        try:
            rss += p.memory_info().rss
            names.append("%s[%d]" % (p.name(), p.pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        try:
            uss += p.memory_full_info().uss
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            uss_ok = False
        if fp_ok:
            v = macos_footprint(p.pid)
            if v is None:
                fp_ok = False
            else:
                fp += v
    return {
        "rss_bytes": rss,
        "uss_bytes": uss if uss_ok else None,
        "footprint_bytes": fp if fp_ok else None,
        "process_count": len(names),
        "processes": names,
    }


def stop_processes(procs, grace=5.0):
    """Terminate, wait, then kill. Returns the processes still alive afterwards."""
    for p in procs:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _gone, alive = psutil.wait_procs(procs, timeout=grace)
    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _gone, alive = psutil.wait_procs(alive, timeout=grace)
    return alive


def still_running(procs):
    """Subset of `procs` still alive (psutil compares create_time, so pid reuse is not a false hit)."""
    alive = []
    for p in procs:
        try:
            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                alive.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return alive


# ---- network ----------------------------------------------------------------------

def net_recv_bytes():
    """Total bytes received by all interfaces since boot (loopback excluded where named)."""
    total = 0
    for name, c in psutil.net_io_counters(pernic=True).items():
        if name.startswith("lo"):
            continue
        total += c.bytes_recv
    return total


# ---- quiet machine ----------------------------------------------------------------

def quiet_check(seconds=5, cpu_limit=15.0):
    """Sample total CPU for `seconds`. Returns (ok, cpu_percent, top_processes)."""
    for p in psutil.process_iter():
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    total = psutil.cpu_percent(interval=seconds)
    top = []
    for p in psutil.process_iter(["name", "pid"]):
        try:
            top.append((p.cpu_percent(None), p.info["name"], p.info["pid"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    top.sort(reverse=True)
    return total <= cpu_limit, total, top[:5]


def now_ms():
    return int(time.time() * 1000)
