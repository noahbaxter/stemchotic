import os

import numpy as np
import soundfile as sf

from src.core.separator import _residual


def _tone(freq, sr, secs=1.0):
    t = np.linspace(0, secs, int(sr * secs), endpoint=False)
    return 0.4 * np.sin(2 * np.pi * freq * t).astype("float32")


def test_residual_near_silence_when_stems_sum_to_mix(tmp_path):
    # Two stems that sum EXACTLY to the mix. Residual must be ~silence.
    sr = 44100
    a, b = _tone(220, sr), _tone(660, sr)
    mix = np.stack([a + b, a + b], axis=1)   # stereo
    sf.write(tmp_path / "mix.wav", mix, sr)
    sf.write(tmp_path / "A.wav", np.stack([a, a], axis=1), sr)
    sf.write(tmp_path / "B.wav", np.stack([b, b], axis=1), sr)

    out = _residual(str(tmp_path / "mix.wav"),
                    [str(tmp_path / "A.wav"), str(tmp_path / "B.wav")],
                    "mix", "WAV")
    res, _ = sf.read(out)
    assert np.max(np.abs(res)) < 1e-3, f"residual not silent: peak {np.max(np.abs(res))}"


def test_residual_aligns_when_mix_is_48k_but_stems_are_44k(tmp_path):
    # yt-dlp/opus case: mix arrives at 48k, audio-separator writes stems at 44.1k.
    # Residual must resample the mix to the stems' rate, not subtract raw samples
    # at mismatched rates (which drifts and leaves a full-mix-loud residual).
    src_sr, stem_sr = 48000, 44100
    a48, b48 = _tone(220, src_sr), _tone(660, src_sr)
    mix48 = np.stack([a48 + b48, a48 + b48], axis=1)
    sf.write(tmp_path / "mix.wav", mix48, src_sr)

    import librosa
    a44 = librosa.resample(a48, orig_sr=src_sr, target_sr=stem_sr)
    b44 = librosa.resample(b48, orig_sr=src_sr, target_sr=stem_sr)
    sf.write(tmp_path / "A.wav", np.stack([a44, a44], axis=1), stem_sr)
    sf.write(tmp_path / "B.wav", np.stack([b44, b44], axis=1), stem_sr)

    out = _residual(str(tmp_path / "mix.wav"),
                    [str(tmp_path / "A.wav"), str(tmp_path / "B.wav")],
                    "mix", "WAV")
    res, res_sr = sf.read(out)
    assert res_sr == stem_sr, f"residual sr {res_sr} != stem sr {stem_sr}"
    # Resampling isn't bit-exact, but should cancel to a low residual, not full mix.
    assert np.max(np.abs(res)) < 0.02, f"residual not cancelled: peak {np.max(np.abs(res))}"
