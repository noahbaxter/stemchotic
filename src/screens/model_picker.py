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

import hashlib
import json
import os
import re
import threading

from chotic_ui import Colors, TwoPane
from ..core.engines import (CONFIG, DRUMSEP_SDR, ENGINE_MODEL, KIT_LAYOUTS, MODEL_SHORT,
                            MVSEP_SDR, _NAME_TO_ENGINE, category_model, short_name,
                            weight_tier, DEFAULT_QUALITY)

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
    ("Drum kit", "_kit", "kit"),    # sentinel cstem: list DrumSep models directly
]

_CATALOG = None
_CATALOG_LOCK = threading.Lock()
_CATALOG_SCHEMA = 1   # bump when the row shape or custom-model handling changes


def _catalog_cache_file() -> str:
    from ..core.separator import models_dir
    return os.path.join(models_dir(), ".catalog.json")


def _audio_separator_version() -> str:
    try:
        from importlib.metadata import version
        return version("audio-separator")
    except Exception:
        return "?"


def _catalog_fingerprint() -> dict:
    """What the cached catalogue depends on. The model list changes only when
    audio-separator upgrades (its bundled jsons) or when we add/change custom
    models, so the cache is reused for everything else and rebuilt when either
    of these moves."""
    custom = hashlib.sha256(json.dumps(_CUSTOM_STEMS, sort_keys=True).encode()).hexdigest()[:12]
    return {"schema": _CATALOG_SCHEMA, "as": _audio_separator_version(), "custom": custom}


def _read_catalog_cache():
    """Cached rows if the cache still matches the fingerprint, else None. Rows
    come back as lists (JSON), which unpack like the tuples."""
    try:
        with open(_catalog_cache_file(), encoding="utf-8") as f:
            blob = json.load(f)
        fp = _catalog_fingerprint()
        if all(blob.get(k) == v for k, v in fp.items()):
            return blob["rows"]
    except Exception:
        pass
    return None


def _write_catalog_cache(rows) -> None:
    try:
        path = _catalog_cache_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({**_catalog_fingerprint(), "rows": rows}, f)
        os.replace(tmp, path)
    except Exception:
        pass   # caching is best-effort; a write failure just means a slow next load


def _kit_entries(current):
    """Right-pane entries for the Drum kit target: the distinct DrumSep models
    (deduped across KIT_LAYOUTS), each carrying its per-piece SDR. Not ranked by
    a catalogue stem; sorted by the kick score for display."""
    seen, out = set(), []
    for lay in KIT_LAYOUTS.values():
        fn = lay["model"]
        if fn in seen:
            continue
        seen.add(fn)
        pieces = DRUMSEP_SDR.get(fn, {})
        out.append({"fn": fn, "sdr": pieces.get("kick"), "arch": "MDXC",
                    "tier": weight_tier("MDXC", fn), "note": _NOTES.get(fn, ""),
                    "current": fn == current, "pinned": True, "_engine": "kit",
                    "_pieces": pieces})
    out.sort(key=lambda e: e["sdr"] or 0, reverse=True)
    return out


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
    # Lock so the background startup preload and an M-press can't both build the
    # catalogue (each constructs a heavy Separator) at once.
    with _CATALOG_LOCK:
        if _CATALOG is not None:
            return _CATALOG
        cached = _read_catalog_cache()
        if cached is not None:
            _CATALOG = cached            # instant: no Separator/torch on repeat launches
            return _CATALOG
        from ..core.separator import _make_separator
        data = _make_separator().get_simplified_model_list()
        rows = []
        for fn, info in data.items():
            sdrs = {s: None for s in _CUSTOM_STEMS[fn]} if fn in _CUSTOM_STEMS else _parse(info)
            rows.append((fn, info.get("Type", "?"), sdrs))
        _CATALOG = rows
        _write_catalog_cache(rows)
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
            "arch": arch_of.get(fn, ""),
            "tier": weight_tier(arch_of.get(fn, ""), fn),
            "note": _NOTES.get(fn, ""),
            "current": fn == current,
            "pinned": pinned,
        }

    return [entry(fn, True) for fn in pinned_fns] + [entry(fn, False) for fn in ranked]


def _family(fn, arch):
    """Group a model into a coarse architecture family, used to pick one
    best-SDR champion per family for the collapsed view."""
    f = fn.lower()
    if "bs-rofo" in f or "bs_roformer" in f:
        return "BS-RoFormer"
    if "melband" in f or "mel_band" in f or "mel-band" in f:
        return "MelBand-RoFormer"
    if "mdx23c" in f:
        return "MDX23C"
    if "demucs" in f:
        return "Demucs"
    if arch == "VR" or f.endswith(".pth"):
        return "VR"
    if "mdx" in f or "mdxnet" in f or arch in ("MDX",):
        return "UVR-MDX"
    if "kuielab" in f:
        return "UVR-MDX"
    return "Other"


