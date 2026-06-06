"""
Thin wrapper over python-audio-separator.

Turns a selection of stems into output files written next to the input. The
heavy dependency (audio_separator -> torch/onnxruntime) is imported lazily so the
TUI launches instantly. audio-separator's own INFO logging is silenced; we emit
our own step messages through the `progress` callback instead.
"""

import logging
import os
from pathlib import Path

from .engines import Pass, resolve, ENGINE_MODEL


def _noop(_msg: str) -> None:
    pass


def _make_separator(output_dir: str, single_stem=None, output_format="WAV"):
    """Construct a Separator with logging silenced. Raises a friendly error if
    the dependency is missing."""
    try:
        from audio_separator.separator import Separator
    except ImportError as e:
        raise RuntimeError(
            "audio-separator is not installed. Run: pip install -r requirements.txt"
        ) from e
    return Separator(
        log_level=logging.ERROR,          # kill the INFO wall-of-text
        output_dir=output_dir,
        output_single_stem=single_stem,   # one file out when set
        output_format=output_format,
    )


def _separate(separator, model: str, input_file: str) -> list[str]:
    """Run one model pass; return absolute output paths."""
    separator.load_model(model_filename=model)
    names = separator.separate(input_file)
    return [os.path.join(separator.output_dir, n) for n in names]


def _filter_to(paths: list[str], keep: list[str]) -> list[str]:
    """Keep only output files matching the wanted stem names; delete the rest."""
    keep_l = [k.lower() for k in keep]
    kept = []
    for path in paths:
        stem = Path(path).stem.lower()
        if any(k in stem for k in keep_l):
            kept.append(path)
        else:
            try:
                os.remove(path)
            except OSError:
                pass
    return kept


def run(
    selected: list[str],
    input_file: str,
    output_format: str = "WAV",
    model_override: str | None = None,
    progress=_noop,
) -> list[str]:
    """
    Separate `input_file` according to the selected stems. Output files are
    written to the SAME directory as the input. Returns the kept output paths.

    `model_override` forces a single raw model pass (all its stems) and ignores
    `selected` - the "pick it yourself" escape hatch.
    """
    input_file = os.path.abspath(input_file)
    if not os.path.isfile(input_file):
        raise RuntimeError(f"File not found: {input_file}")
    out_dir = os.path.dirname(input_file) or os.getcwd()

    if model_override:
        passes = [Pass(engine="custom", model=model_override, stems=[])]
    else:
        passes = resolve(selected)
    if not passes:
        raise RuntimeError("Nothing selected.")

    results: list[str] = []
    total = len(passes)
    for i, p in enumerate(passes, 1):
        if p.cascade_drums:
            progress(f"[{i}/{total}] Extracting drums (HTDemucs)...")
            drums = _separate(
                _make_separator(out_dir, single_stem="Drums"),
                ENGINE_MODEL["band"], input_file,
            )
            drums_path = drums[0]
            progress(f"[{i}/{total}] Splitting kit (drumsep)...")
            outs = _separate(
                _make_separator(out_dir, output_format=output_format),
                p.model, drums_path,
            )
            results += _filter_to(outs, p.stems)
        else:
            label = p.single_stem or ", ".join(p.stems) or p.model
            progress(f"[{i}/{total}] {p.model} -> {label} (this is the slow part)...")
            sep = _make_separator(out_dir, single_stem=p.single_stem, output_format=output_format)
            outs = _separate(sep, p.model, input_file)
            if p.single_stem or not p.stems:
                results += outs            # already exactly what was asked
            else:
                results += _filter_to(outs, p.stems)

    progress("Done.")
    return results
