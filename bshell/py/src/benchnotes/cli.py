import argparse
import sys

from ._version import __version__

DEFAULT_VARIANT = "bshell-py"


def build_parser():
    p = argparse.ArgumentParser(prog="benchnotes")
    sub = p.add_subparsers(dest="cmd", required=True)
    ui = sub.add_parser("ui", help="open the app window")
    ui.add_argument("--check", action="store_true", help="self-test and exit")
    ui.add_argument("--skip-backend", action="store_true",
                    help="with --check: skip importing the window backend (tests on machines without a GUI)")
    up = sub.add_parser("update", help="upgrade this install")
    up.add_argument("--wheel", help="path to a local wheel")
    sub.add_parser("version", help="print the version")
    sh = sub.add_parser("shell", help="native shell (macOS .app)")
    shsub = sh.add_subparsers(dest="shell_cmd", required=True)
    b = shsub.add_parser("build", help="build the .app and self-test it")
    b.add_argument("--apps-dir", required=True)
    b.add_argument("--skip-backend", action="store_true", help="test only: self-test without a window backend")
    return p


def main(argv=None, variant=DEFAULT_VARIANT):
    args = build_parser().parse_args(argv)
    if args.cmd == "version":
        print(__version__)
        return 0
    if args.cmd == "ui":
        from . import ui
        if args.check:
            try:
                ui.self_test(variant, skip_backend=args.skip_backend)
            except Exception as e:  # any failure is a failed self-test
                print("FAILED: %s: %s" % (type(e).__name__, e), file=sys.stderr)
                return 1
            return 0
        return ui.run(variant)
    if args.cmd == "update":
        from . import update
        code = update.update(wheel=args.wheel)
        if code == 0 and sys.platform == "darwin":
            from . import shell_macos
            shell_macos.build()  # default apps dir, or BENCHNOTES_APPS_DIR
        return code
    if args.cmd == "shell":
        from . import shell_macos
        try:
            path = shell_macos.build(args.apps_dir, skip_backend=args.skip_backend)
        except Exception as e:
            print("FAILED: %s: %s" % (type(e).__name__, e), file=sys.stderr)
            return 1
        print(path)
        return 0
    return 2
