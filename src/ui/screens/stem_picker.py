"""
Stem picker - the single screen.

One flat list of stems. Space highlights/de-highlights a stem; the live line
below the box shows exactly which model(s) and settings the current selection
resolves to. Enter on "Separate" runs it. "Advanced" lets you override format or
force a specific model directly.
"""

from ..primitives import Colors, input_with_esc, CancelInput
from ..widgets import Menu, MenuItem, MenuDivider
from ...core.engines import STEM_OPTIONS, plan_text


ACTION_SEPARATE = ("action", "separate")
ACTION_ADVANCED = ("action", "advanced")
FORMATS = ["WAV", "FLAC", "MP3"]


def show_stem_picker() -> dict | None:
    """Run the picker. Returns a dict
    {selected: [str], output_format: str, model_override: str|None} or None if quit."""
    selected: set[str] = set()
    output_format = "WAV"
    idx = 0

    while True:
        menu = Menu(
            title="Pick your stems",
            subtitle="Space highlights a stem. Enter on Separate to run.",
            space_hint="Toggle",
            esc_label="Quit",
        )

        for opt in STEM_OPTIONS:
            on = opt.name in selected
            mark = f"{Colors.GREEN}●{Colors.RESET}" if on else f"{Colors.MUTED}○{Colors.RESET}"
            name_col = Colors.GREEN if on else Colors.MUTED
            tag = f"  {Colors.DIM}(experimental){Colors.RESET}" if opt.experimental else ""
            label = f"{mark} {name_col}{opt.name}{Colors.RESET}{tag}"
            menu.add_item(MenuItem(label=label, value=("stem", opt.name)))

        menu.add_item(MenuDivider(pinned=True))
        menu.add_item(MenuItem(
            label=f"{Colors.HOTKEY}▶ Separate selected{Colors.RESET}",
            value=ACTION_SEPARATE, pinned=True,
        ))
        menu.add_item(MenuItem(
            label=f"{Colors.MUTED}⚙ Advanced: output format / pick model directly{Colors.RESET}",
            hotkey="M", value=ACTION_ADVANCED, pinned=True,
        ))

        menu.status_line = f"{plan_text(list(selected))}    |    format: {output_format}"

        result = menu.run(initial_index=idx)
        if result is None:
            return None

        try:
            idx = menu.items.index(result.item)
        except ValueError:
            idx = 0

        val = result.value

        if val == ACTION_SEPARATE:
            if not selected:
                continue
            return {"selected": list(selected), "output_format": output_format, "model_override": None}

        if val == ACTION_ADVANCED:
            adv = _advanced_menu(output_format)
            if adv is None:
                continue
            if adv.get("model_override"):
                return {"selected": list(selected), "output_format": adv["output_format"],
                        "model_override": adv["model_override"]}
            output_format = adv["output_format"]
            continue

        if isinstance(val, tuple) and val[0] == "stem":
            name = val[1]
            selected.discard(name) if name in selected else selected.add(name)
            continue


def _advanced_menu(output_format: str) -> dict | None:
    """Override output format or force a raw model. Returns the (possibly
    changed) settings, or None if backed out without a change."""
    menu = Menu(
        title="Advanced",
        subtitle="Set the output format, or force a specific model and skip the stem logic.",
        esc_label="Back",
    )
    for fmt in FORMATS:
        on = fmt == output_format
        mark = f"{Colors.GREEN}●{Colors.RESET}" if on else f"{Colors.MUTED}○{Colors.RESET}"
        menu.add_item(MenuItem(label=f"{mark} Output format: {fmt}", value=("format", fmt)))
    menu.add_item(MenuDivider())
    menu.add_item(MenuItem(label="Force a specific model filename…", value=("model", None)))

    result = menu.run()
    if result is None:
        return None

    kind, payload = result.value
    if kind == "format":
        return {"output_format": payload, "model_override": None}
    if kind == "model":
        try:
            name = input_with_esc("  Model filename (see `audio-separator --list_models`): ")
        except CancelInput:
            return None
        name = name.strip()
        return {"output_format": output_format, "model_override": name or None}
    return None
