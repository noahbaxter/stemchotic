"""Picker prefs that survive close/reopen, stored in the shared state.json.

Persisted: the output settings, per-stem custom model overrides ("I always want
this model for bass"), kit_source, and the current stem selection. Deliberately
NOT persisted: one_pass - a temporary "run everything through this one model"
override for a single job, not a lasting preference.

selected and kit_source must persist TOGETHER: "Drum stem" mode (kit_source=
"stem") disables the whole left pane, and the only way back to "song" mode is
the Source toggle, which only renders when "Drums" is selected. The invariant
kit_source=="stem" => "Drums" in selected always holds during a session (Source
can only be set to "stem" once Drums is selected, and stem_picker.py's
on_left_enter refuses to change selection at all while kit_source=="stem"), so
persisting both together carries that invariant across a restart - a restored
"Drum stem" session always has its escape hatch (the Source toggle) visible.
Persisting kit_source WITHOUT selected broke this (a past lockout bug): a
restored kit_source="stem" landed with selected freshly empty, hiding the only
way out.
"""

from . import appstate

_KEYS = ("output_format", "quality", "keep_all", "residual",
         "kit_split", "kit_source", "models", "selected")


def load(path=None) -> dict:
    state = appstate.read(path)
    result = {k: state[k] for k in _KEYS if k in state}
    if "selected" in result:
        result["selected"] = set(result["selected"])
    # Self-heal a violated invariant: a state.json from the pre-fix 0.9.4 build
    # persisted kit_source alone (no selected at all), which reproduces the
    # lockout on upgrade unless we drop it here.
    if result.get("kit_source") == "stem" and "Drums" not in result.get("selected", ()):
        result.pop("kit_source", None)
    return result


def save(picker_state: dict, path=None) -> None:
    updates = {k: picker_state[k] for k in _KEYS if k in picker_state}
    if "selected" in updates:
        updates["selected"] = sorted(updates["selected"])   # set -> JSON-safe list
    appstate.merge(updates, path)
