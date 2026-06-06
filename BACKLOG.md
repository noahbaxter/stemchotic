# Stemchotic Backlog

## Next up
- Verify the drumsep checkpoint actually loads through audio-separator (custom
  Hybrid Demucs, non-standard kick/snare/tom/cymbal stem names). This is the one
  unproven piece of the `kit` cascade.
- Confirm exact model filenames against `audio-separator --list_models` (the
  roformer checkpoint name drifts between releases).
- Tighten cascade stem-routing in `core/separator.py` once drumsep is verified.

## Soon
- Real progress screen during separation (lift/rebuild a progress widget; the
  synchotic one was too coupled to charting to lift directly).
- File picker screen instead of typing a path.

## Later
- Extract the synchotic TUI toolkit into its own repo and submodule it into both
  synchotic and stemchotic, so the framework has one home instead of a copy per
  project. (Copy-in now, extract later.)
- Optional Gradio/desktop front-end for non-terminal users.
