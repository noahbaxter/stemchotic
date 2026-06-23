#!/usr/bin/env python3
"""
Stemchotic entry point.

  stemchotic.py                   -> TUI: highlight stems, separate
  stemchotic.py <preset> <file>   -> direct: run a CLI preset on a file
  stemchotic.py --list            -> list presets
"""

import argparse
import os
import re
import sys
import traceback

from src import __version__
from src.core import applog
from src.core.engines import (
    CLI_PRESETS, STEM_OPTIONS, plan_text, resolve, category_model, DEFAULT_QUALITY,
)
from src.core.model_cache import missing_models, confirm_downloads
from src.core.separator import run


def clean_path(raw: str) -> str:
    """Normalize a typed or dragged-in path: outer quotes, shell escapes
    (drag-and-drop pastes 'My\\ Song.flac'), ~. If the result still isn't a
    file, salvage the last quoted segment that is one (messy paste recovery)."""
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        s = s[1:-1]
    if os.name != "nt":
        s = re.sub(r"\\(.)", r"\1", s)
    s = os.path.expanduser(s)
    if not os.path.isfile(s):
        for quoted in re.findall(r"'([^']+)'|\"([^\"]+)\"", raw):
            cand = os.path.expanduser(quoted[0] or quoted[1])
            if os.path.isfile(cand):
                s = cand
    return s


STEM_NAMES = [s.name for s in STEM_OPTIONS]


def _preset_desc(cfg):
    """One-line description of a preset config dict."""
    sel = cfg.get("selected", [])
    parts = [", ".join(sel)] if sel else []
    if cfg.get("kit_source") == "stem":
        parts.append(f"DrumSep on drum-stem input ({cfg.get('kit_split', '5')}-piece)")
    elif cfg.get("kit_split"):
        parts.append(f"+ {cfg['kit_split']}-piece kit split")
    return "  ".join(parts) or "(nothing)"


def list_presets():
    print(f"\nstemchotic v{__version__} - CLI presets:\n")
    for key, cfg in CLI_PRESETS.items():
        print(f"  {key:<14} {_preset_desc(cfg)}")
    print("\n  Flags override the preset:")
    print("    --stems S1,S2     explicit selection (Vocals/Instrumental/Drums/Bass/Guitar/Piano/Other)")
    print("    --quality best|fast   --format wav|flac|mp3   --all (keep everything)")
    print("    --residual   --split off|4|5|6   --source song|stem   -y (skip download prompt)")
    print("\n  (or run with no args for the interactive picker)\n")


def do_run(selected, input_file, output_format="WAV", models=None, one_pass=None,
           assume_yes=False, quality=DEFAULT_QUALITY, keep_all=False,
           kit_split="off", kit_source="song", residual=False):
    print(f"\n  Plan: {plan_text(selected, models, one_pass, quality, keep_all, kit_split, kit_source, residual)}")
    print(f"  Output -> next to {input_file}\n")
    passes = resolve(selected, models, one_pass, quality, kit_split, kit_source)
    rhythm = category_model("rhythm", quality, models)
    print("  Checking model cache...")
    if not confirm_downloads(missing_models(passes, rhythm), assume_yes):
        print("  Cancelled (no models downloaded).")
        return 1
    def _progress(m):
        print(f"  {m}")
        applog.write(m)

    applog.write(f"Run: {input_file} -> {plan_text(selected, models, one_pass, quality, keep_all, kit_split, kit_source, residual)}")
    try:
        outputs = run(
            selected, input_file,
            output_format=output_format,
            models=models, one_pass=one_pass,
            progress=_progress,
            quality=quality, keep_all=keep_all,
            kit_split=kit_split, kit_source=kit_source, residual=residual,
        )
    except Exception as e:
        applog.write(f"Separation failed: {e!r}\n" + traceback.format_exc().rstrip())
        print(f"\n  Error: {e}")
        return 1
    print("\n  Stems written:")
    for path in outputs:
        print(f"    {path}")
    return 0


# The app owns its window size (it ships in app.zip and auto-updates, unlike the
# frozen launcher), so bump these as the UI grows. 90 cols fits the 81-wide
# banner; rows are sized to the picker with a little headroom.
UI_COLS, UI_ROWS = 90, 30


def _fit_window():
    """Size the terminal to the app's UI. WezTerm (and most terminals) honor this
    XTWINOPS resize escape on every platform; non-supporting terminals ignore it."""
    if sys.stdout.isatty():
        sys.stdout.write(f"\x1b[8;{UI_ROWS};{UI_COLS}t")
        sys.stdout.flush()


