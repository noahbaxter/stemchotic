"""
Nudge the user to re-download the launcher when it's older than the version this
app build expects.

The launcher is a frozen bootstrapper with no self-update, but app.zip *does*
auto-update, so it carries the latest known launcher version and surfaces a
notice when the installed launcher is behind. The launcher reports its own
version through the STEMCHOTIC_LAUNCHER_VERSION env var.
"""

import os

# Bump in lockstep with launcher.py's LAUNCHER_VERSION whenever the launcher
# (or its bundled WezTerm / wezterm.lua) changes and users should re-download.
LATEST_LAUNCHER = "1.1"
RELEASES_URL = "https://github.com/noahbaxter/stemchotic/releases/latest"


def _parse(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return ()


def launcher_outdated() -> bool:
    """True when the running launcher reports a version older than
    LATEST_LAUNCHER. False when up to date, or unknown (dev runs and older
    launchers that predate the notifier and don't set the env var)."""
    running = _parse(os.environ.get("STEMCHOTIC_LAUNCHER_VERSION", ""))
    return bool(running) and running < _parse(LATEST_LAUNCHER)
