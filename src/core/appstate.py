"""Single source of truth for state.json - the small, durable prefs file the
launcher and app share. Lives in data_dir() (outside the app bundle), so its
contents survive both restarts and app auto-updates.

Mirrors launcher.py data_dir(); same process env, so it resolves to the same
file the launcher reads/writes. merge() only touches the keys it's given, so the
app and launcher can each own their own keys without clobbering the other's.
"""

import json
import os
import sys
from pathlib import Path


def state_file() -> Path:
    app = "Stemchotic"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / app / "Data" / "state.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app / "state.json"
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "stemchotic" / "state.json"


def read(path: Path | None = None) -> dict:
    try:
        return json.loads(Path(path or state_file()).read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def merge(updates: dict, path: Path | None = None) -> None:
    path = Path(path or state_file())
    state = read(path)
    state.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))
