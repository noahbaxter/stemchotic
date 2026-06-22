# Stemchotic

A dead-simple stem separator. Pick what you want out of a track ("vocals",
"drum kit pieces", "full band") and Stemchotic picks the right model for you and
runs it. No 40-item dropdown of cryptic model names.

It's a thin, opinionated TUI on top of
[python-audio-separator](https://github.com/karaokenerds/python-audio-separator),
which does the actual separation using models from
[Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui),
Demucs, and the BS-RoFormer family.

## Status

Working for single-model stems. The picker, live plan text, single-stem and
multi-stem (filtered) output, vocals/instrumental routing to RoFormer, output
next to the input, and silenced logging are all verified on real files. The
drum-kit cascade (drums via HTDemucs, then split into kit pieces via DrumSep)
is verified end to end on real audio, in 4/5/6-piece form and in WAV and FLAC
output. Two SOTA public-weight models ship via a registry overlay: jarredou's
DrumSep 5-stem (kit default) and BS-Roformer-SW (guitar/piano/other default,
HTDemucs 6s as the fast fallback). Launcher built and release pipeline in
place; Windows/Linux smoke tests pending.

## Install

Grab the build for your OS from
[GitHub Releases](https://github.com/noahbaxter/stemchotic/releases/latest):

- macOS: `Stemchotic.dmg` (open it and drag Stemchotic to Applications)
- Windows: `stemchotic-launcher.exe`
- Linux: `stemchotic-launcher-linux`

On macOS, launch Stemchotic from Applications. On Windows and Linux, put the
launcher in a folder you like and run it. Everything it installs goes into the
standard per-user app directories for your OS (on macOS, `~/Library`), so
nothing lands in system directories.

**Windows:** the launcher is not yet code-signed, so the first run shows a
"Windows protected your PC" SmartScreen prompt. Click **More info**, then
**Run anyway**. On first run it downloads a small terminal (WezTerm) to give
Stemchotic its own window; later launches open straight into it.

**Linux:** after the first run (launch it from a terminal once), Stemchotic
also appears in your application menu and opens in your default terminal.

**First run:** the launcher checks for the latest release, downloads the app,
then asks one consent question before installing Python and the audio
dependencies. On GPU platforms this is roughly a 2.5 GB download; on Apple
Silicon it's much less. The launcher auto-detects NVIDIA GPUs. On Windows
without NVIDIA it asks whether you have an AMD or Intel GPU (DirectML
acceleration) or want the CPU build.

Separation models are not bundled. Each model downloads on first use with its
own size prompt. Pass `-y/--yes` to stemchotic (or use a CLI preset with
`--yes`) to skip those prompts.

**Later runs:** instant launch with an automatic update check.

### Maintenance flags

| Flag | What it does |
|---|---|
| `--clean` | Reinstalls the app and env; asks before touching downloaded models |
| `--setup` | Re-runs the hardware/GPU question |
| `--offline` | Skips the update check and launches from the local install |

### From source (developers)

The TUI toolkit lives in the [chotic-ui](https://github.com/noahbaxter/chotic-ui)
submodule, so clone with submodules (or init them after):

```sh
git clone --recurse-submodules https://github.com/noahbaxter/stemchotic
# already cloned? -> git submodule update --init

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt    # installs audio-separator + the chotic-ui submodule (editable)
```

On Apple Silicon this pulls `audio-separator[cpu]` (CoreML acceleration). For an
NVIDIA GPU, change the extra to `[gpu]` in `requirements.txt`.

## Use

```sh
# Interactive picker: highlight the stems you want, hit Separate
python stemchotic.py

# Direct, via a CLI preset (-y skips per-model download prompts)
python stemchotic.py drums song.wav -y

# List presets
python stemchotic.py --list
```

Output files are written **next to the input file**.

## Interface

The TUI is two panes. **Tab** switches focus between **Stem Selection** (left:
the seven instrument stems plus a Residual toggle) and **Settings** (right). Each
highlighted stem shows the model it resolves to, and the line under the box is the
live plan. **M** opens the Models screen (Targets | Models), **S** opens the drum
split. Settings cover **Quality** (Best / Fast), **Scope** (My picks / Everything
the models make), **Drum kit** (Split off/4/5/6, Source song/stem), and output
format. Your selection persists for the whole session.

## Presets (CLI shortcuts)

| Key | Does |
|---|---|
| `vocals` | Vocals + Instrumental (BS-RoFormer) |
| `instrumental` | Instrumental only |
| `band` | Drums, Bass, Vocals, Guitar, Piano, Other (Drums/Bass via HTDemucs, others via BS-Roformer-SW, vocals via RoFormer) |
| `drums` | Drums, single file |
| `bass` | Bass, single file |
| `kit` | Drums + 5-piece DrumSep cascade (kick/snare/toms/hh/cymbals) |
| `kit4` | Drums + 4-piece cascade (hh merged into cymbals) |
| `kit6` | Drums + 6-piece cascade (kick/snare/toms/hh/ride/crash) |
| `kitsplit` | Input is already a drum stem: DrumSep it directly, no extraction |

## Headless / CLI

Any preset config can be overridden with flags, or you can skip presets entirely
and drive it with `--stems`:

| Flag | What it does |
|---|---|
| `--stems S1,S2,...` | Explicit selection (Vocals/Instrumental/Drums/Bass/Guitar/Piano/Other); overrides the preset |
| `--quality best\|fast` | Model tier (default best) |
| `--format wav\|flac\|mp3` | Output format (default wav) |
| `--all` | Keep everything the models make (forces residual off) |
| `--residual` | Also write `[Residual]` = mix minus your picks |
| `--split off\|4\|5\|6` | Drum-kit split |
| `--source song\|stem` | Treat the input as a full song or an existing drum stem |
| `-y`, `--yes` | Skip per-model download prompts |

```sh
python stemchotic.py band song.wav --quality fast
python stemchotic.py song.wav --stems Vocals --residual
python stemchotic.py kitsplit drums.wav        # input is already a drum stem
```

## Credits

- [python-audio-separator](https://github.com/karaokenerds/python-audio-separator) by Andrew Beveridge (MIT)
- [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) and its model authors
- TUI via [chotic-ui](https://github.com/noahbaxter/chotic-ui) (originally lifted from synchotic)

MIT licensed.
