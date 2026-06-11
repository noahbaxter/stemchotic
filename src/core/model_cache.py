"""
Model-download awareness: which models a plan needs, which are already cached,
and (best-effort) how big the missing ones are. Used for the consent prompt
before any separation run. No audio_separator imports (torch is slow).
"""

import os
import sys
import urllib.request

from .separator import model_dir
from .engines import Pass, short_name

# audio-separator 0.44.2's built-in default model_file_dir.
_DEFAULT_CACHE = "/tmp/audio-separator-models"

# Single-file models in the public UVR repo. Demucs yaml bundles resolve their
# weight URLs through a network-fetched registry, so those stay unknown.
_PUBLIC_REPO = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models"


def _cache_dir() -> str | None:
    """The directory audio-separator will download into, if known. Pinned dir
    when launched via the launcher; audio-separator's default in dev."""
    md = model_dir()
    if md:
        return md
    return _DEFAULT_CACHE if os.path.isdir(_DEFAULT_CACHE) else None


def is_cached(model_filename: str) -> bool:
    import glob as _glob
    d = _cache_dir()
    if not d:
        return False
    yaml_path = os.path.join(d, model_filename)
    if not os.path.exists(yaml_path):
        return False
    if not model_filename.endswith(".yaml"):
        return True
    # Demucs yaml bundles: require at least one <hash>*.th per listed hash token.
    # Lines like "models: ['955717e8']" or "- 955717e8" carry the identifiers.
    tokens = []
    in_models = False
    with open(yaml_path) as f:
        for line in f:
            if "models:" in line:
                in_models = True
            elif not line.lstrip().startswith("-"):
                in_models = False
                continue
            if in_models:
                for part in line.split():
                    part = part.strip("[],'\"")
                    if len(part) >= 8 and all(c in "0123456789abcdef" for c in part):
                        tokens.append(part)
    if not tokens:
        return True  # no hash tokens found; fall back to yaml-presence
    return all(_glob.glob(os.path.join(d, f"{tok}*.th")) for tok in tokens)


def _download_url(model_filename: str) -> str | None:
    """Cheap URL guess for single-file models; None means size unknown."""
    if model_filename.endswith((".ckpt", ".onnx", ".pth", ".th")):
        return f"{_PUBLIC_REPO}/{model_filename}"
    return None


def _size_of(model_filename: str) -> int | None:
    """Best-effort size in bytes via HEAD on the resolved download URL."""
    try:
        url = _download_url(model_filename)
        if not url:
            return None
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5) as resp:
            n = resp.headers.get("Content-Length")
            return int(n) if n else None
    except Exception:
        return None


def missing_models(passes: list[Pass], rhythm_model: str) -> list[tuple[str, int | None]]:
    """[(model_filename, size_bytes|None)] for models the plan needs but the
    cache lacks. Cascade passes also need the rhythm (drums) model."""
    needed: list[str] = []
    for p in passes:
        if p.cascade_drums and rhythm_model not in needed:
            needed.append(rhythm_model)
        if p.model not in needed:
            needed.append(p.model)
    return [(m, _size_of(m)) for m in needed if not is_cached(m)]


def _fmt_size(n: int | None) -> str:
    if n is None:
        return "size unknown"
    return f"{n / 1024 / 1024:.0f}MB"


def confirm_downloads(missing: list[tuple[str, int | None]], assume_yes: bool = False) -> bool:
    """Consent gate. True = proceed. Non-TTY without assume_yes refuses with a
    clear message rather than silently downloading gigabytes."""
    if not missing:
        return True
    if assume_yes:
        return True
    lines = ", ".join(f"{short_name(m)} ({_fmt_size(s)})" for m, s in missing)
    if not sys.stdin.isatty():
        print(f"  This run needs to download: {lines}")
        print("  Re-run with --yes to allow model downloads in non-interactive mode.")
        return False
    try:
        ans = input(f"  This run downloads: {lines}. Continue? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("", "y", "yes")
