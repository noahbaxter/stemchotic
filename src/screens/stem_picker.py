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
from ..core.engines import STEM_OPTIONS, plan_text, display_model, short_name, DEFAULT_QUALITY
from .model_picker import show_model_overlay


ACTION_SEPARATE = ("action", "separate")
ACTION_FORMAT = ("action", "format")
ACTION_MODEL = ("action", "model")
ACTION_QUALITY = ("action", "quality")
ACTION_SCOPE = ("action", "scope")
FORMATS = ["WAV", "FLAC", "MP3"]
QUALITIES = ["best", "fast"]
_QUALITY_LABEL = {"best": "Best", "fast": "Fast"}
_SCOPE_LABEL = {False: "My picks", True: "Everything the models make"}


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
    return {"selected": set(), "output_format": "WAV", "idx": 0, "models": {},
            "one_pass": None, "quality": DEFAULT_QUALITY, "keep_all": False}


def show_stem_picker(state: dict) -> dict | None:
    """Run the picker against persistent `state`. Returns a run request
    {selected, output_format, models, one_pass} or None if quit."""
    selected: set = state["selected"]
    idx = state.get("idx", 0)

    while True:
        output_format = state["output_format"]
        models = state.setdefault("models", {})
        one_pass = state.get("one_pass")
        quality = state.setdefault("quality", DEFAULT_QUALITY)
        keep_all = state.setdefault("keep_all", False)
        menu = Menu(
            title="Pick your stems",
            subtitle="Space to pick stems  ·  Tab to choose models  ·  Start splitting to run",
            space_hint="Pick",
            esc_label="Quit",
            column_header=f"{Colors.MUTED}model{Colors.RESET}",
        )

        def build(m):
            # Labels bake in color escapes, so this reruns on theme switch.
            m.items.clear()
            for opt, connector in _layout():
                on = opt.name in selected
                mark = f"{Colors.SUCCESS}●{Colors.RESET}" if on else f"{Colors.MUTED}○{Colors.RESET}"
                name_col = Colors.SUCCESS if on else Colors.MUTED
                prefix = f"   {Colors.DIM}{connector}{Colors.RESET} " if connector else ""
                shown = short_name(one_pass) if one_pass else display_model(opt.name, models, quality)
                m.add_item(MenuItem(label=f"{prefix}{mark} {name_col}{opt.name}{Colors.RESET}",
                                    value=("stem", opt.name),
                                    description=shown))

            # Settings (inline), then the proceed action LAST.
            m.add_item(MenuDivider(pinned=True))
            m.add_item(MenuItem(
                label=f"{Colors.MUTED}Output format:{Colors.RESET} {output_format}  {Colors.DIM}(Enter cycles){Colors.RESET}",
                value=ACTION_FORMAT, pinned=True))
            m.add_item(MenuItem(
                label=f"{Colors.MUTED}Quality:{Colors.RESET} {_QUALITY_LABEL[quality]}  {Colors.DIM}(Enter cycles){Colors.RESET}",
                value=ACTION_QUALITY, pinned=True))
            m.add_item(MenuItem(
                label=f"{Colors.MUTED}Output:{Colors.RESET} {_SCOPE_LABEL[keep_all]}  {Colors.DIM}(Enter cycles){Colors.RESET}",
                value=ACTION_SCOPE, pinned=True))
            m.add_item(MenuItem(
                label=f"{Colors.MUTED}Choose models{Colors.RESET}  {Colors.DIM}(Tab){Colors.RESET}",
                hotkey="M", value=ACTION_MODEL, pinned=True))
            m.add_item(MenuDivider(pinned=True))
            m.add_item(MenuItem(
                label=f"{Colors.PRIMARY}Start splitting{Colors.RESET}  {Colors.DIM}→ choose audio file{Colors.RESET}",
                value=ACTION_SEPARATE, pinned=True))

            m.status_line = (f"{plan_text(list(selected), models, one_pass, quality, keep_all)}"
                             f"    |    format: {output_format}  ·  quality: {_QUALITY_LABEL[quality]}")

        menu.rebuild = build
        build(menu)

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

        # Tab anywhere, or selecting "Choose models", opens the model overlay.
        if result.action == "tab" or val == ACTION_MODEL:
            show_model_overlay(list(selected), state)
            continue

        if val == ACTION_FORMAT:
            i = FORMATS.index(output_format) if output_format in FORMATS else 0
            state["output_format"] = FORMATS[(i + 1) % len(FORMATS)]
            continue

        if val == ACTION_QUALITY:
            i = QUALITIES.index(quality) if quality in QUALITIES else 0
            state["quality"] = QUALITIES[(i + 1) % len(QUALITIES)]
            continue

        if val == ACTION_SCOPE:
            state["keep_all"] = not keep_all
            continue

        if val == ACTION_SEPARATE:
            if not selected:
                continue
            return {"selected": list(selected), "output_format": output_format,
                    "models": dict(models), "one_pass": state.get("one_pass"),
                    "quality": quality, "keep_all": keep_all}

        if isinstance(val, tuple) and val[0] == "stem":
            # Enter and Space both just toggle; splitting only starts via Start splitting.
            name = val[1]
            selected.discard(name) if name in selected else selected.add(name)
