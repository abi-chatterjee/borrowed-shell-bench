#!/usr/bin/env python3
"""Benchmark driver. One machine, one results file.

  python bench/run.py --variants all --runs 10 --out results/<host>.json

Per variant, per run (see docs/method.md for the full method and its noise):
  install (timed) -> first launch (cold start) -> quit -> second launch (cold start)
  -> idle 60 s -> memory of every process that did not exist before the launch
  -> quit, verify nothing is left -> update (installer variants) and disk footprint.
Borrowed Shell variants also get one extra "runtime absent" pass that forces the installer
to provision its own Python/Node, which gives the runtime download size and the
first-app / marginal-app disk numbers."""
import argparse
import json
import os
import platform
import re
import shutil
import socket
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure  # noqa: E402
import platform_ops  # noqa: E402
import variants  # noqa: E402
import psutil  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = 1


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def host_info():
    return {
        "name": socket.gethostname(),
        "os": platform_ops.platform_name(),
        "os_version": platform.platform(),
        "arch": platform.machine(),
        "cpu_count": psutil.cpu_count(logical=True),
        "ram_bytes": psutil.virtual_memory().total,
        "python": platform.python_version(),
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def read_text(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


# ---- install ------------------------------------------------------------------------

def install(manifest, dist_dir, scratch, name, absent=False, extra_env=None, path_prepend=None, timeout=1800):
    """Install into scratch/name. Returns a dict (never raises for install failures)."""
    import subprocess
    variant = manifest["variant"]
    root = Path(scratch) / name
    root.mkdir(parents=True, exist_ok=True)
    res = {"ok": False, "seconds": None, "net_bytes": None, "target": None, "root": str(root), "log": "", "error": None}
    net0 = measure.net_recv_bytes()
    t0 = time.monotonic()
    try:
        if manifest["kind"] == "zip":
            zip_name = [n for n in manifest["artifacts"] if n.endswith(".zip")][0]
            platform_ops.extract_zip(Path(dist_dir) / zip_name, root)
            launch = manifest["launch"]
            path = root / launch["path"]
            res["target"] = {"kind": launch["kind"], "path": str(path)}
            res["seconds"] = time.monotonic() - t0
            res["ok"] = path.exists()
            if not res["ok"]:
                res["error"] = "launch target missing after extraction: %s" % path
        else:
            prof = variants.PROFILES[variant]
            home, apps = root / "home", root / "apps"
            artifact = [n for n in manifest["artifacts"] if n.endswith(prof["artifact_suffix"])][0]
            env = dict(os.environ, **{prof["env_home"]: str(home), prof["env_apps"]: str(apps),
                                      prof["env_artifact"]: str(Path(dist_dir) / artifact)})
            env.update(extra_env or {})
            if absent:
                env["BENCHNOTES_FORCE_RUNTIME_INSTALL"] = "1"
            if path_prepend:
                env["PATH"] = path_prepend + os.pathsep + env.get("PATH", "")
            cmd = platform_ops.installer_command(Path(dist_dir) / manifest["installer"])
            r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
            res["seconds"] = time.monotonic() - t0
            text = read_text(home / "logs" / "install.log") or (r.stdout + r.stderr)
            res["log"] = text
            res["log_info"] = variants.parse_install_log(text)
            res["home"], res["apps"] = str(home), str(apps)
            res["ok"] = r.returncode == 0
            if not res["ok"]:
                res["error"] = "installer exit %d: %s" % (r.returncode, (r.stdout + r.stderr)[-600:])
            else:
                res["target"] = variants.installer_target(prof, apps, platform_ops.platform_name(), res["log_info"])
    except Exception as e:  # report, do not abort the whole benchmark
        res["seconds"] = time.monotonic() - t0
        res["error"] = "%s: %s" % (type(e).__name__, e)
    res["net_bytes"] = measure.net_recv_bytes() - net0
    return res


# ---- launching ----------------------------------------------------------------------

def launch_once(target, scratch, idle_seconds, ready_timeout, take_memory):
    """Launch, wait for the ready file, optionally idle and measure memory, then quit.
    Returns a dict with cold_start_ms, ready_ok, memory (or None), leftover count."""
    ready_file = Path(scratch) / "ready.txt"
    data_dir = Path(scratch) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    ready_file.unlink(missing_ok=True)
    env = {"BENCH_READY_FILE": str(ready_file), "BENCH_DATA_DIR": str(data_dir)}
    out = {"ready_ok": False, "cold_start_ms": None, "memory": None, "leftover": 0, "error": None}
    before = measure.snapshot()
    own = {os.getpid()}
    t_ready = None
    with platform_ops.Launcher(env) as launcher:
        t0 = launcher.launch(target)
    deadline = time.monotonic() + ready_timeout
    while time.monotonic() < deadline:
        txt = read_text(ready_file).strip()
        if txt.isdigit():
            t_ready = int(txt)
            break
        time.sleep(0.02)
    procs = []
    try:
        if t_ready is None:
            out["error"] = "no ready file within %ds" % ready_timeout
        else:
            out["ready_ok"] = True
            out["cold_start_ms"] = t_ready - t0
            if take_memory:
                time.sleep(idle_seconds)
                procs = measure.new_processes(before, own)
                out["memory"] = measure.memory_of(procs)
    finally:
        procs = procs or measure.new_processes(before, own)
        measure.stop_processes(procs)
        time.sleep(0.5)
        out["leftover"] = len(measure.still_running(procs))
    return out


# ---- one variant --------------------------------------------------------------------

def run_variant(variant, manifest, dist_dir, args, scratch_root):
    rec = {"version": manifest["version"], "kind": manifest["kind"], "toolchain": manifest.get("toolchain", {}),
           "frontend_sha256": manifest.get("frontend_sha256"), "artifacts": manifest["artifacts"],
           "artifact_bytes": sum(manifest["artifacts"].values()), "runs": [], "absent": None}
    installer_kind = manifest["kind"] == "installer"

    if installer_kind and args.absent_runs:
        rec["absent"] = absent_pass(variant, manifest, dist_dir, args, scratch_root)

    for i in range(1, args.runs + 1):
        scratch = Path(scratch_root) / ("%s-run%d" % (variant, i))
        shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir(parents=True)
        run = {"run": i, "errors": []}
        try:
            log("%s run %d/%d: install" % (variant, i, args.runs))
            ins = install(manifest, dist_dir, scratch, "app", extra_env=args.install_env)
            run["install_ok"] = ins["ok"]
            run["install_s"] = ins["seconds"]
            run["install_net_bytes"] = ins["net_bytes"]
            if installer_kind:
                run["runtime_downloaded"] = (ins.get("log_info") or {}).get("runtime_downloaded")
                run["fetched_logged"] = (ins.get("log_info") or {}).get("fetched")
            a, b = measure.dir_bytes(ins["root"])
            run["disk_install_bytes"], run["disk_install_allocated_bytes"] = a, b
            if not ins["ok"]:
                run["errors"].append("install: " + str(ins["error"]))
                run["install_log_tail"] = ins.get("log", "")[-1500:]
                rec["runs"].append(run)
                continue
            log("%s run %d: first launch" % (variant, i))
            first = launch_once(ins["target"], scratch, args.idle_seconds, args.ready_timeout, take_memory=False)
            run["ready_ok"] = first["ready_ok"]
            run["first_launch_ms"] = first["cold_start_ms"]
            run["leftover_procs"] = first["leftover"]
            if first["error"]:
                run["errors"].append("first launch: " + first["error"])
            if first["ready_ok"]:
                log("%s run %d: second launch + %ds idle" % (variant, i, args.idle_seconds))
                second = launch_once(ins["target"], scratch, args.idle_seconds, args.ready_timeout, take_memory=True)
                run["second_launch_ms"] = second["cold_start_ms"]
                run["leftover_procs"] += second["leftover"]
                if second["error"]:
                    run["errors"].append("second launch: " + second["error"])
                if second["memory"]:
                    m = second["memory"]
                    run["idle_rss_bytes"] = m["rss_bytes"]
                    run["idle_uss_bytes"] = m["uss_bytes"]
                    run["idle_footprint_bytes"] = m["footprint_bytes"]
                    run["idle_process_count"] = m["process_count"]
                    run["idle_processes"] = m["processes"]
            run["success"] = bool(run["install_ok"] and run.get("ready_ok"))
            # update cost
            if installer_kind and manifest.get("update_artifacts"):
                run.update(update_cost(variant, manifest, dist_dir, ins))
            elif not installer_kind:
                run.update(replace_cost(manifest, dist_dir, scratch))
        except Exception as e:
            run["errors"].append("%s: %s" % (type(e).__name__, e))
            run["traceback"] = traceback.format_exc()[-1500:]
        finally:
            if not args.keep:
                shutil.rmtree(scratch, ignore_errors=True)
        rec["runs"].append(run)
    return rec


def update_cost(variant, manifest, dist_dir, ins):
    """Borrowed Shell: move the installed v1.0.0 to v1.0.1 with the package's own update command."""
    import subprocess
    out = {}
    name = sorted(manifest["update_artifacts"])[0]
    artifact = Path(dist_dir) / name
    cmd = variants.update_command(variant, ins["log_info"], artifact)
    net0 = measure.net_recv_bytes()
    t0 = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    out["update_s"] = time.monotonic() - t0
    out["update_net_bytes"] = measure.net_recv_bytes() - net0
    out["update_artifact_bytes"] = artifact.stat().st_size
    out["update_model"] = "package-update"
    ver = subprocess.run(variants.version_command(variant, ins["log_info"]), capture_output=True, text=True, timeout=120)
    expected = re.search(r"\d+\.\d+\.\d+", name).group(0)
    out["update_ok"] = r.returncode == 0 and ver.stdout.strip() == expected
    if not out["update_ok"]:
        out["update_error"] = "update exit %d; version now %r, expected %r; %s" % (
            r.returncode, ver.stdout.strip(), expected, (r.stdout + r.stderr)[-300:])
    return out


def replace_cost(manifest, dist_dir, scratch):
    """Packaged variants have no delta updater in the default configuration: the update is a
    full download of the new artifact and a replace of the installed copy."""
    zip_name = [n for n in manifest["artifacts"] if n.endswith(".zip")][0]
    dest = Path(scratch) / "update-target"
    t0 = time.monotonic()
    platform_ops.extract_zip(Path(dist_dir) / zip_name, dest)
    return {"update_s": time.monotonic() - t0, "update_net_bytes": None,
            "update_artifact_bytes": (Path(dist_dir) / zip_name).stat().st_size,
            "update_model": "full-replace", "update_ok": True}


def absent_pass(variant, manifest, dist_dir, args, scratch_root):
    """Force the installer to provision its own runtime; then a second app that shares it."""
    scratch = Path(scratch_root) / (variant + "-absent")
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    out = {"ok": False}
    try:
        log("%s: runtime-absent install (forced)" % variant)
        first = install(manifest, dist_dir, scratch, "first", absent=True, extra_env=args.install_env)
        out.update(install_s=first["seconds"], net_bytes=first["net_bytes"], error=first["error"])
        if not first["ok"]:
            return out
        info = first["log_info"]
        out["fetched_logged"] = info["fetched"]
        out["runtime_downloaded"] = info["runtime_downloaded"]
        app_a, app_b = measure.dir_bytes(first["target"]["path"]) if first["target"]["kind"] in ("app", "lnk") else (0, 0)
        home_a, home_b = measure.dir_bytes(first["home"])
        out["disk_first_app_bytes"] = home_a + app_a
        out["disk_first_app_allocated_bytes"] = home_b + app_b
        prof = variants.PROFILES[variant]
        runtime_bin = variants.find_runtime_bin(first["home"], prof)
        out["runtime_bin"] = runtime_bin
        if runtime_bin:
            log("%s: second app sharing the first app's runtime" % variant)
            second = install(manifest, dist_dir, scratch, "second", path_prepend=runtime_bin, extra_env=args.install_env)
            out["second_app_ok"] = second["ok"]
            if second["ok"]:
                reused = not (second["log_info"].get("runtime_downloaded"))
                out["second_app_shared_runtime"] = reused
                a, b = measure.dir_bytes(second["home"])
                sa, sb = measure.dir_bytes(second["target"]["path"]) if second["target"]["kind"] in ("app", "lnk") else (0, 0)
                out["disk_marginal_app_bytes"] = a + sa
                out["disk_marginal_app_allocated_bytes"] = b + sb
                out["second_install_net_bytes"] = second["net_bytes"]
            else:
                out["second_app_error"] = second["error"]
        out["ok"] = True
    except Exception as e:
        out["error"] = "%s: %s" % (type(e).__name__, e)
    finally:
        if not args.keep:
            shutil.rmtree(scratch, ignore_errors=True)
    return out


# ---- main ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", default="all", help="'all' or a comma separated list")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", required=True, help="results JSON path")
    ap.add_argument("--dist", help="dist directory (default dist/<os>-<arch>)")
    ap.add_argument("--idle-seconds", type=int, default=20)
    ap.add_argument("--ready-timeout", type=int, default=60)
    ap.add_argument("--absent-runs", type=int, default=1, help="runtime-absent passes for installer variants (0 = skip)")
    ap.add_argument("--scratch", help="scratch directory root (default: a temp dir)")
    ap.add_argument("--keep", action="store_true", help="keep scratch installs for inspection")
    ap.add_argument("--no-quiet-check", action="store_true", help="skip the idle-machine precheck")
    ap.add_argument("--smoke", action="store_true", help="CI smoke: 1 run, 2 s idle, no absent pass, no quiet check")
    ap.add_argument("--install-env", action="append", default=[], metavar="KEY=VALUE",
                    help="extra environment for installers (tests; e.g. BENCHNOTES_UV_INSTALLER_URL)")
    args = ap.parse_args(argv)
    args.install_env = dict(kv.split("=", 1) for kv in args.install_env)
    if args.smoke:
        args.runs, args.idle_seconds, args.absent_runs, args.no_quiet_check = 1, 2, 0, True

    sys.path.insert(0, str(ROOT / "scripts"))
    import platform_tag
    dist = Path(args.dist) if args.dist else ROOT / "dist" / platform_tag.tag()
    chosen, missing = variants.select(dist, args.variants)
    if missing:
        log("not built, skipped: " + ", ".join(missing))
    if not chosen:
        log("nothing to run in %s" % dist)
        return 2

    if not args.no_quiet_check:
        ok, cpu, top = measure.quiet_check()
        log("quiet check: total CPU %.1f%% %s" % (cpu, "(ok)" if ok else "(TOO BUSY)"))
        if not ok:
            log("top processes: " + ", ".join("%s[%d] %.0f%%" % (n, p, c) for c, n, p in top))
            log("Close other applications and retry, or pass --no-quiet-check (results will be noisy).")
            return 3

    results = {"schema": SCHEMA, "host": host_info(), "platform_tag": platform_tag.tag(),
               "settings": {"runs": args.runs, "idle_seconds": args.idle_seconds, "ready_timeout": args.ready_timeout,
                            "absent_runs": args.absent_runs},
               "variants": {}, "skipped": missing}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    scratch_root = Path(args.scratch) if args.scratch else Path(tempfile.mkdtemp(prefix="bench-"))
    scratch_root.mkdir(parents=True, exist_ok=True)
    try:
        for v in chosen:
            manifest = variants.load_manifest(dist, v)
            log("== %s %s" % (v, manifest["version"]))
            results["variants"][v] = run_variant(v, manifest, dist / v, args, scratch_root)
            out.write_text(json.dumps(results, indent=2))
    finally:
        if not args.keep and not args.scratch:
            shutil.rmtree(scratch_root, ignore_errors=True)
    log("wrote %s" % out)
    failed = [v for v, r in results["variants"].items() if not any(x.get("success") for x in r["runs"])]
    if failed:
        log("no successful run for: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
