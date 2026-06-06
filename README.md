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

Early skeleton. The menu, templates, and single-model templates are wired. The
drum-kit cascade (drums -> kick/snare/toms/cymbals via drumsep) is stubbed and
not yet verified.

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
# Interactive menu
python stemchotic.py

# Direct
python stemchotic.py vocals song.wav

# List templates
python stemchotic.py --list
```

## Templates

| Key | Template | Best for |
|---|---|---|
| `vocals` | Vocals + Instrumental | karaoke, acapellas |
| `instrumental` | Clean Instrumental | backing tracks |
| `band` | Full Band (6 stems) | remixing |
| `drums` | Drums (isolated) | drumless tracks |
| `kit` | Drum Kit Pieces (experimental) | charting: kick/snare/toms/cymbals |
| `bass` | Bass | basslines |

## Credits

- [python-audio-separator](https://github.com/karaokenerds/python-audio-separator) by Andrew Beveridge (MIT)
- [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) and its model authors
- TUI toolkit lifted from [synchotic](https://github.com/noahbaxter)

MIT licensed.
