from src.core import prefs


def test_load_is_empty_when_nothing_saved(tmp_path):
    assert prefs.load(tmp_path / "state.json") == {}


def test_settings_round_trip(tmp_path):
    p = tmp_path / "state.json"
    state = {"output_format": "FLAC", "quality": "fast", "keep_all": True,
             "residual": True, "kit_split": "5", "kit_source": "stem"}
    prefs.save(state, p)
    assert prefs.load(p) == state


def test_per_stem_model_overrides_persist(tmp_path):
    p = tmp_path / "state.json"
    prefs.save({"models": {"Bass": "some_bass_model.ckpt"}}, p)
    assert prefs.load(p)["models"] == {"Bass": "some_bass_model.ckpt"}


def test_selection_and_one_pass_are_not_persisted(tmp_path):
    p = tmp_path / "state.json"
    prefs.save({"selected": {"Drums", "Bass"}, "one_pass": "x", "quality": "fast"}, p)
    saved = prefs.load(p)
    assert "selected" not in saved and "one_pass" not in saved
    assert saved == {"quality": "fast"}


def test_save_preserves_unrelated_state_keys(tmp_path):
    import json
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"hardware": "gpu", "device": "cpu"}))
    prefs.save({"quality": "fast"}, p)
    data = json.loads(p.read_text())
    assert data["hardware"] == "gpu" and data["device"] == "cpu" and data["quality"] == "fast"
