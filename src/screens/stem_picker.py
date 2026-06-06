"""
Stem picker - the single screen.

One flat list of stems. Space highlights/de-highlights a stem; the live line
below the box shows exactly which model(s) and settings the current selection
resolves to. Enter on "Separate" runs it. "Advanced" lets you set the output
format or browse/pick any model directly.

Selection state lives in the caller-owned `state` dict so it survives backing
out of the file prompt and returning after a run - it only clears when the app
closes.
"""

from chotic_ui import Colors, Menu, MenuItem, MenuDivider
from ..core.engines import STEM_OPTIONS, plan_text, model_label
from .model_picker import show_model_picker


ACTION_SEPARATE = ("action", "separate")
ACTION_FORMAT = ("action", "format")
ACTION_MODEL = ("action", "model")
FORMATS = ["WAV", "FLAC", "MP3"]


def _layout():
    """Row order with the kit pieces nested as a tree under Drums.
    Returns (StemOption, connector) where connector is '' for top-level rows or
    a tree glyph for nested kit pieces."""
    kit = [o for o in STEM_OPTIONS if o.engine == "kit"]
    rows = []
    for opt in STEM_OPTIONS:
        if opt.engine == "kit":
            continue
        rows.append((opt, ""))
        if opt.name == "Drums":
            for i, k in enumerate(kit):
                rows.append((k, "└" if i == len(kit) - 1 else "├"))
    return rows


def new_state() -> dict:
    """Fresh, session-long picker state."""
    return {"selected": set(), "output_format": "WAV", "idx": 0}


def show_stem_picker(state: dict) -> dict | None:
    """Run the picker against persistent `state`. Returns a run request
    {selected, output_format, model_override} or None if quit."""
    selected: set = state["selected"]
    idx = state.get("idx", 0)

    while True:
        output_format = state["output_format"]
        menu = Menu(
            title="Pick your stems",
            subtitle="Enter or Space to pick stems  ·  then choose Start splitting",
            space_hint="Pick",
            esc_label="Quit",
            column_header=f"{Colors.MUTED}model{Colors.RESET}",
        )

        for opt, connector in _layout():
            on = opt.name in selected
            mark = f"{Colors.GREEN}●{Colors.RESET}" if on else f"{Colors.MUTED}○{Colors.RESET}"
            name_col = Colors.GREEN if on else Colors.MUTED
            prefix = f"   {Colors.DIM}{connector}{Colors.RESET} " if connector else ""
            menu.add_item(MenuItem(label=f"{prefix}{mark} {name_col}{opt.name}{Colors.RESET}",
                                   value=("stem", opt.name),
                                   description=model_label(opt.name)))

        # Settings (inline, no nested screen), then the proceed action LAST.
        menu.add_item(MenuDivider(pinned=True))
        menu.add_item(MenuItem(
            label=f"{Colors.MUTED}Output format:{Colors.RESET} {output_format}  {Colors.DIM}(Enter cycles){Colors.RESET}",
            value=ACTION_FORMAT, pinned=True))
        menu.add_item(MenuItem(
            label=f"{Colors.MUTED}Pick a specific model…{Colors.RESET}",
            hotkey="M", value=ACTION_MODEL, pinned=True))
        menu.add_item(MenuDivider(pinned=True))
        menu.add_item(MenuItem(
            label=f"{Colors.HOTKEY}Start splitting{Colors.RESET}  {Colors.DIM}→ choose audio file{Colors.RESET}",
            value=ACTION_SEPARATE, pinned=True))

        menu.status_line = f"{plan_text(list(selected))}    |    format: {output_format}"

        result = menu.run(initial_index=idx)
        if result is None:
            state["idx"] = idx
            return None

        try:
            idx = menu.items.index(result.item)
        except ValueError:
            idx = 0
        state["idx"] = idx

        val = result.value

        if val == ACTION_FORMAT:
            i = FORMATS.index(output_format) if output_format in FORMATS else 0
            state["output_format"] = FORMATS[(i + 1) % len(FORMATS)]
            continue

        if val == ACTION_MODEL:
            chosen = show_model_picker()
            if chosen:
                return {"selected": list(selected), "output_format": output_format, "model_override": chosen}
            continue

        if val == ACTION_SEPARATE:
            if not selected:
                continue
            return {"selected": list(selected), "output_format": output_format, "model_override": None}

        if isinstance(val, tuple) and val[0] == "stem":
            # Enter and Space both just toggle; splitting only starts via Start splitting.
            name = val[1]
            selected.discard(name) if name in selected else selected.add(name)
