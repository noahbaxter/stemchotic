#!/usr/bin/env python3
"""
Stemchotic entry point.

Two ways to run:
  stemchotic.py                      -> TUI: pick a template from the menu
  stemchotic.py <template> <file>    -> direct: run a template on a file
  stemchotic.py --list               -> list available templates
"""

import argparse
import sys

from src import __version__
from src.core.templates import TEMPLATES, get_template
from src.core.separator import separate


def list_templates():
    print(f"\nstemchotic v{__version__} - templates:\n")
    for t in TEMPLATES:
        tag = "  (experimental)" if t.experimental else ""
        print(f"  {t.key:<14} {t.name}{tag}")
        print(f"  {'':<14} {t.description}\n")


def run_template(template, input_file):
    print(f"\nRunning '{template.name}' on {input_file} ...")
    try:
        outputs = separate(template, input_file, progress=lambda m: print(f"  {m}"))
    except Exception as e:
        print(f"\n  Error: {e}")
        return 1
    print("\n  Done. Output stems:")
    for path in outputs:
        print(f"    {path}")
    return 0


def run_tui():
    """Launch the interactive menu loop."""
    from src.ui import clear_screen, input_with_esc, CancelInput
    from src.ui.screens import show_home

    while True:
        template = show_home()
        if template is None:
            clear_screen()
            print("Bye.")
            return 0

        try:
            input_file = input_with_esc(f"\n  Audio file for '{template.name}': ")
        except CancelInput:
            continue

        if not input_file.strip():
            continue

        run_template(template, input_file.strip())
        try:
            input_with_esc("\n  Press Enter to return to the menu... ")
        except CancelInput:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="stemchotic", description="Easy stem separation templates.")
    parser.add_argument("template", nargs="?", help="Template key (see --list)")
    parser.add_argument("input", nargs="?", help="Input audio file")
    parser.add_argument("-l", "--list", action="store_true", help="List templates and exit")
    parser.add_argument("-v", "--version", action="version", version=f"stemchotic {__version__}")
    args = parser.parse_args(argv)

    if args.list:
        list_templates()
        return 0

    if args.template and args.input:
        template = get_template(args.template)
        if template is None:
            print(f"Unknown template '{args.template}'. Use --list to see options.")
            return 1
        return run_template(template, args.input)

    if args.template and not args.input:
        print("Missing input file. Usage: stemchotic <template> <file>  (or run with no args for the menu)")
        return 1

    return run_tui()


if __name__ == "__main__":
    sys.exit(main())
