"""
Model overlay - choose which model each stem category uses.

Opened with Tab from the stem picker. Shows, per category, the models worth
using (ranked by SDR) so you can switch the best model for each type. When your
selection spans categories and a single multi-stem model can cover it, a "one
model for everything" section is offered too. Picks are written into the picker
state (per-category overrides persist for the session).
"""

import logging
import re

from chotic_ui import Colors, FilterList
from ..core.engines import ENGINE_MODEL, _NAME_TO_ENGINE, short_name

_SDR_NUM = re.compile(r"\(([\d.]+)\)")

# Display stem name -> catalog stem name (kit pieces have no catalogue model).
_CATALOG_STEM = {
    "Vocals": "vocals", "Instrumental": "instrumental", "Drums": "drums",
    "Bass": "bass", "Guitar": "guitar", "Piano": "piano", "Other": "other",
}

# Category -> (section title, predicate over a model's stem set).
_CATEGORIES = [
    ("roformer", "Vocals / Instrumental",
     lambda s: ("vocals" in s or "instrumental" in s) and not ({"drums", "bass", "guitar", "piano"} & s)),
    ("rhythm", "Drums / Bass",
     lambda s: {"drums", "bass"} <= s),
    ("extra", "Guitar / Piano / Other",
     lambda s: "guitar" in s or "piano" in s),
]

_TOP_N = 6
_CATALOG = None


def _parse(info: dict):
    stems, sdrs = set(), []
    for entry in info.get("Stems", []) or []:
        name = entry.split("(")[0].replace("*", "").strip().lower()
        if name:
            stems.add(name)
        m = _SDR_NUM.search(entry)
        if m:
            try:
                sdrs.append(float(m.group(1)))
            except ValueError:
                pass
    for v in (info.get("SDR") or {}).values():
        if isinstance(v, (int, float)):
            sdrs.append(float(v))
    return stems, (max(sdrs) if sdrs else 0.0)


def _load_catalog():
    """[(filename, best_sdr, arch, stems_set)], cached."""
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG
    from audio_separator.separator import Separator
    data = Separator(log_level=logging.ERROR).get_simplified_model_list()
    rows = []
    for fn, info in data.items():
        stems, best = _parse(info)
        rows.append((fn, best, info.get("Type", "?"), stems))
    _CATALOG = rows
    return rows


def _candidates(rows, predicate):
    """Models matching a category predicate, best SDR first, capped."""
    matched = [r for r in rows if predicate(r[3])]
    matched.sort(key=lambda r: r[1], reverse=True)
    return matched[:_TOP_N]


def _one_pass_candidates(rows, selected):
    """Models whose stems cover every selected stem (for a single-pass run).
    Returns [] if any selected stem has no catalogue model (e.g. kit pieces)."""
    needed = set()
    for name in selected:
        cat_stem = _CATALOG_STEM.get(name)
        if cat_stem is None:
            return []
        needed.add(cat_stem)
    if not needed:
        return []
    covering = [r for r in rows if needed <= r[3]]
    covering.sort(key=lambda r: r[1], reverse=True)
    return covering[:_TOP_N]


def _label(fn, sdr, arch, current):
    mark = f"{Colors.GREEN}● {Colors.RESET}" if current else "  "
    sdr_s = f"{sdr:4.1f}" if sdr else "  - "
    return f"{mark}{Colors.HOTKEY}{sdr_s}{Colors.RESET}  {Colors.DIM}{arch:5}{Colors.RESET}  {short_name(fn):14}  {Colors.DIM}{fn}{Colors.RESET}"


def show_model_overlay(selected: list, state: dict) -> None:
    """Tab overlay. Mutates state['models'] (per-category) and state['one_pass'].
    Loops until Esc so several categories can be set in one visit."""
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

        # One-pass section (cross-category selection a single model can cover).
        if len(sel_engines - {"kit"}) > 1:
            opc = _one_pass_candidates(rows, selected)
            if opc:
                items.append((f"── One model for everything selected ──", FilterList.SECTION))
                for fn, sdr, arch, _ in opc:
                    items.append((_label(fn, sdr, arch, fn == state.get("one_pass")), ("onepass", None, fn)))

        # Per-category sections (those in the selection, or all if nothing selected).
        for engine, title, pred in _CATEGORIES:
            if selected and engine not in sel_engines:
                continue
            cands = _candidates(rows, pred)
            if not cands:
                continue
            current = models.get(engine, ENGINE_MODEL[engine])
            items.append((f"── {title} ──", FilterList.SECTION))
            for fn, sdr, arch, _ in cands:
                items.append((_label(fn, sdr, arch, fn == current and not state.get("one_pass")),
                              ("cat", engine, fn)))

        picker = FilterList(
            items,
            title="Choose models",
            subtitle="Pick the best model per type. Type to filter. Esc closes.",
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