def _collapsed(rows, cstem, engine, current):
    """Collapsed right-pane entries: the pinned curated picks plus the single
    highest-SDR model of each architecture family for this stem (deduped, in
    SDR-desc order). Reuses _models_for for the full ranked list."""
    full = _models_for(rows, cstem, engine, current)
    pinned = [e for e in full if e["pinned"]]
    rest = [e for e in full if not e["pinned"]]
    seen, champs = set(), []
    for e in rest:                      # rest is already SDR-desc sorted
        fam = _family(e["fn"], e["arch"])
        if fam in seen:
            continue
        seen.add(fam)
        champs.append(e)
    return pinned + champs


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
    # The note lives in the detail line (full width), not crammed into the row.
    return f"{mark} {Colors.PRIMARY}{sdr_s}{Colors.RESET} {tier_s} {name_c}{name}{Colors.RESET}"


def _detail(e):
    """Full-width help line for the focused model: friendly name, its note (the
    'why'), and the raw filename, none of it truncated in-column."""
    if not isinstance(e, dict):
        return ""
    parts = [f"{Colors.BOLD}{short_name(e['fn'])}{Colors.RESET}"]
    if e["note"]:
        parts.append(f"{Colors.MUTED}{e['note']}{Colors.RESET}")
    if e.get("_pieces"):                # kit entry: show per-piece DrumSep-dataset SDR
        scores = "  ".join(f"{name} {sdr:.1f}" for name, sdr in e["_pieces"].items())
        parts.append(f"{Colors.PRIMARY}{scores}{Colors.RESET}")
    else:
        parts.append(f"{Colors.DIM}{e['fn']}{Colors.RESET}")
    return "  ·  ".join(parts)


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

    view = {"all": False}                # collapsed by default; toggled by the rows below
    SHOW_ALL = ("show_all",)
    SHOW_FEWER = ("show_fewer",)

    def left_rows():
        return [(lambda focus, cursor, name=t[0]: _left_row(name, cursor, focus), t, True)
                for t in TARGETS]

    def _entry_row(e, engine):
        e["_engine"] = engine
        return (lambda focus, cursor, e=e: _entry_label(e, focus and cursor), e, True)

    def right_rows(target, query):
        _, cstem, engine = target
        if cstem == "_kit":             # not a catalogue stem: list DrumSep models directly
            cur = models.get("kit", KIT_LAYOUTS["5"]["model"])
            return [_entry_row(e, "kit") for e in _kit_entries(cur)]
        cur = category_model(engine, state.get("quality", DEFAULT_QUALITY), models)
        full = _models_for(rows, cstem, engine, cur)
        n = len(full)
        if query:
            # Searching always hits the full catalogue; the widget filters it. No toggle.
            return [_entry_row(e, engine) for e in full]
        if view["all"]:
            toggle = (lambda f, c: f"{Colors.MUTED}Show top picks only{Colors.RESET}", SHOW_FEWER, True)
            return [toggle] + [_entry_row(e, engine) for e in full]
        entries = _collapsed(rows, cstem, engine, cur)
        toggle = (lambda f, c: f"{Colors.MUTED}Show all {n} models{Colors.RESET}", SHOW_ALL, True)
        return [_entry_row(e, engine) for e in entries] + [toggle]

    def on_right_enter(val):
        if val == SHOW_ALL:
            view["all"] = True
            return
        if val == SHOW_FEWER:
            view["all"] = False
            return
        eng, fn = val["_engine"], val["fn"]
        default = KIT_LAYOUTS["5"]["model"] if eng == "kit" else ENGINE_MODEL.get(eng)
        if fn == default:
            models.pop(eng, None)   # back to the built-in default
        else:
            models[eng] = fn

    def search_key(val):
        if not isinstance(val, dict):
            return ""
        return f"{val['fn']} {short_name(val['fn'])}"

    pane = TwoPane(
        title="Choose models",
        subtitle="(SDR = MVSep where available; Drum kit scores are DrumSep-dataset)",
        left_header="Target",
        left_rows=left_rows, right_rows=right_rows,
        on_right_enter=on_right_enter, right_filterable=True,
        search_key=search_key, detail=_detail,
        cursor_style="highlight", header_style="bold",
    )
    pane.run()
