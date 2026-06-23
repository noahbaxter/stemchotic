# Stemchotic Backlog

## Next up
- Test the Windows GPU paths before claiming GPU support. 0.9.0 is verified on
  Windows CPU only (the test VM had no GPU). NVIDIA hits requirements-gpu.txt (the
  CUDA path that needed an onnxruntime pin on Linux; Windows wheels differ) and
  AMD/Intel hits requirements-dml.txt (DirectML, fully untested). Run a real
  separation on a Windows GPU box for each.
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
- Clearer current-model marker vs cursor in the model picker (rows reflow as you
  pick, so it's easy to lose which one is selected). Reset-to-defaults and the
  stable right-pane order already shipped.
- File picker screen instead of typing a path.
- Decide whether "band" should pull vocals from HTDemucs (1 pass) instead of
  routing to RoFormer (2 passes). Currently routes to RoFormer for quality.
- Replace the heuristic fast/avg/slow model speed tier with real timing: time a
  short sample render per model once, cache it, show measured speed. Current
  tier is just arch-based guessing (VR=fast, MDX/Demucs=avg, RoFormer/_ft=slow).

## Later
- Trim the bundled macOS WezTerm payload, ~265MB -> ~68MB. Two cuts: (1) ship
  single-arch via `lipo -thin` instead of the fat universal binary; (2) drop the
  sibling binaries we never launch (wezterm-mux-server ~64MB, the wezterm CLI
  ~62MB, strip-ansi-escapes ~3MB) and keep only wezterm-gui, after verifying
  wezterm-gui runs standalone for `start -- <prog>`. macOS-only now: Windows
  downloads WezTerm first-run, Linux uses the native terminal.
- Windows code signing (OV/EV cert) to drop the SmartScreen "unknown publisher"
  wall. Deferred for 0.9.x (shipping unsigned with documented Run-anyway steps).
- Intel Mac support. The launcher is built arm64-only (Apple Silicon); a universal
  or x86_64 build would be needed for Intel Macs.
- Persistent dev-mode model cache. From-source runs (no launcher) cache models in
  /tmp/audio-separator-models (cleared on reboot -> re-downloads). Point the dev
  default at the OS cache dir. Packaged runs already use it.
- In-app "Reveal data folder" action (open / explorer / xdg-open). Clearing is
  already covered by the launcher's --clean / --uninstall.
- Broaden Linux support (0.9.0 is validated only on a modern-glibc + NVIDIA box,
  run from a terminal). Known gaps, revisit if users complain: the launcher is
  built on Ubuntu 24.04 (glibc 2.39) so it won't start on older distros (build on
  manylinux_2_28 / Ubuntu 20.04 to fix); the CPU/AMD path is untested; the
  .desktop double-click (Terminal=true) is untested and flaky on GNOME.
- Migrate synchotic onto the chotic-ui submodule too, so the toolkit has one home
  (stemchotic already uses it; synchotic still has its own copy).
- Optional Gradio/desktop front-end for non-terminal users.
