"""ffmpeg validation: a name on PATH is not proof the binary works.

Regression cover for a user report of every split dying instantly with
"list index out of range". audio-separator's check_ffmpeg_installed reads
splitlines()[0] of `ffmpeg -version` output and only catches FileNotFoundError,
so an ffmpeg that resolves, exits 0 and prints nothing takes the whole run down
before any audio is read.

Verified on a Windows 11 VM with a compiled silent ffmpeg.exe first on PATH (a
stand-in for a Microsoft Store app-execution-alias): audio-separator's check
raises the reported IndexError, and ensure_ffmpeg falls back to static-ffmpeg so
the same check then passes. A .bat cannot stand in for that case, because
CreateProcess will not launch one and audio-separator reports the resulting
FileNotFoundError cleanly instead.
"""

import io
import os
import stat
import subprocess
import sys
import wave

import pytest

from src.core import separator


WIN = sys.platform == "win32"
MARKER = "stub-is-live"

# Stub bodies keyed by the failure they reproduce, per platform. "marker" is not
# a failure: it proves the stub is the binary being resolved, so a stub the
# platform never reaches can't make the real assertions pass for the wrong
# reason. Windows matters most here, since the reported break was a Store
# app-execution-alias.
STUBS = {
    "silent": {
        # Store alias / dead scoop shim: resolves, exits 0, prints nothing.
        "sh": '#!/bin/sh\nexit 0\n',
        "bat": '@echo off\r\nexit /b 0\r\n',
    },
    "liar": {
        # Prints a plausible banner but cannot do the work.
        "sh": ('#!/bin/sh\n'
               'if [ "$1" = "-version" ]; then echo "ffmpeg version 4.2.1"; exit 0; fi\n'
               'exit 1\n'),
        "bat": ('@echo off\r\n'
                'if "%~1"=="-version" (echo ffmpeg version 4.2.1 & exit /b 0)\r\n'
                'exit /b 1\r\n'),
    },
    "truncating": {
        # Decodes, but hands back a truncated stream.
        "sh": ('#!/bin/sh\n'
               'if [ "$1" = "-version" ]; then echo "ffmpeg version 4.2.1"; exit 0; fi\n'
               'printf 0123456789\nexit 0\n'),
        "bat": ('@echo off\r\n'
                'if "%~1"=="-version" (echo ffmpeg version 4.2.1 & exit /b 0)\r\n'
                'echo 0123456789\r\n'
                'exit /b 0\r\n'),
    },
    "marker": {
        "sh": f'#!/bin/sh\necho {MARKER}\nexit 0\n',
        "bat": f'@echo off\r\necho {MARKER}\r\nexit /b 0\r\n',
    },
}


def _stub_dir(tmp_path, name, tools=("ffmpeg", "ffprobe")):
    """A directory holding `tools` as the named stub, ready to prepend to PATH."""
    d = tmp_path / f"bin-{name}"
    d.mkdir(exist_ok=True)
    for tool in tools:
        p = d / (tool + ".bat" if WIN else tool)
        p.write_text(STUBS[name]["bat" if WIN else "sh"], newline="")
        if not WIN:
            p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return d


def _stubs_are_reachable(tmp_path) -> bool:
    """Whether a stub on PATH is what subprocess actually launches.

    On Windows a .bat is found by PATHEXT but CreateProcess does not always
    resolve it the way shutil.which does, so assert the plumbing works before
    trusting any PATH-based assertion."""
    env_path = os.pathsep.join([str(_stub_dir(tmp_path, "marker")),
                                os.environ.get("PATH", "")])
    old = os.environ.get("PATH", "")
    os.environ["PATH"] = env_path
    try:
        r = separator._run(["ffmpeg", "-version"], b"")
    finally:
        os.environ["PATH"] = old
    return r is not None and MARKER.encode() in (r.stdout or b"")


def _skip_unless_stubs_work(tmp_path):
    if not _stubs_are_reachable(tmp_path):
        # Expected on Windows: shutil.which finds a .bat, but CreateProcess
        # won't launch one, so subprocess raises FileNotFoundError. That path is
        # covered by test_works_is_false_when_no_ffmpeg_exists_at_all. The
        # silent-.exe case that actually broke the reporter needs a compiled
        # stub; it was verified by hand on a Windows VM (see the module
        # docstring) rather than faked here.
        pytest.skip("PATH stubs are not reachable via subprocess on this platform")


@pytest.fixture(autouse=True)
def _quiet_log():
    """_note dedupes against a module global; clear it so log assertions and
    ordering between tests stay independent."""
    separator._ffmpeg_last = None
    yield
    separator._ffmpeg_last = None


def _fake_static_ffmpeg(monkeypatch, add_paths):
    """Install a stand-in static_ffmpeg module with the given add_paths."""
    mod = type(sys)("static_ffmpeg")
    mod.add_paths = add_paths
    monkeypatch.setitem(sys.modules, "static_ffmpeg", mod)


def _real_ffmpeg() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


# --- the probe file itself ------------------------------------------------

def test_probe_wav_is_a_readable_stereo_wav():
    with wave.open(io.BytesIO(separator._probe_wav())) as w:
        assert w.getnchannels() == 2
        assert w.getsampwidth() == 2
        assert w.getframerate() == 44100
        assert w.getnframes() == separator._PROBE_FRAMES


# --- _works() against stub binaries on PATH -------------------------------

def test_the_stub_harness_itself_reaches_subprocess(tmp_path):
    """Guard for every PATH test below. If this skips, they are not proving
    anything on this platform and say so rather than passing quietly."""
    _skip_unless_stubs_work(tmp_path)


