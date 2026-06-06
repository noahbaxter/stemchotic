"""
Curated separation templates.

This is the product: instead of making people pick from 40 cryptic model names,
each template maps a plain-language goal to a known-good model (or a cascade of
models) from python-audio-separator's catalogue.

A template is one or more Stages. A single-stage template runs one model. A
multi-stage template is a cascade: the stems kept from one stage become the input
to the next (e.g. pull drums out of the mix, then split that drum stem into
kick/snare/toms/cymbals).
"""

from dataclasses import dataclass, field


# --- Model filenames as known to python-audio-separator ---------------------
# Verify exact names against `audio-separator --list_models` before relying on
# them; the roformer checkpoint name in particular changes between releases.
BS_ROFORMER_VOCALS = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
HTDEMUCS = "htdemucs.yaml"
HTDEMUCS_6S = "htdemucs_6s.yaml"
# drumsep is a community Hybrid Demucs checkpoint, NOT in the default catalogue.
# Loading it is the one unproven piece of the cascade. Treat as experimental.
DRUMSEP = "drumsep.th"


@dataclass
class Stage:
    """One model pass. `keep` names the output stems to keep (and, in a cascade,
    feed into the next stage)."""
    model: str
    keep: list[str]


@dataclass
class Template:
    key: str            # CLI name, e.g. "vocals"
    name: str           # display name in the menu
    description: str    # "best for ..." one-liner
    stages: list[Stage]
    experimental: bool = False


TEMPLATES: list[Template] = [
    Template(
        key="vocals",
        name="Vocals + Instrumental",
        description="Clean vocal / instrumental split for karaoke and acapellas",
        stages=[Stage(BS_ROFORMER_VOCALS, keep=["Vocals", "Instrumental"])],
    ),
    Template(
        key="instrumental",
        name="Clean Instrumental",
        description="Just the backing track, vocals removed",
        stages=[Stage(BS_ROFORMER_VOCALS, keep=["Instrumental"])],
    ),
    Template(
        key="band",
        name="Full Band (6 stems)",
        description="Drums, bass, vocals, guitar, piano, other - for remixing",
        stages=[Stage(HTDEMUCS_6S, keep=["Drums", "Bass", "Vocals", "Guitar", "Piano", "Other"])],
    ),
    Template(
        key="drums",
        name="Drums (isolated)",
        description="Pull the full drum kit out of the mix",
        stages=[Stage(HTDEMUCS, keep=["Drums"])],
    ),
    Template(
        key="kit",
        name="Drum Kit Pieces",
        description="Charting: split drums into kick / snare / toms / cymbals",
        stages=[
            Stage(HTDEMUCS, keep=["Drums"]),
            Stage(DRUMSEP, keep=["Kick", "Snare", "Toms", "Cymbals"]),
        ],
        experimental=True,
    ),
    Template(
        key="bass",
        name="Bass",
        description="Isolate the bassline",
        stages=[Stage(HTDEMUCS, keep=["Bass"])],
    ),
]


def get_template(key: str) -> Template | None:
    """Look up a template by its CLI key."""
    for t in TEMPLATES:
        if t.key == key:
            return t
    return None
