"""
Main screen - a two-pane stems-and-settings view.

LEFT pane is the stem checklist (Space/Enter toggles a stem) plus a pinned
`+ Residual` toggle. Each stem row shows its resolved model. RIGHT pane is the
settings: Output (Format/Quality/Scope) and, only when Drums is picked, Drum kit
(Split/Source). Settings rows cycle on Space/Enter; section headers are skipped.

M opens the model overlay, S starts splitting, Tab switches panes, Esc quits.

Selection + settings live in the caller-owned `state` dict so they survive
backing out of the file prompt and returning after a run - they only clear when
the app closes.
"""

from chotic_ui import Colors, TwoPane, visible_len
from ..core import device, prefs
from ..core.engines import STEM_OPTIONS, plan_text, display_model, short_name, DEFAULT_QUALITY
from ..core.updates import launcher_outdated, RELEASES_URL
from .model_picker import show_model_overlay

_LEFT_W = 40   # left pane width; wide enough for the stem name + its model column


FORMATS = ["WAV", "FLAC", "MP3"]
QUALITIES = ["best", "fast"]
KIT_SPLITS = ["off", "4", "5", "6"]
KIT_SOURCES = ["song", "stem"]
# Faintest readable shade for a shown-but-inert row: the DIM attribute over the
# darkest palette grey. Used for the greyed-out Drum Options when Drums is unpicked.
_FADE = Colors.DIM + Colors.MUTED_DIM
_QUALITY_LABEL = {"best": "Best", "fast": "Fast"}
_SOURCE_LABEL = {"song": "Song", "stem": "Drum stem"}
_SOURCE_HINT = {
    "song": "Song: extract drums from the mix, then split the kit",
    "stem": "Drum stem: input is already a drum stem, split it directly",
}

# Right-pane row values.
SECTION = ("section",)           # non-selectable header sentinel
SET_FORMAT = ("set", "format")
SET_QUALITY = ("set", "quality")
SET_SCOPE = ("set", "scope")
SET_SPLIT = ("set", "split")
SET_SOURCE = ("set", "source")
SET_DEVICE = ("set", "device")
_DEVICE_LABEL = {"gpu": "GPU", "cpu": "CPU"}

# Left-pane row values.
ROW_RESIDUAL = ("residual",)


def new_state() -> dict:
    """Fresh picker state. Saved settings + per-stem model picks are restored;
    stem selection and one-pass always start empty."""
    state = {"selected": set(), "output_format": "WAV", "models": {},
             "one_pass": None, "quality": DEFAULT_QUALITY, "keep_all": False,
             "residual": False, "kit_split": "off", "kit_source": "song"}
    state.update(prefs.load())
    return state


def _cycle(seq, cur):
    i = seq.index(cur) if cur in seq else 0
    return seq[(i + 1) % len(seq)]


def show_stem_picker(state: dict) -> dict | None:
    """Run the Main two-pane against persistent `state`. Returns a run request
    {selected, output_format, models, one_pass, quality, keep_all, residual,
    kit_split, kit_source} on Start, or None if quit."""
    selected: set = state["selected"]
    state.setdefault("models", {})
    state.setdefault("quality", DEFAULT_QUALITY)
    state.setdefault("keep_all", False)
    state.setdefault("residual", False)
    state.setdefault("kit_split", "off")
    state.setdefault("kit_source", "song")

    while True:
        pane = _build_pane(state)
        ret = pane.run()
        prefs.save(state)   # persist any setting/model change from this interaction
        if ret is None:
            return None
        ret = ret.lower()
        if ret == "m":
            show_model_overlay(list(selected), state)
            continue   # rebuild fresh so model labels reflect any change
        if ret == "s":
            keep_all = state["keep_all"]
            residual = state["residual"] and not keep_all   # exclusion
            return {
                "selected": list(selected),
                "output_format": state["output_format"],
                "models": dict(state["models"]),
                "one_pass": state.get("one_pass"),
                "quality": state["quality"],
                "keep_all": keep_all,
                "residual": residual,
                "kit_split": state["kit_split"],
                "kit_source": state["kit_source"],
            }


