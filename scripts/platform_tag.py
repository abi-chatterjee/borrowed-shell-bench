#!/usr/bin/env python3
"""Print '<os>-<arch>' (macos|windows|linux, arm64|x64) for the current machine."""
import platform
import sys


def tag():
    system = {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64" if machine in ("x86_64", "amd64") else machine
    return "%s-%s" % (system, arch)


if __name__ == "__main__":
    print(tag())