@pytest.mark.parametrize("stub", ["silent", "liar", "truncating"])
def test_works_rejects_broken_ffmpeg(tmp_path, monkeypatch, stub):
    _skip_unless_stubs_work(tmp_path)
    monkeypatch.setenv("PATH", str(_stub_dir(tmp_path, stub)), prepend=os.pathsep)
    assert separator._works() is False


def test_works_rejects_a_broken_ffprobe_even_when_ffmpeg_is_fine(tmp_path, monkeypatch):
    _skip_unless_stubs_work(tmp_path)
    if not _real_ffmpeg():
        pytest.skip("no working ffmpeg on PATH to pair with the stub")
    d = _stub_dir(tmp_path, "silent", tools=("ffprobe",))
    monkeypatch.setenv("PATH", str(d), prepend=os.pathsep)
    assert separator._works() is False


def test_works_accepts_a_real_ffmpeg():
    if not _real_ffmpeg():
        pytest.skip("no ffmpeg on PATH")
    assert separator._works() is True


def test_works_is_false_when_no_ffmpeg_exists_at_all(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert separator._works() is False


# --- ensure_ffmpeg() routing ----------------------------------------------

def test_ensure_ffmpeg_always_installs_our_own_copy(monkeypatch):
    """The policy: ours goes on PATH every time, so nothing the machine has can
    break a render."""
    monkeypatch.setattr(separator, "_works", lambda: True)
    calls = []
    _fake_static_ffmpeg(monkeypatch, lambda: calls.append(True))
    assert separator.ensure_ffmpeg() is True
    assert calls == [True], "did not install our own ffmpeg"


def test_ensure_ffmpeg_installs_ours_even_when_the_system_has_a_good_one(monkeypatch):
    """A working system ffmpeg must NOT win. Whatever it is, it's unknowable,
    and this is the regression that keeps the whole class of break fixed."""
    monkeypatch.setattr(separator, "_works", lambda: True)   # system is fine
    calls = []
    _fake_static_ffmpeg(monkeypatch, lambda: calls.append(True))
    separator.ensure_ffmpeg()
    assert calls == [True], "deferred to the system ffmpeg instead of using ours"


def test_ensure_ffmpeg_uses_the_system_one_only_when_ours_is_unavailable(monkeypatch):
    """Offline first run. Ours can't be fetched, so a decoding system ffmpeg is
    better than refusing to run."""
    monkeypatch.setattr(separator, "_works", lambda: True)

    def boom():
        raise RuntimeError("no network")

    _fake_static_ffmpeg(monkeypatch, boom)
    assert separator.ensure_ffmpeg() is True


def test_ensure_ffmpeg_reports_failure_when_ours_fails_and_the_system_is_broken(monkeypatch):
    monkeypatch.setattr(separator, "_works", lambda: False)

    def boom():
        raise RuntimeError("no network")

    _fake_static_ffmpeg(monkeypatch, boom)
    assert separator.ensure_ffmpeg() is False   # must not raise


def test_ensure_ffmpeg_reports_failure_when_our_own_copy_cant_decode(monkeypatch):
    monkeypatch.setattr(separator, "_works", lambda: False)
    _fake_static_ffmpeg(monkeypatch, lambda: None)
    assert separator.ensure_ffmpeg() is False


# --- self-repair: the verdict is never cached ------------------------------

def test_a_failed_fallback_retries_on_the_next_run(monkeypatch):
    """The offline-first-render case. A failure must not latch the session into
    a broken state; the next run tries again and can succeed."""
    attempts = []

    def add_paths():
        attempts.append(len(attempts))
        if len(attempts) == 1:
            raise RuntimeError("no network")

    monkeypatch.setattr(separator, "_works", lambda: len(attempts) >= 2)
    _fake_static_ffmpeg(monkeypatch, add_paths)

    assert separator.ensure_ffmpeg() is False, "first run should fail (offline)"
    assert separator.ensure_ffmpeg() is True, "second run should self-repair"


def test_our_copy_is_reinstalled_if_it_goes_missing_mid_session(monkeypatch):
    """Deleted side-folder, wiped cache, half-finished download. A later run
    re-probes and re-installs rather than trusting an earlier verdict."""
    installs = []
    ok = {"v": False}

    def add_paths():
        installs.append(True)
        ok["v"] = True

    monkeypatch.setattr(separator, "_works", lambda: ok["v"])
    _fake_static_ffmpeg(monkeypatch, add_paths)

    assert separator.ensure_ffmpeg() is True
    ok["v"] = False                         # our copy disappears
    assert separator.ensure_ffmpeg() is True
    assert len(installs) == 2, "did not re-install after our copy went missing"


def test_make_separator_reports_plainly_when_nothing_works(monkeypatch):
    """The last resort. Better a named cause than audio-separator's bare
    "list index out of range" from its own version check."""
    pytest.importorskip("audio_separator")   # checked before ffmpeg, so it wins
    monkeypatch.setattr(separator, "ensure_ffmpeg", lambda: False)
    with pytest.raises(RuntimeError, match="No working ffmpeg"):
        separator._make_separator()


def test_end_to_end_a_silent_ffmpeg_no_longer_reaches_audio_separator(tmp_path, monkeypatch):
    """The actual reported bug: with a silent ffmpeg first on PATH, the real
    static_ffmpeg fallback must leave a decoding ffmpeg in front of it."""
    _skip_unless_stubs_work(tmp_path)
    pytest.importorskip("static_ffmpeg")
    monkeypatch.setenv("PATH", str(_stub_dir(tmp_path, "silent")), prepend=os.pathsep)
    assert separator._works() is False, "stub should not pass the probe"
    separator.ensure_ffmpeg()
    assert separator._works() is True, "fallback did not produce a usable ffmpeg"
