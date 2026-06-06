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
drum-kit cascade (drums -> kick/snare/toms/cymbals via drumsep) is wired but the
drumsep checkpoint load is not yet verified.

## Install

Uses a standard venv + `requirements.txt`:

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

On Apple Silicon this pulls `audio-separator[cpu]` (CoreML acceleration). For an
NVIDIA GPU, change the extra to `[gpu]` in `requirements.txt`.

## Use

```sh
# Interactive picker: highlight the stems you want, hit Separate
python stemchotic.py

# Direct, via a CLI preset
python stemchotic.py drums song.wav

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
| `kit` | Kick, Snare, Toms, Cymbals | experimental drumsep cascade |
| `bass` | Bass | single file |

## Credits

- [python-audio-separator](https://github.com/karaokenerds/python-audio-separator) by Andrew Beveridge (MIT)
- [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) and its model authors
- TUI toolkit lifted from [synchotic](https://github.com/noahbaxter)

MIT licensed.
