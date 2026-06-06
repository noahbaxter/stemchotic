# Stemchotic Backlog

## Next up
- Verify the drumsep checkpoint actually loads through audio-separator (custom
  Hybrid Demucs, non-standard kick/snare/tom/cymbal stem names). This is the one
  unproven piece of the `kit` cascade.
- Confirm exact model filenames against `audio-separator --list_models` (the
  roformer checkpoint name drifts between releases).
- Tighten cascade stem-routing in `core/separator.py` once drumsep is verified.

## Soon
- Own the inference progress bar instead of letting audio-separator's raw tqdm
  through (no callback hook exists; would need to capture stderr or drive a
  custom bar). Logging is already silenced.
- File picker screen instead of typing a path.
- Decide whether "band" should pull vocals from HTDemucs (1 pass) instead of
  routing to RoFormer (2 passes). Currently routes to RoFormer for quality.

## Later
- Extract the synchotic TUI toolkit into its own repo and submodule it into both
  synchotic and stemchotic, so the framework has one home instead of a copy per
  project. (Copy-in now, extract later.)
- Optional Gradio/desktop front-end for non-terminal users.
