"""
Registry overlay for custom public-weight models.

audio-separator lists models from download_checks.json in its model dir and
only downloads what that registry names. Our custom models (models.json
"custom_models") aren't in the upstream catalogue, so we merge them in here
and download their ckpt+config ourselves from the mirror URLs.
"""

import json
import os
import time
import urllib.request

from .engines import CONFIG

_UPSTREAM = "https://raw.githubusercontent.com/TRvlvr/application_data/main/filelists/download_checks.json"
_MAX_AGE = 7 * 24 * 3600   # refresh the upstream registry weekly

CUSTOM_MODELS = {m["filename"]: m for m in CONFIG.get("custom_models", [])}


def ensure_registry(model_dir: str) -> None:
    """Make download_checks.json in model_dir exist, be reasonably fresh, and
    contain our custom_models entries. Idempotent; offline is fine as long as
    a registry is already on disk."""
    path = os.path.join(model_dir, "download_checks.json")
    stale = not os.path.isfile(path) or time.time() - os.path.getmtime(path) > _MAX_AGE
    if stale:
        try:
            tmp = path + ".part"
            urllib.request.urlretrieve(_UPSTREAM, tmp)
            os.replace(tmp, path)
        except Exception:
            if not os.path.isfile(path):
                raise
    with open(path, encoding="utf-8") as f:
        registry = json.load(f)
    changed = False
    for m in CUSTOM_MODELS.values():
        entry = {m["filename"]: m["config"]}   # same shape as catalogue entries
        group = registry.setdefault(m["group"], {})
        if group.get(m["entry_name"]) != entry:
            group[m["entry_name"]] = entry
            changed = True
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=4)


def download_custom(entry: dict, model_dir: str, progress=lambda msg: None) -> None:
    """Fetch a custom model's ckpt + config into model_dir (skips files already
    present). The config is saved under entry['config'], which may differ from
    the URL's basename."""
    for kind in ("config", "ckpt"):
        filename = entry["config"] if kind == "config" else entry["filename"]
        dest = os.path.join(model_dir, filename)
        if os.path.isfile(dest):
            continue
        last = -1

        def hook(blocks, bs, total):
            nonlocal last
            if total > 0:
                pct = min(blocks * bs * 100 // total, 100)
                if pct != last:
                    last = pct
                    progress(f"Downloading {filename}... {pct}%")

        tmp = dest + ".part"
        urllib.request.urlretrieve(entry["urls"][kind], tmp, reporthook=hook)
        os.replace(tmp, dest)