def _build_pane(state: dict) -> TwoPane:
    # Only the stable mutable refs are captured. Every volatile scalar
    # (quality, one_pass, kit_source) is read from `state` live inside the
    # per-frame closures, so a setting change shows immediately instead of
    # waiting for the pane to be rebuilt.
    selected: set = state["selected"]
    models = state["models"]
    # Compute toggle: a CPU fallback for GPU installs. Read once (switching
    # re-execs the process, so it can't change within this pane's lifetime).
    dev_available = device.gpu_toggle_available()
    dev_pref = device.read_device_pref()

    # --- left pane: stems + Residual ---
    def left_rows():
        quality = state["quality"]
        one_pass = state.get("one_pass")
        rows = [(_stem_render(opt, selected, models, quality, one_pass),
                 ("stem", opt.name), True) for opt in STEM_OPTIONS]
        rows.append((_residual_render(state), ROW_RESIDUAL, True))
        return rows

    def on_left_enter(val):
        if val == ROW_RESIDUAL:
            if state["keep_all"]:
                return   # disabled: Everything already gives every stem
            state["residual"] = not state["residual"]
        elif isinstance(val, tuple) and val[0] == "stem":
            name = val[1]
            selected.discard(name) if name in selected else selected.add(name)

    # --- right pane: settings (each row shows its options inline, active one lit) ---
    def right_rows(_left, _query=""):
        scope = "Everything" if state["keep_all"] else "My picks"
        split = "Off" if state["kit_split"] == "off" else state["kit_split"]
        source = _SOURCE_LABEL[state["kit_source"]]
        drums_on = "Drums" in selected
        hdr = f"{Colors.MUTED}{Colors.BOLD}" if drums_on else _FADE   # header fades with the group
        rows = [
            (_opt_render("Format", FORMATS, state["output_format"]), SET_FORMAT, True),
            (_opt_render("Quality", ["Best", "Fast"], _QUALITY_LABEL[state["quality"]]), SET_QUALITY, True),
            (_opt_render("Scope", ["My picks", "Everything"], scope), SET_SCOPE, True),
            (lambda f, c: "", SECTION, False),   # blank spacer, no dashes
            (lambda f, c: f"  {hdr}Drum Options{Colors.RESET}", SECTION, False),
        ]
        if drums_on:
            rows += [
                (_opt_render("Split", ["Off", "4", "5", "6"], split), SET_SPLIT, True),
                (_opt_render("Input", ["Song", "Drum stem"], source), SET_SOURCE, True),
                (lambda f, c: f"  {Colors.DIM}{_SOURCE_HINT[state['kit_source']]}{Colors.RESET}", SECTION, False),
            ]
        else:
            # Shown but inert until Drums is a chosen stem (the engine ignores
            # these unless Drums is selected, so a persisted value can't leak in).
            rows += [
                (_opt_render("Split", ["Off", "4", "5", "6"], split, disabled=True), SECTION, False),
                (_opt_render("Input", ["Song", "Drum stem"], source, disabled=True), SECTION, False),
                (lambda f, c: f"  {_FADE}Select Drums to enable{Colors.RESET}", SECTION, False),
            ]
        if dev_available:
            rows += [
                (lambda f, c: "", SECTION, False),
                (_opt_render("Compute", ["GPU", "CPU"], _DEVICE_LABEL[dev_pref]), SET_DEVICE, True),
            ]
        return rows

    def on_right_enter(val):
        if val == SET_FORMAT:
            state["output_format"] = _cycle(FORMATS, state["output_format"])
        elif val == SET_QUALITY:
            state["quality"] = _cycle(QUALITIES, state["quality"])
        elif val == SET_SCOPE:
            state["keep_all"] = not state["keep_all"]
        elif val == SET_SPLIT:
            state["kit_split"] = _cycle(KIT_SPLITS, state["kit_split"])
        elif val == SET_SOURCE:
            state["kit_source"] = _cycle(KIT_SOURCES, state["kit_source"])
        elif val == SET_DEVICE:
            # Persist pending changes first: switch_device re-execs and never returns.
            prefs.save(state)
            device.switch_device("cpu" if dev_pref == "gpu" else "gpu")

    def footer():
        # Recomputed each frame so the plan reflects live toggles.
        plan = plan_text(list(selected), models, state.get("one_pass"), state["quality"],
                         state["keep_all"], state["kit_split"], state["kit_source"],
                         state["residual"] and not state["keep_all"])
        keys = (f"  {Colors.PRIMARY}Tab{Colors.MUTED} panes  "
                f"{Colors.PRIMARY}Space{Colors.MUTED} pick/change  "
                f"{Colors.PRIMARY}M{Colors.MUTED} models  "
                f"{Colors.PRIMARY}S{Colors.MUTED} start splitting  "
                f"{Colors.PRIMARY}Esc{Colors.MUTED} quit{Colors.RESET}")
        rows = []
        if launcher_outdated():   # frozen launcher behind the app; WezTerm linkifies the URL
            rows.append(f"  {Colors.INFO}{Colors.BOLD}New launcher available, re-download:{Colors.RESET}"
                        f"{Colors.INFO} {RELEASES_URL}{Colors.RESET}")
        rows.append(keys)
        rows.append(f"  {Colors.DIM}{plan}{Colors.RESET}")
        return "\n".join(rows)

    return TwoPane(
        title="Stemchotic", subtitle="Space picks stems  ·  M for models  ·  S to split",
        left_header="Stem Selection", right_header="Settings", show_count=False,
        left_width=_LEFT_W,
        left_rows=left_rows, right_rows=right_rows,
        on_left_enter=on_left_enter, on_right_enter=on_right_enter,
        right_filterable=False,
        keys={"m": lambda: "return", "M": lambda: "return",
              "s": lambda: "return", "S": lambda: "return"},
        footer=footer, left_enter_focuses_right=False,
        cursor_style="highlight", header_style="bold",
    )


