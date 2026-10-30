"""Windows prerequisites for pywebview's WebView2 backend.

pywebview's Windows backend needs the WebView2 runtime and .NET Framework
4.7.2 or later. Check both registry keys before importing the backend so the
user gets one actionable sentence instead of a stack trace."""
import sys

WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
NET472_RELEASE = 461808  # Release value for .NET Framework 4.7.2
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
NET_URL = "https://dotnet.microsoft.com/download/dotnet-framework"


def _read(winreg, hive, key, name, view=0):
    try:
        with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def webview2_version(winreg):
    key = r"SOFTWARE\Microsoft\EdgeUpdate\Clients" + "\\" + WEBVIEW2_GUID
    wow = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients" + "\\" + WEBVIEW2_GUID
    for hive, k in ((winreg.HKEY_LOCAL_MACHINE, wow), (winreg.HKEY_LOCAL_MACHINE, key),
                    (winreg.HKEY_CURRENT_USER, key)):
        v = _read(winreg, hive, k, "pv")
        if v and v != "0.0.0.0":
            return v
    return None


def dotnet_release(winreg):
    v = _read(winreg, winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full", "Release")
    return v if isinstance(v, int) else None


def problems(winreg=None):
    """Return a list of actionable sentences; empty means OK."""
    if winreg is None:
        import winreg  # only exists on Windows
    out = []
    if webview2_version(winreg) is None:
        out.append("The Microsoft Edge WebView2 Runtime is not installed. "
                   "Install it from " + WEBVIEW2_URL + " and start Bench Notes again.")
    rel = dotnet_release(winreg)
    if rel is None or rel < NET472_RELEASE:
        out.append(".NET Framework 4.7.2 or later is required. Install it from " + NET_URL
                   + " and start Bench Notes again.")
    return out


def show_message_box(text, title="Bench Notes"):
    """Best effort native message box (pythonw has no console)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        pass
