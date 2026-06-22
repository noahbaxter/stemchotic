"""
Thin wrapper over python-audio-separator.

Turns a selection of stems into output files written next to the input. The
heavy dependency (audio_separator -> torch/onnxruntime) is imported lazily so the
TUI launches instantly. audio-separator's own INFO logging is silenced; we emit
our own step messages through the `progress` callback instead.
"""

import logging
import os
import re
import shutil
import threading
from pathlib import Path

from .engines import Pass, resolve, short_name, category_model, DEFAULT_QUALITY
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


def _device_label() -> str:
    """What audio-separator will actually run on, so GPU use is visible (we
    silence audio-separator's own device logs). Mirrors its detection order:
    CUDA, then Apple MPS, else CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            try:
                name = torch.cuda.get_device_name(0)
            except Exception:
                name = "CUDA"
            ort_gpu = ""
            try:
                import onnxruntime as ort
                if "CUDAExecutionProvider" not in ort.get_available_providers():
                    ort_gpu = "  (note: onnxruntime is CPU-only; .onnx models run on CPU)"
            except Exception:
                pass
            return f"NVIDIA GPU - {name}{ort_gpu}"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "Apple GPU (MPS)"
    except Exception:
        pass
    return "CPU (no GPU acceleration detected)"


def model_dir() -> str | None:
    """Pinned model cache when launched via the launcher (STEMCHOTIC_ROOT set),
    else None -> audio-separator's default cache (dev runs)."""
    root = os.environ.get("STEMCHOTIC_ROOT")
    return os.path.join(root, ".stemchotic", "models") if root else None


def models_dir() -> str:
    """The directory the Separator will actually use: pinned dir or the
    audio-separator default."""
    return model_dir() or DEFAULT_CACHE


_FFMPEG_LOCK = threading.Lock()
_ffmpeg_ready = False


def ensure_ffmpeg() -> None:
    """Put ffmpeg + ffprobe on PATH for audio-separator and pydub.

    A packaged app's PATH does not include the user's ffmpeg, and a fresh
    machine may have none, so we ship our own via the static-ffmpeg package and
    prepend it here. A real system ffmpeg already on PATH (dev machines, CLI
    users) is used as-is; we only fall back to the bundled binaries otherwise.
    Idempotent and thread-safe (the TUI warms this from a background thread)."""
    global _ffmpeg_ready
    if _ffmpeg_ready:
        return
    with _FFMPEG_LOCK:
        if _ffmpeg_ready:
            return
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            try:
                import static_ffmpeg
                static_ffmpeg.add_paths()   # prepend cached ffmpeg/ffprobe to PATH
            except Exception:
                pass   # leave PATH as-is; Separator reports if ffmpeg is truly missing
        _ffmpeg_ready = True


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
    ensure_ffmpeg()
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


_DEFAULT_STEM = re.compile(r"_\(([^)]+)\)_")   # audio-separator's "base_(stem)_model" pattern


def _rename_all(paths: list[str], base: str, model: str, tag_model: bool) -> list[str]:
    """Rename every stem a model emitted to '<base> [Stem]', tagging the model
    name when more than one model runs so same-named stems can't collide."""
    kept = []
    for path in paths:
        m = _DEFAULT_STEM.search(Path(path).name)
        stem = m.group(1) if m else Path(path).stem
        label = f"{base} [{_pretty(stem)}]"
        if tag_model:
            label += f" ({short_name(model)})"
        new = os.path.join(os.path.dirname(path), label + Path(path).suffix)
        if os.path.abspath(new) != os.path.abspath(path):
            os.replace(path, new)
        kept.append(new)
    return kept


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


