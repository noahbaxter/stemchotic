"""CPU/GPU compute toggle.

The GPU env (cu128 torch + onnxruntime-gpu) runs both modes; audio-separator
picks GPU whenever torch.cuda.is_available(), so the only lever is the
CUDA_VISIBLE_DEVICES env var ("" hides the GPU, leaving CPU). torch reads it at
first CUDA init, so at startup (before torch is imported) setting it in-process
is enough. Flipping device mid-session means restarting the process, but the
env is already built, so that restart is instant (no reinstall, no second venv).

This lives entirely in the app bundle: the frozen launcher is never touched, so
the toggle works for every user regardless of their launcher version.
"""

import os
import subprocess
import sys
from pathlib import Path

from . import appstate

VISIBLE = "CUDA_VISIBLE_DEVICES"


# --- pure helper (unit-tested without torch/GPU) ---

def apply_to_env(pref: str, env) -> None:
    """Set CUDA masking in `env` for `pref`. CPU masks the GPU with ""; GPU only
    acts to undo a "" mask, leaving any other value (e.g. "0") alone."""
    if pref == "cpu":
        env[VISIBLE] = ""
    elif env.get(VISIBLE) == "":
        del env[VISIBLE]


# --- pref persistence ---

def read_device_pref(path: Path | None = None) -> str:
    pref = appstate.read(path).get("device")
    return pref if pref in ("gpu", "cpu") else "gpu"


def write_device_pref(pref: str, path: Path | None = None) -> None:
    appstate.merge({"device": pref}, path)


def gpu_toggle_available(path: Path | None = None) -> bool:
    """The toggle only makes sense when the GPU env is installed."""
    return appstate.read(path).get("hardware") == "gpu"


# --- the impure edges ---

def apply_pref_at_startup() -> None:
    """Call before torch is imported. Applies the saved pref to this process's
    env directly; no restart, so a bad pref can never keep the app from opening."""
    if not gpu_toggle_available():      # cpu/dml installs have nothing to mask
        return
    apply_to_env(read_device_pref(), os.environ)


def _restart(pref: str) -> None:
    env = os.environ.copy()
    apply_to_env(pref, env)
    argv = [sys.executable, *sys.argv]
    sys.stdout.flush()
    if sys.platform == "win32":
        # Windows has no real exec: os.execve spawns a new process and exits this
        # one, so the launcher (and the terminal window) think the app quit.
        # Run the new app as a child and pass its exit code through instead.
        sys.exit(subprocess.run(argv, env=env).returncode)
    os.execve(sys.executable, argv, env)


def switch_device(new_pref: str) -> None:
    """Persist the new pref and restart immediately so torch picks it up."""
    write_device_pref(new_pref)
    _restart(new_pref)   # does not return
