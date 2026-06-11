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
drum-kit cascade (drums via HTDemucs, then split into kit pieces via MDX23C
DrumSep) is verified end to end on real audio, in both 4-piece and 6-piece
form and in WAV and FLAC output. Launcher built and release pipeline in place;
Windows/Linux smoke tests pending.

## Install

Grab the launcher for your OS from
[GitHub Releases](https://github.com/noahbaxter/stemchotic/releases/latest):

- `stemchotic-launcher-macos`
- `stemchotic-launcher.exe`
- `stemchotic-launcher-linux`

Put it in a folder you like and run it. Everything it installs goes into a
`.stemchotic/` folder next to it, so nothing lands in system directories.

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

In the picker, each stem you highlight implies its model, and the line under the
box shows the exact plan (which model(s), how many passes, single-stem vs
filtered). Pick exactly one stem and it optimises for that one file; pick vocals
or instrumental and it routes to the dedicated BS-RoFormer model. The drum-kit
pieces (kick/snare/toms/cymbals) are nested under Drums. "Advanced" lets you set
the output format or browse all ~160 models (filter by typing `/`, each tagged
with its architecture and best stem) and force one directly. Your selection
persists for the whole session.

## Presets (CLI shortcuts)

| Key | Stems | Notes |
|---|---|---|
| `vocals` | Vocals, Instrumental | BS-RoFormer |
| `instrumental` | Instrumental | BS-RoFormer |
| `band` | Drums, Bass, Vocals, Guitar, Piano, Other | HTDemucs 6-stem (vocals routed to RoFormer) |
| `drums` | Drums | single file |
| `kit` | Kick, Snare, Toms, HH, Ride, Crash | MDX23C DrumSep cascade (6 piece) |
| `kit4` | Kick, Snare, Toms, Cymbals | same cascade, cymbals summed (4 piece) |
| `bass` | Bass | single file |

## Credits

- [python-audio-separator](https://github.com/karaokenerds/python-audio-separator) by Andrew Beveridge (MIT)
- [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) and its model authors
- TUI via [chotic-ui](https://github.com/noahbaxter/chotic-ui) (originally lifted from synchotic)

MIT licensed.