def _residual(input_file, picked_paths, base, output_format):
    """One file = the input mix minus the picked whole-stem outputs."""
    import soundfile as sf, numpy as np
    mix, sr = sf.read(input_file)
    acc = np.zeros_like(mix)
    for p in picked_paths:
        a, _ = sf.read(p)
        n = min(len(a), len(acc))
        if a.ndim == mix.ndim:
            acc[:n] += a[:n]
        else:                                  # mono stem into stereo mix or vice versa
            acc[:n] += a[:n, None] if mix.ndim == 2 else a[:n].mean(axis=1)[:n]
    res = np.clip(mix - acc, -1.0, 1.0)
    ext = output_format.lower()
    out = os.path.join(os.path.dirname(os.path.abspath(input_file)), f"{base} [Residual].{ext}")
    sf.write(out, res, sr)
    return out


def run(
    selected: list[str],
    input_file: str,
    output_format: str = "WAV",
    models: dict | None = None,
    one_pass: str | None = None,
    progress=_noop,
    quality: str = DEFAULT_QUALITY,
    keep_all: bool = False,
    kit_split: str = "off",
    kit_source: str = "song",
    residual: bool = False,
) -> list[str]:
    """
    Separate `input_file` according to the selected stems. Output files are
    written to the SAME directory as the input. Returns the kept output paths.

    `models`: per-category model overrides. `one_pass`: run a single model for the
    whole selection. `keep_all`: keep every stem each model emits instead of
    trimming to the selection (the "everything the models make" output mode).
    """
    input_file = os.path.abspath(input_file)
    if not os.path.isfile(input_file):
        raise RuntimeError(f"File not found: {input_file}")
    out_dir = os.path.dirname(input_file) or os.getcwd()

    passes = resolve(selected, models, one_pass, quality, kit_split=kit_split, kit_source=kit_source)
    if not passes:
        raise RuntimeError("Nothing selected.")

    base = Path(input_file).stem
    rhythm_model = category_model("rhythm", quality, models)

    # Custom models aren't in audio-separator's repos; fetch them ourselves.
    needed = [p.model for p in passes]
    if any(p.cascade_drums for p in passes):
        needed.append(rhythm_model)
    for m in dict.fromkeys(needed):
        entry = CUSTOM_MODELS.get(m)
        if entry:   # skips files already present
            os.makedirs(models_dir(), exist_ok=True)
            download_custom(entry, models_dir(), progress)

    progress(f"Compute device: {_device_label()}")

    results: list[str] = []
    whole_stem_paths: list[str] = []   # non-kit pass outputs, for the residual
    total = len(passes)
    for i, p in enumerate(passes, 1):
        if p.cascade_drums or p.direct_split:
            if p.direct_split:
                drums_path, reused = input_file, True   # the input file IS the drum stem
            else:
                # Reuse a [Drums] stem already produced this run (rhythm pass)
                # instead of extracting drums a second time. Match the token
                # anywhere, since keep_all tags the name "[Drums] (Model)".
                drums_path = next((r for r in results if "[Drums]" in Path(r).stem), None)
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
            if keep_all:
                # Keep every stem the model emits, named "<base> [Stem]" (model-
                # tagged when more than one model runs, so stems can't collide).
                sep = _make_separator(out_dir, output_format=output_format)
                outs = _separate(sep, p.model, input_file,
                                 label=f"[{i}/{total}] {short_name(p.model)} -> all stems")
                kept = _rename_all(outs, base, p.model, tag_model=total > 1)
            else:
                keep = [p.single_stem] if p.single_stem else p.stems
                sep = _make_separator(out_dir, single_stem=p.single_stem, output_format=output_format)
                outs = _separate(sep, p.model, input_file, _names(base, keep),
                                 label=f"[{i}/{total}] {short_name(p.model)} -> {label}")
                # Multi-stem models (roformer/MDXC) ignore output_single_stem and
                # emit every stem, so always filter to the ask and delete the rest
                # (also drops the ugly default-named extras SW would leave behind).
                kept = _filter_to(outs, keep) if keep else outs
            results += kept
            whole_stem_paths += kept   # only non-kit passes feed the residual

    if residual and not keep_all and whole_stem_paths:
        results.append(_residual(input_file, whole_stem_paths, base, output_format))
    progress("Done.")
    return results
