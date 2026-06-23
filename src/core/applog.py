"""
Best-effort session logging for the packaged app, so a user who hits a problem
can send a file instead of copying the terminal.

Writes to the same Logs dir the launcher uses (computed here independently, so
no launcher cooperation is needed and it works with already-shipped launchers).
We mirror stderr to the log: Python already routes uncaught exceptions, the
"Exception ignored" GC noise, and thread crashes there, so teeing stderr
captures all of them without touching sys.excepthook. The interactive TUI
redraws (stdout) are deliberately NOT mirrored, to keep the log readable.

Everything here is best-effort: any failure leaves the app running normally.
"""

import os
import re
import sys
import time
from pathlib import Path

_APP_DIRNAME = "Stemchotic"
_KEEP_DAYS = 7
_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

_log_file = None


def log_dir() -> Path:
    """Same location the launcher logs to (Logs), computed independently."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / _APP_DIRNAME / "Logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / _APP_DIRNAME
    base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return base / "stemchotic"


def write(msg: str) -> None:
    """Append a timestamped line to the log (no-op until init() succeeds)."""
    if _log_file is None:
        return
    try:
        _log_file.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        _log_file.flush()
    except Exception:
        pass


class _Tee:
    """Mirror writes to the real stream and the log file. Used for stderr so
    warnings and tracebacks land in the log without disturbing the terminal.
    ANSI/carriage-returns are stripped on the file side to keep it readable."""

    def __init__(self, stream, fp):
        self._stream = stream
        self._fp = fp

    def write(self, s):
        try:
            self._stream.write(s)
        except Exception:
            pass
        try:
            self._fp.write(_ANSI.sub("", s).replace("\r", ""))
            self._fp.flush()
        except Exception:
            pass
        return len(s)

    def flush(self):
        for t in (self._stream, self._fp):
            try:
                t.flush()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _prune(d: Path) -> None:
    cutoff = time.time() - _KEEP_DAYS * 86400
    for p in d.glob("app-*.log"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def init(version: str = "") -> None:
    """Open today's log and mirror stderr into it. Idempotent and best-effort:
    failure leaves the app running normally."""
    global _log_file
    if _log_file is not None:
        return
    try:
        d = log_dir()
        d.mkdir(parents=True, exist_ok=True)
        _prune(d)
        _log_file = open(d / f"app-{time.strftime('%Y-%m-%d')}.log", "a",
                         encoding="utf-8", errors="replace")
    except Exception:
        _log_file = None
        return

    write("=" * 50)
    write(f"Session start: stemchotic {version}".rstrip())
    write(f"Platform: {sys.platform}  Python: {sys.version.split()[0]}")
    write(f"Args: {' '.join(sys.argv[1:]) or '(none)'}")

    sys.stderr = _Tee(sys.stderr, _log_file)
