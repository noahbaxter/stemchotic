"""
Model overlay - a two-pane picker for which model each stem type uses.

Opened with Tab from the stem picker. Left pane is the target (Vocals,
Instrumental, Drums, Bass, Guitar/Piano/Other); the right pane lists every model
that can produce that target, our curated picks pinned at the top with a short
"why", then the rest of the catalogue ranked by that stem's SDR. Tab switches
panes, the cursor moves within the focused pane, typing filters the right pane,
Enter sets the focused model for that target. Picks write into the picker state
(per category, session).
"""

import re
import sys

from chotic_ui import Colors, getch, print_header, visible_len, pad_to
from chotic_ui.primitives import cbreak_noecho, KEY_UP, KEY_DOWN, KEY_ENTER, KEY_ESC, KEY_TAB, KEY_BACKSPACE, KEY_SPACE
from chotic_ui.components import box_row, BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_H, BOX_V, BOX_TL_DIV, BOX_TR_DIV
from ..core.engines import CONFIG, ENGINE_MODEL, MODEL_SHORT, _NAME_TO_ENGINE, short_name, weight_tier

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
    ("Guitar / Piano / Other", "guitar", "extra"),
]

_TOP_N = 12
_CATALOG = None


def _body_h(term, n):
    """Visible body rows: enough for the target list and the entries on screen,
    capped to terminal height."""
    return max(len(TARGETS), min(term[1] - 14, max(n, 1)))


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

    sdr_of = {fn: sdrs.get(cstem) for fn, _, sdrs in rows if cstem in sdrs}
    arch_of = {fn: arch for fn, arch, _ in rows}

    ranked = [fn for fn in sdr_of if fn not in pinned_fns]
    ranked.sort(key=lambda fn: sdr_of[fn] if sdr_of[fn] is not None else -1, reverse=True)
    ranked = ranked[:_TOP_N]

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

def _entry_label(e, width, focused_cursor):
    mark = f"{Colors.SUCCESS}●{Colors.RESET}" if e["current"] else (
        f"{Colors.PRIMARY}▸{Colors.RESET}" if focused_cursor else " ")
    name = short_name(e["fn"]) if (e["pinned"] or e["fn"] in MODEL_SHORT) else e["fn"]
    name_c = Colors.BOLD if e["pinned"] else Colors.RESET
    sdr = e["sdr"]
    sdr_s = f"{sdr:4.1f}" if isinstance(sdr, (int, float)) and sdr else "   -"
    tier = e["tier"]
    tier_s = f"{_TIER_COLOR.get(tier, Colors.MUTED)}{tier:<4}{Colors.RESET}"
    head = f"{mark} {Colors.PRIMARY}{sdr_s}{Colors.RESET} {tier_s} {name_c}{name}{Colors.RESET}"
    if e["note"]:
        head += f"   {Colors.MUTED}{e['note']}{Colors.RESET}"
    return pad_to(head, width)


