#!/usr/bin/env python3
"""
Stemchotic entry point.

  stemchotic.py                   -> TUI: highlight stems, separate
  stemchotic.py <preset> <file>   -> direct: run a CLI preset on a file
  stemchotic.py --list            -> list presets
"""

import argparse
import sys

from src import __version__
from src.core.engines import CLI_PRESETS, plan_text
from src.core.separator import run


def list_presets():
    print(f"\nstemchotic v{__version__} - CLI presets:\n")
    for key, stems in CLI_PRESETS.items():
        print(f"  {key:<14} {', '.join(stems)}")
    print("\n  (or run with no args for the interactive picker)\n")


def do_run(selected, input_file, output_format="WAV", model_override=None):
    print(f"\n  Plan: {plan_text(selected)}")
    print(f"  Output -> next to {input_file}\n")
    try:
        outputs = run(
            selected, input_file,
            output_format=output_format,
            model_override=model_override,
            progress=lambda m: print(f"  {m}"),
        )
    except Exception as e:
        print(f"\n  Error: {e}")
        return 1
    print("\n  Stems written:")
    for path in outputs:
        print(f"    {path}")
    return 0


def run_tui():
    from src.ui import clear_screen, input_with_esc, CancelInput
    from src.ui.screens import show_stem_picker

    while True:
        choice = show_stem_picker()
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
            choice["selected"], input_file.strip(),
            output_format=choice["output_format"],
            model_override=choice["model_override"],
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
    parser.add_argument("-v", "--version", action="version", version=f"stemchotic {__version__}")
    args = parser.parse_args(argv)

    if args.list:
        list_presets()
        return 0

    if args.preset and args.input:
        if args.preset not in CLI_PRESETS:
            print(f"Unknown preset '{args.preset}'. Use --list to see options.")
            return 1
        return do_run(CLI_PRESETS[args.preset], args.input)

    if args.preset and not args.input:
        print("Missing input file. Usage: stemchotic <preset> <file>  (or no args for the picker)")
        return 1

    return run_tui()


if __name__ == "__main__":
    sys.exit(main())
