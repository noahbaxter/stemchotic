"""
Model overlay - choose which model each stem type uses.

Opened with Tab from the stem picker. Sections are per target stem (Vocals,
Instrumental, Drums, Bass, ...), each listing the models that produce that stem
ranked by *that stem's* SDR, so you pick the best per type. When your selection
spans types and one multi-stem model can cover it, a "one model for everything"
section is offered. Picks write into the picker state (per-type, session).

Reality: dedicated single-stem models basically only exist for vocals/
instrumental; drums/bass/guitar/piano all come from the 4-/6-stem demucs models,
so those sections list the same handful (ranked by the relevant stem's SDR).
"""

import re

from chotic_ui import Colors, FilterList
from ..core.engines import ENGINE_MODEL, _NAME_TO_ENGINE, weight_tier

_SDR_NUM = re.compile(r"\(([\d.]+)\)")
_TIER_COLOR = {"fast": Colors.SUCCESS, "avg": Colors.MUTED, "slow": Colors.ERROR}

# Display stem -> catalog stem (kit pieces have no catalogue model).
_CATALOG_STEM = {
    "Vocals": "vocals", "Instrumental": "instrumental", "Drums": "drums",
    "Bass": "bass", "Guitar": "guitar", "Piano": "piano", "Other": "other",
}

# Overlay sections: (title, catalog stem to rank by, category the pick overrides).
_STEM_SECTIONS = [
    ("Vocals", "vocals", "roformer"),
    ("Instrumental", "instrumental", "roformer"),
    ("Drums", "drums", "rhythm"),
    ("Bass", "bass", "rhythm"),
    ("Guitar / Piano / Other (6-stem)", "guitar", "extra"),
]

_TOP_N = 6
_CATALOG = None


def _parse(info: dict) -> dict:
    """{stem_name: sdr} for a model (sdr 0.0 if unlisted)."""
    out = {}
    for entry in info.get("Stems", []) or []:
        name = entry.split("(")[0].replace("*", "").strip().lower()
        if not name:
            continue
        m = _SDR_NUM.search(entry)
        out[name] = float(m.group(1)) if m else out.get(name, 0.0)
    for k, v in (info.get("SDR") or {}).items():
        if isinstance(v, (int, float)):
            out[k.lower()] = float(v)
    return out


def _load_catalog():
    """[(filename, arch, {stem: sdr})], cached."""
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG
    from ..core.separator import _make_separator
    data = _make_separator().get_simplified_model_list()
    _CATALOG = [(fn, info.get("Type", "?"), _parse(info)) for fn, info in data.items()]
    return _CATALOG


def _by_stem(rows, stem):
    """Models producing `stem`, ranked by that stem's SDR. Returns (fn, arch, sdr)."""
    out = [(fn, arch, sdrs[stem]) for fn, arch, sdrs in rows if stem in sdrs]
    out.sort(key=lambda r: r[2], reverse=True)
    return out[:_TOP_N]


def _one_pass(rows, selected):
    """Models covering every selected stem, ranked by best SDR. (fn, arch, sdr)."""
    needed = set()
    for name in selected:
        cs = _CATALOG_STEM.get(name)
        if cs is None:
            return []
        needed.add(cs)
    if not needed:
        return []
    out = [(fn, arch, max(sdrs.values()) if sdrs else 0.0)
           for fn, arch, sdrs in rows if needed <= set(sdrs)]
    out.sort(key=lambda r: r[2], reverse=True)
    return out[:_TOP_N]


def _label(fn, arch, sdr, current):
    mark = f"{Colors.SUCCESS}● {Colors.RESET}" if current else "  "
    sdr_s = f"{sdr:4.1f}" if sdr else "  - "
    tier = weight_tier(arch, fn)
    tier_s = f"{_TIER_COLOR.get(tier, Colors.MUTED)}{tier:<5}{Colors.RESET}"
    return f"{mark}{Colors.PRIMARY}{sdr_s}{Colors.RESET}  {tier_s}  {fn}"


def show_model_overlay(selected: list, state: dict) -> None:
    """Tab overlay. Mutates state['models'] (per-category) and state['one_pass'].
    Loops until Esc."""
    print("\n  Loading model list...")
    try:
        rows = _load_catalog()
    except Exception as e:
        print(f"  Could not load model list: {e}")
        return

    models = state.setdefault("models", {})
    sel_engines = {_NAME_TO_ENGINE.get(n) for n in selected}

    while True:
        items = [(f"{Colors.MUTED}Reset all to SDR defaults{Colors.RESET}", ("reset", None, None)),
                 ("", FilterList.SECTION)]

        if len(sel_engines - {"kit"}) > 1:
            opc = _one_pass(rows, selected)
            if opc:
                items.append(("── One model for everything selected ──", FilterList.SECTION))
                for fn, arch, sdr in opc:
                    items.append((_label(fn, arch, sdr, fn == state.get("one_pass")), ("onepass", None, fn)))

        for title, cstem, engine in _STEM_SECTIONS:
            if selected and engine not in sel_engines:
                continue
            cands = _by_stem(rows, cstem)
            if not cands:
                continue
            current = models.get(engine, ENGINE_MODEL[engine])
            items.append((f"── {title} ──", FilterList.SECTION))
            for fn, arch, sdr in cands:
                items.append((_label(fn, arch, sdr, fn == current and not state.get("one_pass")),
                              ("cat", engine, fn)))

        picker = FilterList(
            items,
            title="Choose models",
            subtitle="Best model per type, ranked by that stem's SDR. SDR · speed · file. Type to filter.",
            esc_label="Done",
            prompt="Filter",
        )
        choice = picker.run()
        if choice is None:
            return
        kind, engine, fn = choice
        if kind == "reset":
            state["models"] = {}
            state["one_pass"] = None
            models = state["models"]
        elif kind == "onepass":
            state["one_pass"] = fn
        elif kind == "cat":
            models[engine] = fn
            state["one_pass"] = None