# --- row renderers ---

def _stem_render(opt, selected, models, quality, one_pass):
    def render(focus, cursor):
        on = opt.name in selected
        mark = f"{Colors.SUCCESS}●{Colors.RESET}" if on else f"{Colors.MUTED}○{Colors.RESET}"
        name_c = Colors.SUCCESS if on else Colors.MUTED
        left = f"{mark} {name_c}{opt.name}{Colors.RESET}"
        # Model in its own right-aligned column (the dedicated "model" space).
        shown = short_name(one_pass) if one_pass else display_model(opt.name, models, quality)
        model = f"{Colors.MUTED}{shown}{Colors.RESET}"
        # The widget reserves a 2-col cursor gutter, so our budget is _LEFT_W - 2.
        gap = _LEFT_W - 2 - visible_len(left) - visible_len(model) - 1
        return f"{left}{' ' * max(1, gap)}{model}"
    return render


def _residual_render(state):
    def render(focus, cursor):
        if state["keep_all"]:
            return f"{Colors.DIM}+ Residual  (off: Scope){Colors.RESET}"
        on = state["residual"]
        mark = f"{Colors.SUCCESS}●{Colors.RESET}" if on else f"{Colors.MUTED}○{Colors.RESET}"
        name_c = Colors.SUCCESS if on else Colors.MUTED
        return f"{mark} {name_c}+ Residual{Colors.RESET}"
    return render


def _opt_render(label, options, current, disabled=False):
    """A setting row: label, then every option inline with the active one lit
    (accent + bold) and the rest muted. Enter/Space advances to the next.
    `disabled` renders the whole row in a uniform faint fade (no active accent)
    for a shown-but-inert setting."""
    def render(focus, cursor):
        if disabled:                          # uniform faint fade, no active-option accent
            segs = [f"{_FADE}{o}{Colors.RESET}" for o in options]
            return f"{_FADE}{label:<8}{Colors.RESET}" + "  ".join(segs)
        segs = [(f"{Colors.PRIMARY}{Colors.BOLD}{o}{Colors.RESET}" if o == current
                 else f"{Colors.MUTED}{o}{Colors.RESET}") for o in options]
        return f"{Colors.DIM}{label:<8}{Colors.RESET}" + "  ".join(segs)
    return render