def _frame(target_idx, entries, cursor, scroll, query, focus, cur_fn, term):
    w = max(72, min(term[0] - 2, 110))
    rows_h = _body_h(term, len(entries))
    inner = w - 4
    left_w = 22
    right_w = inner - left_w - 3            # " │ " between columns
    c = Colors.PRIMARY
    lines = [box_row(BOX_TL, BOX_H, BOX_TR, w, c)]

    def row(content):
        pad = inner - visible_len(content)
        lines.append(f"{c}{BOX_V}{Colors.RESET} {content}{' ' * max(0, pad)} {c}{BOX_V}{Colors.RESET}")

    def two(left, right):
        row(f"{pad_to(left, left_w)} {Colors.DIM}{BOX_V}{Colors.RESET} {pad_to(right, right_w)}")

    row(f"{Colors.BOLD}Choose models{Colors.RESET}")
    lines.append(box_row(BOX_TL_DIV, BOX_H, BOX_TR_DIV, w, c))

    n = len(entries)
    filt = f"{Colors.PRIMARY}Filter:{Colors.RESET} {query}{Colors.PRIMARY}▌{Colors.RESET}" if focus == "right" \
        else f"{Colors.MUTED}(type to filter){Colors.RESET}"
    count = f"{Colors.MUTED}{n}{Colors.RESET}"
    pad = right_w - visible_len(filt) - visible_len(count)
    two(f"{Colors.BOLD}Target{Colors.RESET}", f"{filt}{' ' * max(1, pad)}{count}")
    lines.append(box_row(BOX_TL_DIV, BOX_H, BOX_TR_DIV, w, c))

    end = min(n, scroll + rows_h)
    for r in range(rows_h):
        # left column: the target list (only the first len(TARGETS) rows)
        if r < len(TARGETS):
            t = TARGETS[r][0]
            if r == target_idx:
                mk = f"{Colors.PRIMARY}▸{Colors.RESET}" if focus == "left" else f"{Colors.SUCCESS}•{Colors.RESET}"
                left = f"{mk} {Colors.BOLD if focus == 'left' else ''}{t}{Colors.RESET}"
            else:
                left = f"  {Colors.MUTED}{t}{Colors.RESET}"
        else:
            left = ""
        # right column: scrolled entry window
        idx = scroll + r
        if r == 0 and scroll > 0:
            right = f"{Colors.MUTED}  ▲ {scroll} above{Colors.RESET}"
        elif r == rows_h - 1 and end < n:
            right = f"{Colors.MUTED}  ▼ {n - end} below{Colors.RESET}"
        elif idx < n:
            right = _entry_label(entries[idx], right_w, focus == "right" and idx == cursor)
        else:
            right = ""
        two(left, right)

    lines.append(box_row(BOX_BL, BOX_H, BOX_BR, w, c))
    lines.append(f"  {Colors.PRIMARY}Tab{Colors.MUTED} switch pane  {Colors.PRIMARY}↑/↓{Colors.MUTED} move  "
                 f"{Colors.PRIMARY}Enter{Colors.MUTED} set  {Colors.PRIMARY}Esc{Colors.MUTED} done  "
                 f"{Colors.DIM}(type to filter the right){Colors.RESET}")

    out = sys.__stdout__ if sys.__stdout__ else sys.stdout
    out.write("\033[H\033[J")
    print_header()
    out.write("\n".join(lines).replace("\n", "\033[K\n") + "\033[J\033[3J")
    out.flush()


def show_model_overlay(selected: list, state: dict) -> None:
    """Tab overlay. Mutates state['models'] (per-category). Loops until Esc."""
    print("\n  Loading model list...")
    try:
        rows = _load_catalog()
    except Exception as e:
        print(f"  Could not load model list: {e}")
        return

    import shutil
    models = state.setdefault("models", {})
    state["one_pass"] = None             # two-pane picker is per-category only

    target_idx, focus, cursor, scroll, query = 0, "left", 0, 0, ""

    def build():
        title, cstem, engine = TARGETS[target_idx]
        cur = models.get(engine, ENGINE_MODEL[engine])
        entries = _models_for(rows, cstem, engine, cur)
        if query:
            q = query.lower()
            entries = [e for e in entries
                       if q in e["fn"].lower() or q in short_name(e["fn"]).lower()]
        return entries, cur

    with cbreak_noecho():
        while True:
            entries, cur = build()
            cursor = max(0, min(cursor, len(entries) - 1)) if entries else 0
            term = shutil.get_terminal_size((80, 24))
            rows_h = _body_h(term, len(entries))
            if cursor < scroll:
                scroll = cursor
            elif cursor >= scroll + rows_h:
                scroll = cursor - rows_h + 1
            scroll = max(0, min(scroll, max(0, len(entries) - rows_h)))

            _frame(target_idx, entries, cursor, scroll, query, focus, cur, term)

            key = getch(return_special_keys=True)
            if key == KEY_ESC:
                return
            if key == KEY_TAB:
                focus = "right" if focus == "left" else "left"
            elif key == KEY_UP:
                if focus == "left":
                    target_idx = max(0, target_idx - 1)
                    cursor = scroll = 0
                    query = ""
                else:
                    cursor = max(0, cursor - 1)
            elif key == KEY_DOWN:
                if focus == "left":
                    target_idx = min(len(TARGETS) - 1, target_idx + 1)
                    cursor = scroll = 0
                    query = ""
                else:
                    cursor = min(len(entries) - 1, cursor + 1) if entries else 0
            elif key == KEY_ENTER:
                if focus == "left":
                    focus = "right"
                elif entries:
                    _, _, engine = TARGETS[target_idx]
                    fn = entries[cursor]["fn"]
                    if fn == ENGINE_MODEL.get(engine):
                        models.pop(engine, None)   # back to the built-in default
                    else:
                        models[engine] = fn
            elif key == KEY_BACKSPACE:
                if focus == "right":
                    query = query[:-1]
                    cursor = scroll = 0
            elif key == KEY_SPACE:
                if focus == "right":
                    query += " "
                    cursor = scroll = 0
            elif isinstance(key, str) and len(key) == 1 and key.isprintable():
                focus = "right"
                query += key
                cursor = scroll = 0
