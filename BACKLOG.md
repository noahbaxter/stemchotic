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
- Fix the misleading first-run size prompt. ensure_env says "downloads ~2.5GB,
  uses ~5GB disk" but that's the NVIDIA-CUDA worst case; on Apple Silicon the env
  is ~1GB (python 53MB + torch 401MB + onnx/numba/scipy). Make the message
  hardware-aware (cpu/mps vs cuda) so Mac users aren't scared by a 5GB figure.
- Dependency-prune experiment to shrink the ~1GB env. Candidates that look like
  unused transitive pulls (verify "does a separation still run?" after removing
  each): sympy (29MB), PIL + Cython (24MB), onnx vs onnxruntime (67MB, if only
  the runtime is needed at inference), numba + llvmlite (132MB, if librosa's JIT
  path is never hit). Potential ~200-400MB saved -> ~700MB. torch (~400MB) is the
  irreducible floor. Also reconsider static_ffmpeg (94MB) vs a leaner ffmpeg.
- Own the inference progress bar instead of letting audio-separator's raw tqdm
  through (no callback hook exists; would need to capture stderr or drive a
  custom bar). Logging is already silenced. (Confirmed worth doing in local-build
  testing: the raw "x%" reads as janky for a native-feeling app.)
- Model picker UX (from local-build testing): add a "reset to defaults" action;
  stabilise the right-pane order (curated picks re-pin and jump when the current
  selection changes, which reads as the list reshuffling); make the current-model
  marker vs cursor clearer since rows reflow as you pick.
- Single-keypress y/n for the LAUNCHER prompts too (first-run "Continue?",
  hardware A/C, directory M/D/I, delete-models). The app's model-download prompt
  is already single-key; the launcher is a separate stdlib-only codebase so it
  needs its own tiny single-char reader (it already has wait_for_keypress).
- File picker screen instead of typing a path.
- Decide whether "band" should pull vocals from HTDemucs (1 pass) instead of
  routing to RoFormer (2 passes). Currently routes to RoFormer for quality.
- Replace the heuristic fast/avg/slow model speed tier with real timing: time a
  short sample render per model once, cache it, show measured speed. Current
  tier is just arch-based guessing (VR=fast, MDX/Demucs=avg, RoFormer/_ft=slow).

## Later
- Move data OUT of the side-folder to OS-standard per-user dirs (DECIDED). Layout,
  split by purpose so the ~5GB of regenerable stuff stays out of Time Machine:
    - Caches (`~/Library/Caches/Stemchotic`, win `%LOCALAPPDATA%\Stemchotic\Cache`,
      linux `~/.cache/stemchotic`): python runtime, venv+deps, _app source, models,
      catalog cache. Regenerable -> not backed up, clearable.
    - App Support (`~/Library/Application Support/Stemchotic`, win `...\Data`,
      linux `~/.local/share/stemchotic`): small precious state (hardware choice, prefs).
    - Logs (`~/Library/Logs/Stemchotic`, win `...\Logs`, linux `~/.local/state/stemchotic`).
  One small per-OS path helper hides the branches. Add in-app "Reveal data folder"
  (open/explorer/xdg-open) and "Clear models / Reset" actions. Output stems stay
  next to the input (unchanged). Win: deletes the launcher's move-detection
  migration AND the macOS translocation guard, and lets the .app live in
  /Applications cleanly (data no longer depends on where the app sits). Slot into
  the Plan 3 launcher generalization.
- Ship as a uv-launcher app (mac/win/linux); CI bundles the chotic-ui submodule;
  separate CPU/CUDA builds on win/linux, MPS on mac.
- Trim the WezTerm payload in the package (keep WezTerm IN the .app so the first
  run has a window to show provisioning progress; just stop over-shipping). Two
  cuts, ~265MB -> ~68MB: (1) ship single-arch via `lipo -thin` instead of the fat
  universal binary; (2) drop the sibling binaries we never launch (wezterm-mux-server
  ~64MB, the wezterm CLI ~62MB, strip-ansi-escapes ~3MB) and keep only wezterm-gui,
  after verifying wezterm-gui runs standalone for `start -- <prog>`.
  Design rule (everything else): "bundled" = downloaded first-run into the
  side-folder (python/deps/ffmpeg already do this via the launcher + static-ffmpeg),
  NOT shipped in the package. WezTerm is the one deliberate exception because it
  renders the first-run UI.
- Persistent dev-mode model cache. From-source runs without the launcher cache
  models in /tmp/audio-separator-models (cleared on reboot -> re-downloads). Point
  the dev default at a persistent dir (e.g. ~/Library/Application Support/stemchotic
  or the side-folder). Packaged runs already use the side-folder. (Plan 3.)
- Migrate synchotic onto the chotic-ui submodule too, so the toolkit has one home
  (stemchotic already uses it; synchotic still has its own copy).
- Optional Gradio/desktop front-end for non-terminal users.
- Broaden Linux support (0.9.0 is validated only on a modern-glibc + NVIDIA box,
  run from a terminal). Known gaps, revisit if users complain: the launcher is
  built on Ubuntu 24.04 (glibc 2.39) so it won't start on older distros (build on
  manylinux_2_28 / Ubuntu 20.04 to fix); the CPU/AMD path is untested; the
  .desktop double-click (Terminal=true) is untested and flaky on GNOME.

## Done
- Extracted the TUI toolkit into the chotic-ui repo and submoduled it in
  (libs/chotic-ui, installed editable via requirements.txt).
