"""
Engines, stem options, and selection -> execution-plan resolution.

The UI is one flat screen of stems you highlight. Each stem belongs to exactly
one engine, so your selection implicitly picks the model(s). `resolve()` turns a
set of selected stem names into the concrete passes to run.
"""

from dataclasses import dataclass, field


# --- Model filenames as known to python-audio-separator ---------------------
# Verify against `audio-separator --list_models` before relying on them.
BS_ROFORMER_VOCALS = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
HTDEMUCS_6S = "htdemucs_6s.yaml"
# drumsep: community Hybrid Demucs checkpoint, NOT in the default catalogue.
# Loading it is unverified - the `kit` stems are experimental.
DRUMSEP = "drumsep.th"

ENGINE_MODEL = {
    "roformer": BS_ROFORMER_VOCALS,
    "band": HTDEMUCS_6S,
    "kit": DRUMSEP,
}
ENGINE_LABEL = {
    "roformer": "BS-RoFormer",
    "band": "HTDemucs 6-stem",
    "kit": "drumsep",
}


@dataclass(frozen=True)
class StemOption:
    name: str            # display + output stem name
    engine: str          # roformer | band | kit
    experimental: bool = False


# Each stem belongs to one engine, so highlighting it picks the model.
STEM_OPTIONS = [
    StemOption("Vocals", "roformer"),
    StemOption("Instrumental", "roformer"),
    StemOption("Drums", "band"),
    StemOption("Bass", "band"),
    StemOption("Guitar", "band"),
    StemOption("Piano", "band"),
    StemOption("Other", "band"),
    StemOption("Kick", "kit", experimental=True),
    StemOption("Snare", "kit", experimental=True),
    StemOption("Toms", "kit", experimental=True),
    StemOption("Cymbals", "kit", experimental=True),
]

_NAME_TO_ENGINE = {s.name: s.engine for s in STEM_OPTIONS}

# CLI shortcuts -> default stem selections.
CLI_PRESETS = {
    "vocals": ["Vocals", "Instrumental"],
    "instrumental": ["Instrumental"],
    "band": ["Drums", "Bass", "Vocals", "Guitar", "Piano", "Other"],
    "drums": ["Drums"],
    "kit": ["Kick", "Snare", "Toms", "Cymbals"],
    "bass": ["Bass"],
}


@dataclass
class Pass:
    engine: str
    model: str
    stems: list[str]               # stems to keep from this engine
    single_stem: str | None = None  # exactly-one -> output_single_stem (one file)
    cascade_drums: bool = False     # kit: extract drums first, then drumsep


def resolve(selected: list[str]) -> list[Pass]:
    """Group selected stems by engine into concrete passes, preserving the
    STEM_OPTIONS order."""
    by_engine: dict[str, list[str]] = {}
    for opt in STEM_OPTIONS:               # stable, deterministic order
        if opt.name in selected:
            by_engine.setdefault(opt.engine, []).append(opt.name)

    passes: list[Pass] = []
    for engine, stems in by_engine.items():
        p = Pass(engine=engine, model=ENGINE_MODEL[engine], stems=stems)
        if engine == "kit":
            p.cascade_drums = True
        elif len(stems) == 1:
            p.single_stem = stems[0]       # write just the one file
        passes.append(p)
    return passes


def plan_text(selected: list[str]) -> str:
    """One-line, human-readable description of what the current selection will
    run. Shown live below the picker."""
    if not selected:
        return "Nothing selected - highlight stems with Space, then Enter on Separate."

    passes = resolve(selected)
    parts = []
    for p in passes:
        if p.single_stem:
            parts.append(f"{ENGINE_LABEL[p.engine]} -> {p.single_stem} only")
        elif p.cascade_drums:
            parts.append(f"drums -> drumsep -> {', '.join(p.stems)}")
        else:
            parts.append(f"{ENGINE_LABEL[p.engine]} -> {', '.join(p.stems)}")
    n = len(passes)
    prefix = f"{n} pass{'es' if n > 1 else ''}: "
    return prefix + "  ·  ".join(parts)
