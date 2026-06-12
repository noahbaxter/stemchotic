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

from src import __version__
from src.core.engines import CLI_PRESETS, plan_text, resolve, category_model, DEFAULT_QUALITY
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


def list_presets():
    print(f"\nstemchotic v{__version__} - CLI presets:\n")
    for key, stems in CLI_PRESETS.items():
        print(f"  {key:<14} {', '.join(stems)}")
    print("\n  (or run with no args for the interactive picker)\n")


def do_run(selected, input_file, output_format="WAV", models=None, one_pass=None,
           assume_yes=False, quality=DEFAULT_QUALITY, keep_all=False):
    print(f"\n  Plan: {plan_text(selected, models, one_pass, quality, keep_all)}")
    print(f"  Output -> next to {input_file}\n")
    passes = resolve(selected, models, one_pass, quality)
    rhythm = category_model("rhythm", quality, models)
    print("  Checking model cache...")
    if not confirm_downloads(missing_models(passes, rhythm), assume_yes):
        print("  Cancelled (no models downloaded).")
        return 1
    try:
        outputs = run(
            selected, input_file,
            output_format=output_format,
            models=models, one_pass=one_pass,
            progress=lambda m: print(f"  {m}"),
            quality=quality, keep_all=keep_all,
        )
    except Exception as e:
        print(f"\n  Error: {e}")
        return 1
    print("\n  Stems written:")
    for path in outputs:
        print(f"    {path}")
    return 0


def run_tui():
    from chotic_ui import clear_screen, input_with_esc, CancelInput, configure_header, set_theme
    from src.banner import BANNER
    from src.screens import show_stem_picker, new_state

    set_theme("kanagawa")
    configure_header(BANNER, __version__)
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
        )
        try:
            input_with_esc("\n  Press Enter to return to the picker... ")
        except CancelInput:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="stemchotic", description="Easy stem separation.")
    parser.add_argument("preset", nargs="?", help="Preset key (see --list)")
    parser.add_argument("input", nargs="?", help="Input audio file")
    parser.add_argument("-l", "--list", action="store_true", help="List presets and exit")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip the model-download confirmation")
    parser.add_argument("-v", "--version", action="version", version=f"stemchotic {__version__}")
    args = parser.parse_args(argv)

    if args.list:
        list_presets()
        return 0

    if args.preset and args.input:
        if args.preset not in CLI_PRESETS:
            print(f"Unknown preset '{args.preset}'. Use --list to see options.")
            return 1
        return do_run(CLI_PRESETS[args.preset], clean_path(args.input), assume_yes=args.yes)

    if args.preset and not args.input:
        print("Missing input file. Usage: stemchotic <preset> <file>  (or no args for the picker)")
        return 1

    return run_tui()


if __name__ == "__main__":
    sys.exit(main())
