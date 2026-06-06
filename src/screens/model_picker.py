"""
Model picker - two tiers.

Tier 1: a few curated "ideal for this purpose" picks with a one-line why.
Tier 2 (Advanced): every model in the catalogue, grouped into sections by what
they output and ranked by SDR within each, live-filterable. The "I know better"
escape hatch.

Returns a model filename (a global override for the whole separation) or None.
"""

import logging
import re

from chotic_ui import Colors, Menu, MenuItem, MenuDivider, FilterList

_SDR_NUM = re.compile(r"\(([\d.]+)\)")


# Curated picks: (label, model_filename, why)
CURATED = [
    ("Karaoke (vocals + instrumental)", "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
     "Best instrumental, vocals nearly best, one pass"),
    ("Cleanest vocals", "vocals_mel_band_roformer.ckpt",
     "Highest vocal SDR (12.6)"),
    ("Full band (6 stems)", "htdemucs_6s.yaml",
     "drums/bass/vocals/guitar/piano/other"),
    ("Best drums + bass", "htdemucs_ft.yaml",
     "Top rhythm SDR (10.0 / 12.0), slower"),
]

_CATALOG = None


def show_model_picker() -> str | None:
    """Curated picks + an Advanced entry. Returns a model filename or None."""
    menu = Menu(
        title="Pick a model",
        subtitle="Recommended picks for common goals, or browse everything.",
        esc_label="Back",
    )
    for label, model, why in CURATED:
        menu.add_item(MenuItem(label=label, value=("model", model), description=why))
    menu.add_item(MenuDivider())
    menu.add_item(MenuItem(label=f"{Colors.HOTKEY}Advanced:{Colors.RESET} all models, ranked by SDR…",
                           value=("advanced", None)))

    result = menu.run()
    if result is None:
        return None
    kind, payload = result.value
    if kind == "model":
        return payload
    return _advanced_model_list()


def _load_catalog():
    """[(filename, category, best_sdr, arch, stems_str)], cached."""
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG
    from audio_separator.separator import Separator
    data = Separator(log_level=logging.ERROR).get_simplified_model_list()

    rows = []
    for fn, info in data.items():
        stems, best = _parse(info)
        rows.append((fn, _category(stems), best, info.get("Type", "?"), ", ".join(sorted(stems)) or "?"))
    _CATALOG = rows
    return rows


def _parse(info: dict):
    """Output stem names and best SDR, parsed from the model's Stems field
    (which lists every output stem; SDR is only in parens on some)."""
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


def _category(stems: set) -> str:
    if "guitar" in stems or "piano" in stems:
        return "6-stem (full band)"
    if "drums" in stems and "bass" in stems:
        return "4-stem (drums/bass/vocals/other)"
    if "vocals" in stems or "instrumental" in stems:
        return "Vocals / Instrumental"
    return "Specialized / utility"


_SECTION_ORDER = [
    "Vocals / Instrumental",
    "4-stem (drums/bass/vocals/other)",
    "6-stem (full band)",
    "Specialized / utility",
]


def _advanced_model_list() -> str | None:
    print("\n  Loading model list...")
    try:
        rows = _load_catalog()
    except Exception as e:
        print(f"  Could not load model list: {e}")
        return None

    items = []
    for section in _SECTION_ORDER:
        in_sec = [r for r in rows if r[1] == section]
        if not in_sec:
            continue
        in_sec.sort(key=lambda r: r[2], reverse=True)  # best SDR first
        items.append((f"── {section} ──", FilterList.SECTION))
        for fn, _cat, best, arch, stems in in_sec:
            sdr = f"{best:4.1f}" if best else "  - "
            label = (f"{Colors.HOTKEY}{sdr}{Colors.RESET}  {Colors.DIM}{arch:5}{Colors.RESET}  "
                     f"{fn}   {Colors.DIM}{stems}{Colors.RESET}")
            items.append((label, fn))

    picker = FilterList(
        items,
        title="All models (ranked by SDR)",
        subtitle="Type to filter by name, stem, or architecture.",
        esc_label="Back",
        prompt="Filter",
    )
    return picker.run()
