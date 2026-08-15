"""Stemchotic - an easy stem separation TUI on top of python-audio-separator."""

from pathlib import Path


def _version() -> str:
    """The release version, read from the .version file CI writes into app.zip.

    Deliberately not a literal in this file. The tag is the single source of truth:
    a hardcoded version here is a second place to bump, and the two drift the first
    time you forget. Source checkouts have no .version, hence "dev".
    """
    try:
        return (Path(__file__).resolve().parent.parent / ".version").read_text().strip() or "dev"
    except OSError:
        return "dev"


__version__ = _version()
