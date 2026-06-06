"""
Model picker - browse and filter all available models.

Shows every model python-audio-separator knows about, tagged with its
architecture and best stem/SDR, so you never have to know a filename. Press `/`
to filter by typing; Enter selects.
"""

import logging

from ..primitives import Colors, input_with_esc, CancelInput
from ..widgets import Menu, MenuItem


_MODEL_CACHE = None


def _tag(info: dict) -> str:
    """Short 'what is this good for' tag from a model's metadata."""
    typ = info.get("Type", "?")
    stems = info.get("Stems", []) or []
    primary = next((s for s in stems if "*" in s), stems[0] if stems else "")
    primary = primary.replace("*", "").strip()
    return f"{typ}  ·  {primary}" if primary else typ


def _load_models():
    """Load and cache the (filename, tag) list. May hit the network on first call."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    from audio_separator.separator import Separator

    sep = Separator(log_level=logging.ERROR)
    data = sep.get_simplified_model_list()
    entries = [(fn, _tag(info)) for fn, info in data.items()]
    entries.sort(key=lambda e: e[0].lower())
    _MODEL_CACHE = entries
    return entries


def show_model_picker() -> str | None:
    """Browse/filter models. Returns the chosen model filename, or None if backed out."""
    print("\n  Loading model list...")
    try:
        models = _load_models()
    except Exception as e:
        print(f"  Could not load model list: {e}")
        try:
            input_with_esc("  Press Enter... ")
        except CancelInput:
            pass
        return None

    filter_str = ""
    idx = 0

    while True:
        f = filter_str.lower()
        matches = [m for m in models if f in (m[0] + " " + m[1]).lower()] if f else models

        sub = f"{len(matches)} of {len(models)} models"
        sub += f"   ·   filter: '{filter_str}'" if filter_str else "   ·   press / to filter"
        menu = Menu(title="Pick a model", subtitle=sub, esc_label="Back")

        menu.add_item(MenuItem(label=f"{Colors.HOTKEY}/ Filter...{Colors.RESET}",
                               hotkey="/", value=("filter", None), pinned=True))
        if filter_str:
            menu.add_item(MenuItem(label=f"{Colors.MUTED}Clear filter{Colors.RESET}",
                                   value=("clear", None), pinned=True))

        for fn, tag in matches:
            menu.add_item(MenuItem(label=f"{fn}   {Colors.DIM}{tag}{Colors.RESET}", value=("model", fn)))

        result = menu.run(initial_index=idx)
        if result is None:
            return None

        try:
            idx = menu.items.index(result.item)
        except ValueError:
            idx = 0

        kind, payload = result.value
        if kind == "model":
            return payload
        if kind == "filter":
            try:
                filter_str = input_with_esc("  Filter: ").strip()
            except CancelInput:
                pass
            idx = 0
        elif kind == "clear":
            filter_str = ""
            idx = 0
