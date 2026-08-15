# Stemchotic

A dead-simple stem separator that gives you access to the best open models with no setup required. Just choose your stems and Stemchotic decides the best model and runs it.

It's a thin, opinionated TUI on top of
[python-audio-separator](https://github.com/karaokenerds/python-audio-separator),
which does the actual separation using models from
[Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui),
Demucs, and the BS-RoFormer family.

![Stemchotic](docs/screenshot.png)

### Download

[![macOS](https://img.shields.io/badge/macOS-Apple%20Silicon-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/noahbaxter/stemchotic/releases/latest/download/Stemchotic.dmg)
[![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/noahbaxter/stemchotic/releases/latest/download/Stemchotic.exe)
[![Linux](https://img.shields.io/badge/Linux-x86__64-FCC624?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/noahbaxter/stemchotic/releases/latest/download/Stemchotic)

Also on [dichoticstudios.com](https://dichoticstudios.com/plugins/stemchotic).

## Status

Stemchotic is currently in Beta on macOS, Windows, and Linux.

- Pick the instruments you want and that's what you get. Each uses my preferred splitting model either for quality or speed, but you're able to easily set alternate model at any time.
- Drum-kit splitting into kick / snare / toms / cymbals (choice of 4/5/6-pieces).
- Routes to the best open models (BS-RoFormer, DrumSep, Demucs) and handles all downloads.
- Automatically sets up GPU acceleration if you have the hardware for it.
- Useable as an interactive TUI for normies or one-line CLI for scripting.

## Install

Use the download button for your platform above, then:

**macOS** (Apple Silicon)
1. Open `Stemchotic.dmg`. In the window that opens, drag the **Stemchotic** icon onto the **Applications** folder.
2. Open **Stemchotic** like any other macOS app.

**Windows 10/11**
1. Double-click `Stemchotic.exe`. Windows will say "Windows protected your PC", so click **More info** then **Run anyway**.

**Linux**
1. Mark `Stemchotic` executable and run it from a terminal.

The first launch downloads a Python virtual environment and the audio engine, 1-2.5 GB depending on your hardware, so give it a few minutes. After that it'll open in seconds.

Separation models download the first time you use each one (50-670 MB apiece) and
are cached for repeat use. The list is sourced from python-audio-separator; the `models.json` in
this repo adds quality rankings and a few open-weight extras (DrumSep,
BS-Roformer-SW). Each model is pulled from its public host on first use.

## Using it

1. Open Stemchotic (double-click it).
2. Scroll the part list and press **Space** to select each stem you want.
3. Press **S** to start splitting.
4. Type the path to your audio file, or just drag the file onto the window.
5. Stemchotic separates the stems, names them clearly, and drops them in the same folder as the original.

That's the whole loop. If you want more control the window has two panes, **Tab**
switches between **Stem Selection** (left) and **Settings** (right). Each highlighted
stem shows the model it'll use, and the line under the box is the plan. **M** opens the Model 
picker screen. Settings cover **Quality** (Best / Fast), **Scope** (only your stems or 
everything the models make), **Drum kit** (4/5/6-piece, from a song or an existing drum stem), 
and output format.

### Maintenance flags

If you have any issues, these maintenance flags can be run in a command line.

| Flag | What it does |
|---|---|
| `--clean` | Reinstalls the app and env; asks before touching downloaded models |
| `--setup` | Re-runs the hardware/GPU question |
| `--offline` | Skips the update check and launches from the local install |
| `--uninstall` | Removes everything it installed (cache, state, logs, menu entry); leaves the launcher |

## For devs

<details>
<summary><b>Command line</b> (presets, flags, scripting)</summary>

For scripting and power users (run from a source checkout; the installed launcher
binary accepts the same arguments). Pass a preset and/or an audio file, plus flags:

```sh
python stemchotic.py                     # interactive picker
python stemchotic.py drums song.wav -y   # a preset, headless
python stemchotic.py --list              # list presets
```

**Presets:**

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

**Flags** (override the preset, or skip presets with `--stems`):

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

</details>

<details>
<summary><b>From source</b></summary>

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

</details>

## Credits

- [python-audio-separator](https://github.com/karaokenerds/python-audio-separator) by Andrew Beveridge (MIT)
- [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) and its model authors
- TUI via [chotic-ui](https://github.com/noahbaxter/chotic-ui) (originally lifted from synchotic)

MIT licensed.
