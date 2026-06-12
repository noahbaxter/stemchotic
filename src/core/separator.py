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

from .engines import Pass, resolve, short_name, ENGINE_MODEL
from .progress import capture_tqdm
from .registry import CUSTOM_MODELS, download_custom, ensure_registry

# audio-separator 0.44.2's built-in default model_file_dir (dev runs).
DEFAULT_CACHE = "/tmp/audio-separator-models"


def _pretty(stem: str) -> str:
    """Display form of a stem name: 'kick' -> 'Kick', 'hh' -> 'HH'."""
    return stem.upper() if len(stem) <= 2 else stem.capitalize()


def _names(base: str, stems) -> dict:
    """custom_output_names mapping the model's stem names to '<base> [Stem]'.
    Includes case variants so it matches whatever casing the model emits."""
    out = {}
    for s in stems:
        nm = f"{base} [{_pretty(s)}]"
        for key in {s, s.lower(), s.capitalize(), s.upper()}:
            out[key] = nm
    return out


def _noop(_msg: str) -> None:
    pass


def model_dir() -> str | None:
    """Pinned model cache when launched via the launcher (STEMCHOTIC_ROOT set),
    else None -> audio-separator's default cache (dev runs)."""
    root = os.environ.get("STEMCHOTIC_ROOT")
    return os.path.join(root, ".stemchotic", "models") if root else None


def models_dir() -> str:
    """The directory the Separator will actually use: pinned dir or the
    audio-separator default."""
    return model_dir() or DEFAULT_CACHE


def _make_separator(output_dir=None, single_stem=None, output_format="WAV"):
    """Construct a Separator with logging silenced and the model cache pinned
    under STEMCHOTIC_ROOT when launched via the launcher. Raises a friendly
    error if the dependency is missing."""
    try:
        from audio_separator.separator import Separator
    except ImportError as e:
        raise RuntimeError(
            "audio-separator is not installed. Run: pip install -r requirements.txt"
        ) from e
    kwargs = {}
    md = model_dir()
    if md:
        kwargs["model_file_dir"] = md
    # Merge our custom models into the registry the Separator will read.
    reg_dir = models_dir()
    os.makedirs(reg_dir, exist_ok=True)
    try:
        ensure_registry(reg_dir)
    except Exception:
        pass   # offline with no registry on disk; catalogue models still work
    if output_dir is not None:
        kwargs["output_dir"] = output_dir
    return Separator(
        log_level=logging.ERROR,          # kill the INFO wall-of-text
        output_single_stem=single_stem,   # one file out when set
        output_format=output_format,
        **kwargs,
    )


def _separate(separator, model: str, input_file: str, names: dict | None = None,
              label: str = "") -> list[str]:
    """Run one model pass; return absolute output paths. `names` sets the output
    filenames explicitly (audio-separator custom_output_names). `label` titles
    the in-place progress line that replaces tqdm's stderr bars."""
    with capture_tqdm(label or short_name(model)):
        separator.load_model(model_filename=model)
        out = separator.separate(input_file, names) if names else separator.separate(input_file)
    return [n if os.path.isabs(n) else os.path.join(separator.output_dir, n) for n in out]


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


def _merge_pieces(paths: list[str], merge: dict, base: str, output_format: str) -> list[str]:
    """Sum groups of kit pieces into one (e.g. hh+ride+crash -> Cymbals), delete
    the parts. Pieces are matched by their '[name]' token. `merge` is
    {new_name: [piece_names]}."""
    import soundfile as sf
    import numpy as np

    kept = list(paths)
    ext = output_format.lower()
    for new_name, parts in merge.items():
        part_paths = [p for p in kept
                      if any(f"[{pt.lower()}]" in Path(p).stem.lower() for pt in parts)]
        if not part_paths:
            continue
        mix, sr = None, None
        for pp in part_paths:
            audio, sr = sf.read(pp)
            mix = audio if mix is None else mix + audio
        mix = np.clip(mix, -1.0, 1.0)

        # Remove the parts BEFORE writing: the merged name may collide with one
        # of them (e.g. hh+cymbals -> Cymbals), and writing first would get the
        # fresh file deleted by this cleanup.
        out_path = os.path.join(os.path.dirname(part_paths[0]), f"{base} [{new_name}].{ext}")
        for pp in part_paths:
            kept.remove(pp)
            try:
                os.remove(pp)
            except OSError:
                pass
        sf.write(out_path, mix, sr)
        kept.append(out_path)
    return kept


def run(
    selected: list[str],
    input_file: str,
    output_format: str = "WAV",
    models: dict | None = None,
    one_pass: str | None = None,
    progress=_noop,
) -> list[str]:
    """
    Separate `input_file` according to the selected stems. Output files are
    written to the SAME directory as the input. Returns the kept output paths.

    `models`: per-category model overrides. `one_pass`: run a single model for the
    whole selection (filtered to the selected stems).
    """
    input_file = os.path.abspath(input_file)
    if not os.path.isfile(input_file):
        raise RuntimeError(f"File not found: {input_file}")
    out_dir = os.path.dirname(input_file) or os.getcwd()

    passes = resolve(selected, models, one_pass)
    if not passes:
        raise RuntimeError("Nothing selected.")

    base = Path(input_file).stem
    rhythm_model = (models or {}).get("rhythm", ENGINE_MODEL["rhythm"])

    # Custom models aren't in audio-separator's repos; fetch them ourselves.
    needed = [p.model for p in passes]
    if any(p.cascade_drums for p in passes):
        needed.append(rhythm_model)
    for m in dict.fromkeys(needed):
        entry = CUSTOM_MODELS.get(m)
        if entry:   # skips files already present
            os.makedirs(models_dir(), exist_ok=True)
            download_custom(entry, models_dir(), progress)

    results: list[str] = []
    total = len(passes)
    for i, p in enumerate(passes, 1):
        if p.cascade_drums:
            # Reuse a [Drums] stem already produced this run (rhythm pass)
            # instead of extracting drums a second time.
            drums_path = next((r for r in results if Path(r).stem.endswith("[Drums]")), None)
            reused = drums_path is not None
            if not reused:
                progress(f"[{i}/{total}] Extracting drums ({short_name(rhythm_model)})...")
                drums = _separate(
                    _make_separator(out_dir, single_stem="Drums"),
                    rhythm_model, input_file,
                    label=f"[{i}/{total}] {short_name(rhythm_model)} -> Drums",
                )
                drums_path = drums[0]
            progress(f"[{i}/{total}] Splitting kit ({short_name(p.model)})...")
            outs = _separate(
                _make_separator(out_dir, output_format=output_format),
                p.model, drums_path, _names(base, p.pieces or []),
                label=f"[{i}/{total}] Splitting kit",
            )
            if not reused:
                try:
                    os.remove(drums_path)  # drop the intermediate drums stem
                except OSError:
                    pass
            results += _merge_pieces(outs, p.merge, base, output_format) if p.merge else outs
        else:
            label = p.single_stem or ", ".join(p.stems) or short_name(p.model)
            progress(f"[{i}/{total}] {short_name(p.model)} -> {label} (this is the slow part)...")
            keep = [p.single_stem] if p.single_stem else p.stems
            sep = _make_separator(out_dir, single_stem=p.single_stem, output_format=output_format)
            outs = _separate(sep, p.model, input_file, _names(base, keep),
                             label=f"[{i}/{total}] {short_name(p.model)} -> {label}")
            if p.single_stem or not p.stems:
                results += outs            # already exactly what was asked
            else:
                results += _filter_to(outs, p.stems)

    progress("Done.")
    return results
