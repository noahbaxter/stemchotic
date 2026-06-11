# Stemchotic Backlog

## Next up
- Integrate BS-Roformer-SW (open-weight 6-stem roformer: vocals/drums/bass/guitar/
  piano/other). It's what charters actually prefer for full band, and it's free to
  run locally, just not in audio-separator's catalogue. Register its ckpt+config as
  a custom MDXC model in audio-separator, or add bs-roformer-infer as a 2nd backend.
  Would beat htdemucs_6s and close the full-band gap without mvsep. Sources: HF
  jarredou/BS-ROFO-SW-Fixed, pip bs-roformer-infer, ZFTurbo Music-Source-Separation-Training.
  Priority note: charters widely prefer mvsep's BS-Roformer-SW, but several say the
  gap over demucs is "marginal" (demucs is "very good", the emergency/fallback). So
  this is a nice upgrade, not urgent - our local demucs default is genuinely fine.
- Optimal per-model settings: we run audio-separator's defaults (segment size,
  overlap, shifts). Not tuned. Worth a pass once the model set settles.
- Confirm exact model filenames against `audio-separator --list_models` (the
  roformer checkpoint name drifts between releases).

## Soon
- Own the inference progress bar instead of letting audio-separator's raw tqdm
  through (no callback hook exists; would need to capture stderr or drive a
  custom bar). Logging is already silenced.
- File picker screen instead of typing a path.
- Decide whether "band" should pull vocals from HTDemucs (1 pass) instead of
  routing to RoFormer (2 passes). Currently routes to RoFormer for quality.
- Replace the heuristic fast/avg/slow model speed tier with real timing: time a
  short sample render per model once, cache it, show measured speed. Current
  tier is just arch-based guessing (VR=fast, MDX/Demucs=avg, RoFormer/_ft=slow).

## Later
- Ship as a uv-launcher app (mac/win/linux); CI bundles the chotic-ui submodule;
  separate CPU/CUDA builds on win/linux, MPS on mac.
- Migrate synchotic onto the chotic-ui submodule too, so the toolkit has one home
  (stemchotic already uses it; synchotic still has its own copy).
- Optional Gradio/desktop front-end for non-terminal users.

## Done
- Extracted the TUI toolkit into the chotic-ui repo and submoduled it in
  (libs/chotic-ui, installed editable via requirements.txt).
