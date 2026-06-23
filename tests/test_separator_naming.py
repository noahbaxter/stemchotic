import os

import numpy as np
import soundfile as sf

from src.core.separator import _merge_pieces, _prefix_kit


def test_prefix_kit_tags_pieces_as_drum_parts(tmp_path):
    src = [tmp_path / "Song [Kick].wav", tmp_path / "Song [HH].wav"]
    for p in src:
        p.write_bytes(b"")
    out = _prefix_kit([str(p) for p in src])
    assert sorted(os.path.basename(p) for p in out) == [
        "Song [Drums-HH].wav", "Song [Drums-Kick].wav",
    ]
    assert (tmp_path / "Song [Drums-Kick].wav").exists()
    assert not (tmp_path / "Song [Kick].wav").exists()


def test_prefix_kit_leaves_brackets_in_the_base_alone(tmp_path):
    p = tmp_path / "My [Live] Song [Snare].wav"
    p.write_bytes(b"")
    out = _prefix_kit([str(p)])
    assert os.path.basename(out[0]) == "My [Live] Song [Drums-Snare].wav"


def test_merge_then_prefix_produces_drum_cymbals(tmp_path):
    # The 4-piece layout merges hh+cymbals -> Cymbals on bare names, then the
    # post-step prefixes everything. Verifies the two steps compose correctly.
    sr = 100
    silence = np.zeros((sr, 2), dtype="float32")
    bare = {
        "hh": tmp_path / "Song [HH].wav",
        "cymbals": tmp_path / "Song [Cymbals].wav",
        "kick": tmp_path / "Song [Kick].wav",
    }
    for p in bare.values():
        sf.write(p, silence, sr)

    merged = _merge_pieces([str(p) for p in bare.values()],
                           {"Cymbals": ["hh", "cymbals"]}, "Song", "WAV")
    final = sorted(os.path.basename(p) for p in _prefix_kit(merged))

    assert "Song [Drums-Cymbals].wav" in final   # merged result, prefixed
    assert "Song [Drums-Kick].wav" in final       # unrelated piece, prefixed
    assert not (tmp_path / "Song [HH].wav").exists()   # part consumed by merge