def run_tui():
    from chotic_ui import clear_screen, input_with_esc, CancelInput, configure_header, set_theme
    from src.banner import BANNER
    from src.screens import show_stem_picker, new_state

    _fit_window()
    set_theme("kanagawa")
    configure_header(BANNER, __version__)

    # Warm the model catalogue in the background so the M (models) screen opens
    # instantly instead of paying the first audio-separator/torch import then.
    import threading
    from src.screens.model_picker import _load_catalog

    def _preload_catalog():
        try:
            _load_catalog()
        except Exception:
            pass   # the M screen will surface any real error when opened

    threading.Thread(target=_preload_catalog, daemon=True).start()

    state = new_state()  # persists for the whole session
    while True:
        choice = show_stem_picker(state)
        if choice is None:
            clear_screen()
            print("Bye.")
            return 0

        try:
            input_file = input_with_esc("\n  Audio file: ")
        except CancelInput:
            continue
        if not input_file.strip():
            continue

        do_run(
            choice["selected"], clean_path(input_file),
            output_format=choice["output_format"],
            models=choice.get("models"), one_pass=choice.get("one_pass"),
            quality=choice.get("quality", DEFAULT_QUALITY),
            keep_all=choice.get("keep_all", False),
            kit_split=choice.get("kit_split", "off"),
            kit_source=choice.get("kit_source", "song"),
            residual=choice.get("residual", False),
        )
        try:
            input_with_esc("\n  Press Enter to return to the picker... ")
        except CancelInput:
            pass


def main(argv=None):
    from chotic_ui import bootstrap
    bootstrap("Stemchotic")
    applog.init(__version__)
    parser = argparse.ArgumentParser(prog="stemchotic", description="Easy stem separation.")
    parser.add_argument("preset", nargs="?", help="Preset key (see --list), or the input file")
    parser.add_argument("input", nargs="?", help="Input audio file")
    parser.add_argument("--stems", help="Explicit selection, comma-separated (overrides the preset)")
    parser.add_argument("--quality", choices=["best", "fast"], default=DEFAULT_QUALITY,
                        help="Model tier (default best)")
    parser.add_argument("--format", dest="fmt", default="wav", type=str.lower,
                        choices=["wav", "flac", "mp3"],
                        help="Output format: wav, flac, or mp3 (default wav)")
    parser.add_argument("--all", dest="keep_all", action="store_true",
                        help="Keep everything the models make (forces residual off)")
    parser.add_argument("--residual", action="store_true", help="Also write mix - picks")
    parser.add_argument("--split", choices=["off", "4", "5", "6"], help="Drum-kit split")
    parser.add_argument("--source", choices=["song", "stem"],
                        help="Treat the input as a full song or a drum stem")
    parser.add_argument("-l", "--list", action="store_true", help="List presets and exit")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip the model-download confirmation")
    parser.add_argument("-v", "--version", action="version", version=f"stemchotic {__version__}")
    args = parser.parse_args(argv)

    if args.list:
        list_presets()
        return 0

    # Disambiguate the positionals. With one positional that isn't a known preset,
    # treat it as the input (no preset) when it's an existing file OR when
    # selection flags were given (so a bare-input headless run works).
    preset, input_file = args.preset, args.input
    flags_given = bool(args.stems or args.split or args.source)
    if preset and input_file is None and preset not in CLI_PRESETS and (
        flags_given or os.path.isfile(clean_path(preset))
    ):
        preset, input_file = None, preset

    if preset and preset not in CLI_PRESETS:
        print(f"Unknown preset '{preset}'. Use --list to see options.")
        return 1
    if input_file is None:
        if preset:
            print("Missing input file. Usage: stemchotic [preset] <file>  (or no args for the picker)")
            return 1
        return run_tui()   # no args at all -> interactive picker

    cfg = dict(CLI_PRESETS.get(preset, {})) if preset else {}
    selected = list(cfg.get("selected", []))
    kit_split = cfg.get("kit_split", "off")
    kit_source = cfg.get("kit_source", "song")

    if args.stems is not None:
        selected = [s.strip() for s in args.stems.split(",") if s.strip()]
        unknown = [s for s in selected if s not in STEM_NAMES]
        if unknown:
            print(f"Unknown stem(s): {', '.join(unknown)}. Valid: {', '.join(STEM_NAMES)}")
            return 1
    if args.split is not None:
        kit_split = args.split
    if args.source is not None:
        kit_source = args.source

    keep_all = args.keep_all
    residual = args.residual and not keep_all   # same exclusion as the TUI

    return do_run(
        selected, clean_path(input_file),
        output_format=args.fmt.upper(), assume_yes=args.yes,
        quality=args.quality, keep_all=keep_all,
        kit_split=kit_split, kit_source=kit_source, residual=residual,
    )


if __name__ == "__main__":
    sys.exit(main())
