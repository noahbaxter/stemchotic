"""Picker prefs that survive close/reopen, stored in the shared state.json.

Persisted: the output settings and per-stem custom model overrides ("I always
want this model for bass"). Deliberately NOT persisted: which stems are checked
(`selected`) and the one-pass override - those are picked fresh each session.
"""

from . import appstate

_KEYS = ("output_format", "quality", "keep_all", "residual",
         "kit_split", "kit_source", "models")


def load(path=None) -> dict:
    state = appstate.read(path)
    return {k: state[k] for k in _KEYS if k in state}


def save(picker_state: dict, path=None) -> None:
    appstate.merge({k: picker_state[k] for k in _KEYS if k in picker_state}, path)
