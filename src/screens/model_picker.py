"""
Model overlay - a two-pane picker for which model each stem type uses.

Opened with Tab from the stem picker. Left pane is the target (Vocals,
Instrumental, Drums, Bass, Other); the right pane lists every model
that can produce that target, our curated picks pinned at the top with a short
"why", then the rest of the catalogue ranked by that stem's SDR. Tab switches
panes, the cursor moves within the focused pane, typing filters the right pane,
Enter sets the focused model for that target. Picks write into the picker state
(per category, session).
"""

import re

from chotic_ui import Colors, TwoPane
from ..core.engines import (CONFIG, ENGINE_MODEL, MODEL_SHORT, MVSEP_SDR, _NAME_TO_ENGINE,
                            category_model, short_name, weight_tier, DEFAULT_QUALITY)

_SDR_NUM = re.compile(r"\(([\d.]+)\)")
_TIER_COLOR = {"fast": Colors.SUCCESS, "avg": Colors.MUTED, "slow": Colors.ERROR}

_CUSTOM_STEMS = {m["filename"]: m.get("stems", []) for m in CONFIG.get("custom_models", [])}
_NOTES = CONFIG.get("model_notes", {})

# Left pane: (title, catalog stem to rank the right pane by, category overridden).
TARGETS = [
    ("Vocals", "vocals", "roformer"),
    ("Instrumental", "instrumental", "roformer"),
    ("Drums", "drums", "rhythm"),
    ("Bass", "bass", "rhythm"),
    ("Other", "guitar", "extra"),   # one 6-stem model; governs guitar/piano/other
]

_CATALOG = None


def _parse(info: dict) -> dict:
    """{stem_name: sdr} for a catalogue model (sdr 0.0 if unlisted)."""
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
    """[(filename, arch, {stem: sdr})], cached. Custom models get their real
    stems (the catalogue reports them as 'Unknown' with no SDR)."""
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG
    from ..core.separator import _make_separator
    data = _make_separator().get_simplified_model_list()
    rows = []
    for fn, info in data.items():
        sdrs = {s: None for s in _CUSTOM_STEMS[fn]} if fn in _CUSTOM_STEMS else _parse(info)
        rows.append((fn, info.get("Type", "?"), sdrs))
    _CATALOG = rows
    return _CATALOG


def _models_for(rows, cstem, engine, current):
    """Right-pane entries for a target. Curated picks (current selection, the
    category default, any custom model producing this stem) pinned first, then
    the catalogue ranked by this stem's SDR. Each entry:
    {fn, sdr, tier, note, current, pinned}."""
    pinned_fns = []
    for fn in [current, ENGINE_MODEL.get(engine), *(_CUSTOM_STEMS.keys())]:
        if not fn or fn in pinned_fns:
            continue
        if fn in _CUSTOM_STEMS and cstem not in _CUSTOM_STEMS[fn]:
            continue
        pinned_fns.append(fn)

    # Prefer the consistent MVSep SDR where we have it; else the catalogue value.
    sdr_of = {}
    for fn, _, sdrs in rows:
        mv = MVSEP_SDR.get(fn, {}).get(cstem)
        if mv is not None:
            sdr_of[fn] = mv
        elif cstem in sdrs:
            sdr_of[fn] = sdrs.get(cstem)
    arch_of = {fn: arch for fn, arch, _ in rows}

    ranked = [fn for fn in sdr_of if fn not in pinned_fns]
    ranked.sort(key=lambda fn: sdr_of[fn] if sdr_of[fn] is not None else -1, reverse=True)

    def entry(fn, pinned):
        return {
            "fn": fn,
            "sdr": sdr_of.get(fn),
            "tier": weight_tier(arch_of.get(fn, ""), fn),
            "note": _NOTES.get(fn, ""),
            "current": fn == current,
            "pinned": pinned,
        }

    return [entry(fn, True) for fn in pinned_fns] + [entry(fn, False) for fn in ranked]


# --- rendering ---

def _entry_label(e, focused_cursor):
    # The widget draws the cursor indicator; we draw only the current-selection dot.
    mark = f"{Colors.SUCCESS}●{Colors.RESET}" if e["current"] else " "
    name = short_name(e["fn"]) if (e["pinned"] or e["fn"] in MODEL_SHORT) else e["fn"]
    name_c = Colors.BOLD if e["pinned"] else Colors.RESET
    sdr = e["sdr"]
    sdr_s = f"{sdr:4.1f}" if isinstance(sdr, (int, float)) and sdr else "   -"
    tier = e["tier"]
    tier_s = f"{_TIER_COLOR.get(tier, Colors.MUTED)}{tier:<4}{Colors.RESET}"
    head = f"{mark} {Colors.PRIMARY}{sdr_s}{Colors.RESET} {tier_s} {name_c}{name}{Colors.RESET}"
    if e["note"]:
        head += f"   {Colors.MUTED}{e['note']}{Colors.RESET}"
    return head


def _left_row(name, is_active, focus_left):
    """Render a left-pane target row. The widget draws the cursor indicator; we
    only colour the active target bold and mute the rest."""
    if is_active:
        return f"{Colors.BOLD if focus_left else ''}{name}{Colors.RESET}"
    return f"{Colors.MUTED}{name}{Colors.RESET}"


def show_model_overlay(selected: list, state: dict) -> None:
    """Tab overlay. Mutates state['models'] (per-category). Loops until Esc."""
    print("\n  Loading model list...")
    try:
        rows = _load_catalog()
    except Exception as e:
        print(f"  Could not load model list: {e}")
        return

    models = state.setdefault("models", {})
    state["one_pass"] = None             # two-pane picker is per-category only

    def left_rows():
        return [(lambda focus, cursor, name=t[0]: _left_row(name, cursor, focus), t, True)
                for t in TARGETS]

    def right_rows(target):
        _, cstem, engine = target
        cur = category_model(engine, state.get("quality", DEFAULT_QUALITY), models)
        entries = _models_for(rows, cstem, engine, cur)
        for e in entries:
            e["_engine"] = engine
        return [(lambda focus, cursor, e=e: _entry_label(e, focus and cursor), e, True)
                for e in entries]

    def on_right_enter(e):
        eng, fn = e["_engine"], e["fn"]
        if fn == ENGINE_MODEL.get(eng):
            models.pop(eng, None)   # back to the built-in default
        else:
            models[eng] = fn

    def search_key(e):
        return f"{e['fn']} {short_name(e['fn'])}"

    pane = TwoPane(
        title="Choose models", subtitle="(SDR = MVSep where available)",
        left_header="Target",
        left_rows=left_rows, right_rows=right_rows,
        on_right_enter=on_right_enter, right_filterable=True,
        search_key=search_key,
        cursor_style="highlight", header_style="bold",
    )
    pane.run()
