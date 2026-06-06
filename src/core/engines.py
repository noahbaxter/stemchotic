"""
Engines, stem options, and selection -> execution-plan resolution.

The UI is one flat screen of stems you highlight. Each stem belongs to exactly
one engine, so your selection implicitly picks the model(s). `resolve()` turns a
set of selected stem names into the concrete passes to run.
"""

from dataclasses import dataclass, field


# --- Model filenames as known to python-audio-separator ---------------------
# Verify against `audio-separator --list_models` before relying on them.
# Defaults chosen by SDR from `audio-separator --list_models`.
BS_ROFORMER = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"  # #1 instrumental (16.5), near-best vocals (12.4)
HTDEMUCS = "htdemucs.yaml"            # balanced drums (9.4) / bass (11.6)
HTDEMUCS_6S = "htdemucs_6s.yaml"      # only source of guitar / piano / other
# drumsep: community Hybrid Demucs checkpoint, NOT in the catalogue. Experimental.
DRUMSEP = "drumsep.th"

ENGINE_MODEL = {
    "roformer": BS_ROFORMER,
    "rhythm": HTDEMUCS,
    "extra": HTDEMUCS_6S,
    "kit": DRUMSEP,
}
ENGINE_LABEL = {
    "roformer": "BS-RoFormer",
    "rhythm": "HTDemucs",
    "extra": "HTDemucs 6s",
    "kit": "drumsep",
}


@dataclass(frozen=True)
class StemOption:
    name: str            # display + output stem name
    engine: str          # roformer | rhythm | extra | kit
    experimental: bool = False


# Each stem belongs to one engine, so highlighting it picks the model.
STEM_OPTIONS = [
    StemOption("Vocals", "roformer"),
    StemOption("Instrumental", "roformer"),
    StemOption("Drums", "rhythm"),
    StemOption("Bass", "rhythm"),
    StemOption("Guitar", "extra"),
    StemOption("Piano", "extra"),
    StemOption("Other", "extra"),
    StemOption("Kick", "kit", experimental=True),
    StemOption("Snare", "kit", experimental=True),
    StemOption("Toms", "kit", experimental=True),
    StemOption("Cymbals", "kit", experimental=True),
]

_NAME_TO_ENGINE = {s.name: s.engine for s in STEM_OPTIONS}


def model_label(name: str) -> str:
    """Short label of the model a given stem uses by default (for display)."""
    return ENGINE_LABEL.get(_NAME_TO_ENGINE.get(name, ""), "")

# CLI shortcuts -> default stem selections.
CLI_PRESETS = {
    "vocals": ["Vocals", "Instrumental"],
    "instrumental": ["Instrumental"],
    "band": ["Drums", "Bass", "Vocals", "Guitar", "Piano", "Other"],
    "drums": ["Drums"],
    "kit": ["Kick", "Snare", "Toms", "Cymbals"],
    "bass": ["Bass"],
}


# Pretty short names for display; arbitrary models fall back to the filename stem.
MODEL_SHORT = {
    BS_ROFORMER: "BS-RoFormer",
    HTDEMUCS: "HTDemucs",
    HTDEMUCS_6S: "HTDemucs 6s",
    DRUMSEP: "drumsep",
    "htdemucs_ft.yaml": "HTDemucs FT",
    "hdemucs_mmi.yaml": "HDemucs MMI",
    "vocals_mel_band_roformer.ckpt": "Mel-Band",
}


def short_name(filename: str) -> str:
    if filename in MODEL_SHORT:
        return MODEL_SHORT[filename]
    base = filename.rsplit(".", 1)[0]
    return base if len(base) <= 18 else base[:17] + "…"


def model_for(stem: str, models: dict | None = None) -> str:
    """The model filename a stem uses, honoring per-category overrides."""
    cat = _NAME_TO_ENGINE.get(stem, "")
    return (models or {}).get(cat, ENGINE_MODEL.get(cat, ""))


def display_model(stem: str, models: dict | None = None) -> str:
    return short_name(model_for(stem, models))


@dataclass
class Pass:
    engine: str
    model: str
    stems: list[str]               # stems to keep from this engine
    single_stem: str | None = None  # exactly-one -> output_single_stem (one file)
    cascade_drums: bool = False     # kit: extract drums first, then drumsep


def resolve(selected: list[str], models: dict | None = None, one_pass: str | None = None) -> list[Pass]:
    """Concrete passes for a selection.

    `models`: per-category model overrides {category: filename}.
    `one_pass`: a single model to run for the whole selection (cross-category),
    filtered to the selected stems.
    """
    if one_pass:
        single = selected[0] if len(selected) == 1 else None
        return [Pass(engine="custom", model=one_pass, stems=list(selected), single_stem=single)]

    by_engine: dict[str, list[str]] = {}
    for opt in STEM_OPTIONS:               # stable, deterministic order
        if opt.name in selected:
            by_engine.setdefault(opt.engine, []).append(opt.name)

    passes: list[Pass] = []
    for engine, stems in by_engine.items():
        model = (models or {}).get(engine, ENGINE_MODEL[engine])
        p = Pass(engine=engine, model=model, stems=stems)
        if engine == "kit":
            p.cascade_drums = True
        elif len(stems) == 1:
            p.single_stem = stems[0]       # write just the one file
        passes.append(p)
    return passes


def plan_text(selected: list[str], models: dict | None = None, one_pass: str | None = None) -> str:
    """One-line description of what the current selection will run."""
    if not selected:
        return "Nothing selected - pick stems with Space, then Start splitting."

    if one_pass:
        return f"1 pass: {short_name(one_pass)} -> {', '.join(selected)} (one model)"

    parts = []
    for p in resolve(selected, models):
        label = short_name(p.model)
        if p.cascade_drums:
            parts.append(f"drums -> drumsep -> {', '.join(p.stems)}")
        elif p.single_stem:
            parts.append(f"{label} -> {p.single_stem} only")
        else:
            parts.append(f"{label} -> {', '.join(p.stems)}")
    n = len(parts)
    return f"{n} pass{'es' if n > 1 else ''}: " + "  ·  ".join(parts)
