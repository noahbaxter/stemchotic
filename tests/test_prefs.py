from src.core import prefs


def test_load_is_empty_when_nothing_saved(tmp_path):
    assert prefs.load(tmp_path / "state.json") == {}


def test_settings_round_trip(tmp_path):
    # kit_source="song" here (not "stem"): that invariant has its own dedicated
    # test below, this one just covers the plain settings.
    p = tmp_path / "state.json"
    state = {"output_format": "FLAC", "quality": "fast", "keep_all": True,
             "residual": True, "kit_split": "5", "kit_source": "song"}
    prefs.save(state, p)
    assert prefs.load(p) == state


def test_per_stem_model_overrides_persist(tmp_path):
    p = tmp_path / "state.json"
    prefs.save({"models": {"Bass": "some_bass_model.ckpt"}}, p)
    assert prefs.load(p)["models"] == {"Bass": "some_bass_model.ckpt"}


def test_selection_persists_as_a_set(tmp_path):
    p = tmp_path / "state.json"
    prefs.save({"selected": {"Drums", "Bass"}, "quality": "fast"}, p)
    saved = prefs.load(p)
    assert saved["selected"] == {"Drums", "Bass"} and isinstance(saved["selected"], set)


def test_selected_and_kit_source_persist_together_so_the_escape_hatch_survives(tmp_path):
    # The invariant kit_source=="stem" => "Drums" in selected must survive a
    # restart, or a restored drum-stem session hides its only way back to "song"
    # (see prefs.py docstring / the lockout this replaced).
    p = tmp_path / "state.json"
    prefs.save({"selected": {"Drums"}, "kit_source": "stem"}, p)
    saved = prefs.load(p)
    assert saved["kit_source"] == "stem" and saved["selected"] == {"Drums"}


def test_load_self_heals_a_legacy_kit_source_without_matching_selection(tmp_path):
    # Simulates a state.json written by the pre-fix 0.9.4 build, which persisted
    # kit_source alone (selected didn't exist yet). Must not resurrect the lockout
    # for users upgrading straight from that broken build.
    import json
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"kit_source": "stem"}))
    assert prefs.load(p).get("kit_source") != "stem"


def test_one_pass_is_not_persisted(tmp_path):
    # Temporary "run everything through this one model" override, not a lasting pref.
    p = tmp_path / "state.json"
    prefs.save({"one_pass": "x", "quality": "fast"}, p)
    saved = prefs.load(p)
    assert "one_pass" not in saved and saved == {"quality": "fast"}


def test_save_preserves_unrelated_state_keys(tmp_path):
    import json
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"hardware": "gpu", "device": "cpu"}))
    prefs.save({"quality": "fast"}, p)
    data = json.loads(p.read_text())
    assert data["hardware"] == "gpu" and data["device"] == "cpu" and data["quality"] == "fast"
