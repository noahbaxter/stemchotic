"""Fast, in-process integration test for the main picker.

Drives show_stem_picker through real key handling (the same getch loop the live
TUI uses) without a terminal or models, so it runs every time and deterministically.
The slow pty-driven real-separation test lives in test_e2e_separation.py.

Patches two seams: getch (feed scripted keys) and cbreak_noecho (it calls termios
on stdin, which has no tty under pytest). State/prefs are redirected to a temp file.
"""
import contextlib

import pytest

from chotic_ui.primitives import KEY_TAB, KEY_DOWN, KEY_SPACE, KEY_ESC
from src.core import appstate, device, prefs
from src.screens import stem_picker


def _script(keys):
    """A getch replacement that returns each scripted key in turn, then ESC
    (so an under-specified script quits the pane instead of hanging)."""
    it = iter(keys)

    def fake_getch(return_special_keys=True):
        return next(it, KEY_ESC)
    return fake_getch


@pytest.fixture
def picker(tmp_path, monkeypatch):
    """show_stem_picker wired to a temp state file, with the terminal seams stubbed.
    Returns a runner: drive(keys) -> the run-request dict (or None on quit)."""
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(appstate, "state_file", lambda: state_file)
    monkeypatch.setattr(stem_picker, "cbreak_noecho", contextlib.nullcontext, raising=False)
    # two_pane binds getch/cbreak_noecho into its own namespace at import.
    import chotic_ui.widgets.two_pane as tp
    monkeypatch.setattr(tp, "cbreak_noecho", contextlib.nullcontext)

    def drive(keys):
        monkeypatch.setattr(tp, "getch", _script(keys))
        return stem_picker.show_stem_picker(stem_picker.new_state())

    drive.state_file = state_file
    drive.monkeypatch = monkeypatch
    return drive


def test_format_cycles_on_spacebar(picker):
    # Tab into settings (cursor lands on Format), Space twice: WAV -> FLAC -> MP3,
    # then 's' to start. The returned run-request must reflect the keypresses.
    result = picker([KEY_TAB, KEY_SPACE, KEY_SPACE, "s"])
    assert result is not None
    assert result["output_format"] == "MP3"


def test_settings_persist_across_a_fresh_picker(picker):
    picker([KEY_TAB, KEY_SPACE, "s"])                  # WAV -> FLAC, then start
    assert prefs.load(picker.state_file)["output_format"] == "FLAC"
    # A brand-new session restores it.
    assert stem_picker.new_state()["output_format"] == "FLAC"


def test_compute_toggle_appears_and_fires_for_gpu_installs(picker):
    # Fake a GPU install so the Compute row shows, and capture the re-exec instead
    # of actually execing. Hardware can't test this; a faked tier can.
    calls = []
    picker.monkeypatch.setattr(device, "gpu_toggle_available", lambda *a: True)
    picker.monkeypatch.setattr(device, "read_device_pref", lambda *a: "gpu")
    picker.monkeypatch.setattr(device, "switch_device", lambda pref: calls.append(pref))

    # Tab to settings, Down past Format/Quality/Scope to the Compute row, Space it.
    picker([KEY_TAB, KEY_DOWN, KEY_DOWN, KEY_DOWN, KEY_SPACE, KEY_ESC])
    assert calls == ["cpu"], "Spacebar on Compute should switch GPU -> CPU"


def test_no_compute_row_without_a_gpu_install(picker):
    # Default tier (no gpu): toggling should never fire even if we land where the
    # row would be. read_device_pref/switch_device stay real; just assert no exec.
    calls = []
    picker.monkeypatch.setattr(device, "gpu_toggle_available", lambda *a: False)
    picker.monkeypatch.setattr(device, "switch_device", lambda pref: calls.append(pref))
    picker([KEY_TAB, KEY_DOWN, KEY_DOWN, KEY_DOWN, KEY_SPACE, KEY_ESC])
    assert calls == []
