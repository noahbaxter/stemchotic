"""
Engines, stem options, and selection -> execution-plan resolution.

The UI is one flat screen of stems you highlight. Each stem belongs to exactly
one engine, so your selection implicitly picks the model(s). `resolve()` turns a
set of selected stem names into the concrete passes to run.
"""

import json
import os
from dataclasses import dataclass

# Editable defaults (per-category model, friendly names, curated picks) live in
# models.json at the repo root. SDR rankings + the model list come live from
# audio-separator; only the picks/labels are config.
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "models.json")
with open(_CONFIG_PATH, encoding="utf-8") as _f:
    CONFIG = json.load(_f)

ENGINE_MODEL = CONFIG["category_defaults"]   # category -> default model filename
MODEL_SHORT = CONFIG["names"]                # model filename -> friendly short name


@dataclass(frozen=True)
class StemOption:
    name: str            # display + output stem name
    engine: str          # roformer | rhythm | extra | kit
    experimental: bool = False
    model: str = ""      # kit options carry their own drumsep model


# Each stem belongs to one engine, so highlighting it picks the model. Kit options
# (drumsep 4 / 6) come from models.json - each runs a whole-kit cascade.
STEM_OPTIONS = [
    StemOption("Vocals", "roformer"),
    StemOption("Instrumental", "roformer"),
    StemOption("Drums", "rhythm"),
    StemOption("Bass", "rhythm"),
    StemOption("Guitar", "extra"),
    StemOption("Piano", "extra"),
    StemOption("Other", "extra"),
] + [StemOption(k["name"], "kit", experimental=True, model=k["model"])
     for k in CONFIG.get("kit_models", [])]

_NAME_TO_ENGINE = {s.name: s.engine for s in STEM_OPTIONS}
_STEM_MODEL = {s.name: s.model for s in STEM_OPTIONS if s.model}
_KIT_NAMES = [s.name for s in STEM_OPTIONS if s.engine == "kit"]


# CLI shortcuts -> default stem selections.
CLI_PRESETS = {
    "vocals": ["Vocals", "Instrumental"],
    "instrumental": ["Instrumental"],
    "band": ["Drums", "Bass", "Vocals", "Guitar", "Piano", "Other"],
    "drums": ["Drums"],
    "bass": ["Bass"],
}
if _KIT_NAMES:
    CLI_PRESETS["kit"] = [_KIT_NAMES[-1]]   # default kit = the 6-piece (last)
    CLI_PRESETS["kit4"] = [_KIT_NAMES[0]]   # the 4-piece


def short_name(filename: str) -> str:
    """Friendly name (from models.json), else the filename stem (truncated)."""
    if filename in MODEL_SHORT:
        return MODEL_SHORT[filename]
    base = filename.rsplit(".", 1)[0]
    return base if len(base) <= 18 else base[:17] + "…"


def weight_tier(arch: str, filename: str) -> str:
    """Rough relative speed: fast / avg / slow. A heuristic from the architecture
    plus a few filename markers (no real benchmark data)."""
    fl = (filename or "").lower()
    a = (arch or "").upper()
    if "ensemble" in fl or "_ft" in fl:   # bag-of-models / ensembles
        return "slow"
    if "roformer" in fl:                   # transformers are the heaviest
        return "slow"
    if a in ("VR", "MDX"):                  # VR-arch and plain MDX-Net are quick
        return "fast"
    return "avg"                            # MDX23C, Demucs, unknown


def model_for(stem: str, models: dict | None = None) -> str:
    """The model filename a stem uses, honoring per-category overrides."""
    if stem in _STEM_MODEL:          # kit options carry their own model
        return _STEM_MODEL[stem]
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
    kit_passes: list[Pass] = []
    for opt in STEM_OPTIONS:               # stable, deterministic order
        if opt.name not in selected:
            continue
        if opt.engine == "kit":            # each kit option = its own whole-kit cascade
            kit_passes.append(Pass(engine="kit", model=opt.model, stems=[], cascade_drums=True))
        else:
            by_engine.setdefault(opt.engine, []).append(opt.name)

    passes: list[Pass] = []
    for engine, stems in by_engine.items():
        model = (models or {}).get(engine, ENGINE_MODEL[engine])
        p = Pass(engine=engine, model=model, stems=stems)
        if len(stems) == 1:
            p.single_stem = stems[0]       # write just the one file
        passes.append(p)
    return passes + kit_passes


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
            parts.append(f"drums -> {label} (full kit)")
        elif p.single_stem:
            parts.append(f"{label} -> {p.single_stem} only")
        else:
            parts.append(f"{label} -> {', '.join(p.stems)}")
    n = len(parts)
    return f"{n} pass{'es' if n > 1 else ''}: " + "  ·  ".join(parts)
