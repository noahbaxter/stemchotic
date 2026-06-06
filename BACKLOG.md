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
- Migrate synchotic onto the chotic-ui submodule too, so the toolkit has one home
  (stemchotic already uses it; synchotic still has its own copy).
- Optional Gradio/desktop front-end for non-terminal users.

## Done
- Extracted the TUI toolkit into the chotic-ui repo and submoduled it in
  (libs/chotic-ui, installed editable via requirements.txt).
