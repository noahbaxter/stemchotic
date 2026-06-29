"""CPU/GPU compute toggle.

The GPU env (cu128 torch + onnxruntime-gpu) runs both modes; audio-separator
picks GPU whenever torch.cuda.is_available(), so the only lever is the
CUDA_VISIBLE_DEVICES env var ("" hides the GPU, leaving CPU). torch reads it at
first CUDA init, so flipping device means re-exec'ing the process - but the env
is already built, so that re-exec is instant (no reinstall, no second venv).

This lives entirely in the app bundle: the frozen launcher is never touched, so
the toggle works for every user regardless of their launcher version.
"""

import os
import sys
from pathlib import Path

from . import appstate

VISIBLE = "CUDA_VISIBLE_DEVICES"
SENTINEL = "STEMCHOTIC_DEVICE_APPLIED"   # guards against a startup re-exec loop


# --- pure helpers (unit-tested without torch/GPU) ---

def target_visible(pref: str):
    """The CUDA_VISIBLE_DEVICES value a preference wants. "" masks the GPU for
    CPU mode; None means leave it untouched (GPU mode)."""
    return "" if pref == "cpu" else None


def needs_reexec(pref: str, current_visible, already_applied: bool) -> bool:
    """Whether startup must re-exec to honor `pref`. `current_visible` is the
    raw CUDA_VISIBLE_DEVICES (None if unset). Always False once the sentinel is
    set, so the re-exec'd child never bounces again."""
    if already_applied:
        return False
    if pref == "cpu":
        return current_visible != ""        # mask it unless already masked
    return current_visible == ""            # gpu: only act to unmask


# --- pref persistence ---

def read_device_pref(path: Path | None = None) -> str:
    pref = appstate.read(path).get("device")
    return pref if pref in ("gpu", "cpu") else "gpu"


def write_device_pref(pref: str, path: Path | None = None) -> None:
    appstate.merge({"device": pref}, path)


def gpu_toggle_available(path: Path | None = None) -> bool:
    """The toggle only makes sense when the GPU env is installed."""
    return appstate.read(path).get("hardware") == "gpu"


# --- the impure edges: re-exec into the same python with device masking set ---

def _reexec(pref: str) -> None:
    env = os.environ.copy()
    tv = target_visible(pref)
    if tv is None:
        env.pop(VISIBLE, None)
    else:
        env[VISIBLE] = tv
    env[SENTINEL] = "1"
    os.execve(sys.executable, [sys.executable, *sys.argv], env)


def apply_pref_at_startup() -> None:
    """Call before torch is imported. Re-execs once if the saved pref needs a
    different CUDA masking than the current process has. No-op in GPU default."""
    if os.environ.get(SENTINEL):
        return
    if not gpu_toggle_available():      # cpu/dml installs have nothing to mask
        return
    pref = read_device_pref()
    if needs_reexec(pref, os.environ.get(VISIBLE), already_applied=False):
        _reexec(pref)   # does not return


def switch_device(new_pref: str) -> None:
    """Persist the new pref and re-exec immediately so torch picks it up."""
    write_device_pref(new_pref)
    _reexec(new_pref)   # does not return
