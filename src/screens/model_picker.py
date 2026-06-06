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


_BS = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"

# Curated picks by stem grouping: (label, model_filename, why)
CURATED = [
    ("Vocals (cleanest)", "vocals_mel_band_roformer.ckpt", "Best vocal isolation (12.6)"),
    ("Instrumental (cleanest)", _BS, "Best instrumental (16.5)"),
    ("Vocals + Instrumental", _BS, "Karaoke split, both in one pass"),
    ("4-stem: drums / bass / vocals / other", "htdemucs_ft.yaml", "Best 4-stem, slower"),
    ("Full band: 6 stems", "htdemucs_6s.yaml", "+ guitar / piano / other"),
]

_CATALOG = None


def show_model_picker(current: str | None = None) -> tuple[str, str | None]:
    """Curated picks + Advanced browser. Returns one of:
    ("set", filename), ("clear", None), or ("cancel", None). Picking a model only
    sets the override; the caller decides when to actually run."""
    while True:
        menu = Menu(
            title="Pick a model",
            subtitle="Recommended picks by stem grouping, or browse everything.",
            esc_label="Back",
        )
        for label, model, why in CURATED:
            mark = f"{Colors.GREEN}● {Colors.RESET}" if model == current else "  "
            menu.add_item(MenuItem(label=f"{mark}{label}", value=("model", model), description=why))
        menu.add_item(MenuDivider())
        menu.add_item(MenuItem(label=f"{Colors.HOTKEY}Advanced:{Colors.RESET} all models, ranked by SDR…",
                               value=("advanced", None)))
        if current:
            menu.add_item(MenuItem(label=f"{Colors.MUTED}Clear override (use stem picks){Colors.RESET}",
                                   value=("clear", None)))

        result = menu.run()
        if result is None:
            return ("cancel", None)
        kind, payload = result.value
        if kind == "model":
            return ("set", payload)
        if kind == "clear":
            return ("clear", None)
        if kind == "advanced":
            chosen = _advanced_model_list()
            if chosen is None:
                continue  # Esc in Advanced returns here, not to the main picker
            return ("set", chosen)


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
