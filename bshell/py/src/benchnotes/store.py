"""Note storage: one JSON file in a per-user data directory."""
import json
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path

MAX_TITLE = 200
MAX_BODY = 100_000
_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def data_dir(variant, env=None, platform=None):
    """Directory holding notes.json for a variant. BENCH_DATA_DIR wins."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    override = env.get("BENCH_DATA_DIR")
    if override:
        return Path(override)
    home = Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    if platform == "darwin":
        base = home / "Library" / "Application Support" / "BenchNotes"
    elif platform == "win32":
        local = env.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        base = Path(local) / "BenchNotes"
    else:
        xdg = env.get("XDG_DATA_HOME") or str(home / ".local" / "share")
        base = Path(xdg) / "BenchNotes"
    return base / variant


class NoteStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "notes.json"
        self._lock = threading.Lock()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            notes = data.get("notes", [])
            return notes if isinstance(notes, list) else []
        except FileNotFoundError:
            return []
        except (ValueError, OSError):
            # Corrupt file: keep it for inspection and start empty.
            try:
                os.replace(self.path, self.path.with_suffix(".corrupt"))
            except OSError:
                pass
            return []

    def _write(self, notes):
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"notes": notes}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def list(self):
        with self._lock:
            return self._load()

    def save(self, note):
        if not isinstance(note, dict):
            raise ValueError("note must be an object")
        title = note.get("title", "")
        body = note.get("body", "")
        if not isinstance(title, str) or not isinstance(body, str):
            raise ValueError("title and body must be strings")
        if len(title) > MAX_TITLE or len(body) > MAX_BODY:
            raise ValueError("note too large")
        nid = note.get("id")
        if nid is not None and not (isinstance(nid, str) and _ID_RE.match(nid)):
            raise ValueError("bad id")
        with self._lock:
            notes = self._load()
            nid = nid or uuid.uuid4().hex
            saved = {"id": nid, "title": title, "body": body, "updated": int(time.time() * 1000)}
            for i, n in enumerate(notes):
                if n.get("id") == nid:
                    notes[i] = saved
                    break
            else:
                notes.append(saved)
            self._write(notes)
            return saved

    def remove(self, nid):
        with self._lock:
            notes = self._load()
            kept = [n for n in notes if n.get("id") != nid]
            if len(kept) == len(notes):
                return False
            self._write(kept)
            return True
