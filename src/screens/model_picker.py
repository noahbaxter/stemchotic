"""
Model picker - browse and live-filter all available models.

Shows every model python-audio-separator knows about, tagged with its
architecture and best stem/SDR, so you never have to know a filename. Type to
filter in real time; Enter selects.
"""

import logging

from chotic_ui import Colors, input_with_esc, CancelInput, FilterList


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

    # (label, value) where value is the filename; label carries a dim tag.
    items = [(f"{fn}   {Colors.DIM}{tag}{Colors.RESET}", fn) for fn, tag in models]

    picker = FilterList(
        items,
        title="Pick a model",
        subtitle="Type to filter by name, architecture, or stem.",
        esc_label="Back",
        prompt="Filter",
    )
    return picker.run()
