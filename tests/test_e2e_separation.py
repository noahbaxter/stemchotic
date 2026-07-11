"""End-to-end render test: actually separate a short clip and assert stem files
appear. Slow (downloads a model the first time, runs inference on CPU), so it's
opt-in: set STEMCHOTIC_E2E=1 and have the built app env present.

This drives the headless CLI (`stemchotic.py --stems ... -y`), which runs the
exact same do_run -> separator.run engine the TUI triggers on Start. The picker's
key handling is covered separately and deterministically by test_picker_flow.py;
this layer's job is to prove the render path writes real files given real settings.
"""
import math
import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent


def _env_python() -> Path | None:
    """The built app env's python (has torch + audio_separator); None if absent."""
    p = Path.home() / "Library" / "Caches" / "Stemchotic" / "_env" / "bin" / "python"
    return p if p.exists() else None


pytestmark = pytest.mark.skipif(
    os.environ.get("STEMCHOTIC_E2E") != "1" or _env_python() is None,
    reason="opt-in: set STEMCHOTIC_E2E=1 and build the app env first",
)


def _write_sine_wav(path: Path, seconds=3.0, rate=44100, freq=220.0):
    """A short stereo tone. Content doesn't matter (we assert files exist, not
    audio), only that it's a valid wav the engine can chew on."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            v = int(0.3 * 32767 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<hh", v, v)
        w.writeframes(bytes(frames))


def test_separation_writes_stem_files(tmp_path):
    wav = tmp_path / "clip.wav"
    _write_sine_wav(wav)

    # --stems Vocals at fast quality: smallest sensible job. -y skips the
    # model-download confirmation. Outputs land next to the input (tmp_path).
    proc = subprocess.run(
        [str(_env_python()), "stemchotic.py",
         "--stems", "Vocals", "--quality", "fast", "--format", "wav", "-y", str(wav)],
        cwd=str(_REPO), capture_output=True, text=True, timeout=900,
    )
    assert proc.returncode == 0, f"separation failed:\nSTDOUT\n{proc.stdout}\nSTDERR\n{proc.stderr}"

    outputs = [p for p in tmp_path.iterdir() if p != wav and p.suffix.lower() == ".wav"]
    assert outputs, f"no stem files written. stdout:\n{proc.stdout}"
    # Vocals separation yields a vocal + its complement; names carry the stem.
    names = " ".join(p.name for p in outputs).lower()
    assert "vocal" in names or "instrumental" in names, f"unexpected outputs: {[p.name for p in outputs]}"


def _ffmpeg_on_path() -> bool:
    """Bundled static-ffmpeg on PATH; True if ffmpeg is usable."""
    if shutil.which("ffmpeg"):
        return True
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception:
        pass
    return bool(shutil.which("ffmpeg"))


def test_residual_reconstructs_a_48k_container_source(tmp_path):
    """Regression for the 0.9.7 residual fixes. A 48k opus/webm source (the
    yt-dlp case) split with --residual must: decode at all (libsndfile can't open
    webm), write outputs at 44.1k, and have 'picks + residual' reconstruct the
    source. A loud, out-of-sync residual would mean the 48k drift or the level
    attenuation is back."""
    import numpy as np
    import soundfile as sf
    import librosa
    import warnings

    if not _ffmpeg_on_path():
        pytest.skip("ffmpeg unavailable to build the container input")

    wav48 = tmp_path / "src48.wav"
    _write_sine_wav(wav48, seconds=4.0, rate=48000, freq=220.0)
    src = tmp_path / "clip.webm"
    enc = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav48),
                          "-c:a", "libopus", str(src)], capture_output=True, text=True)
    if enc.returncode != 0:
        pytest.skip(f"ffmpeg can't encode opus/webm here: {enc.stderr}")

    proc = subprocess.run(
        [str(_env_python()), "stemchotic.py",
         "--stems", "Vocals", "--quality", "fast", "--format", "wav",
         "--residual", "-y", str(src)],
        cwd=str(_REPO), capture_output=True, text=True, timeout=900,
    )
    assert proc.returncode == 0, f"separation failed:\nSTDOUT\n{proc.stdout}\nSTDERR\n{proc.stderr}"

    voc, res = tmp_path / "clip [Vocals].wav", tmp_path / "clip [Residual].wav"
    assert voc.exists() and res.exists(), f"missing outputs: {list(tmp_path.iterdir())}"

    v, sr_v = sf.read(voc)
    r, sr_r = sf.read(res)
    assert sr_v == 44100 and sr_r == 44100, f"outputs not 44.1k: vocals={sr_v}, residual={sr_r}"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mix = librosa.load(str(src), sr=44100, mono=False)[0].T
    n = min(len(v), len(r), len(mix))
    err_peak = float(np.max(np.abs((v[:n] + r[:n]) - mix[:n])))
    mix_peak = float(np.max(np.abs(mix[:n])))
    assert err_peak < mix_peak * 0.02, (
        f"picks + residual don't reconstruct the mix: error peak {err_peak:.4f} "
        f"vs mix peak {mix_peak:.4f} (drift or attenuation is back)")
