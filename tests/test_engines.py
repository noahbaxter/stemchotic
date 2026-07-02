from src.core.engines import resolve


def test_drum_stem_mode_does_a_direct_split_when_drums_selected():
    passes = resolve(["Drums"], kit_split="5", kit_source="stem")
    assert len(passes) == 1 and passes[0].direct_split, (
        "Drums + Drum stem should be one direct kit-split pass"
    )


def test_stray_drum_stem_value_is_inert_without_drums_selected():
    # A persisted kit_source="stem" must not hijack a non-drum run: with Vocals
    # selected and no Drums, we get the normal vocal pass, never a direct split.
    passes = resolve(["Vocals"], kit_split="5", kit_source="stem")
    assert passes and not any(p.direct_split for p in passes), (
        "kit_source='stem' must be ignored when Drums is not selected"
    )
    assert any("Vocals" in p.stems for p in passes)
