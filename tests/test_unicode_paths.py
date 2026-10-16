"""The bundled keyboard reader must preserve paths through file validation."""
from types import SimpleNamespace

import pytest

from chotic_ui.primitives import keyboard_input
from stemchotic import clean_path
from src.core import separator


def test_unicode_path_reaches_separator(tmp_path, monkeypatch, capsys):
    folder = tmp_path / 'Bomber \uff0f Bakudanma (\u7206\u5f3e\u9b54)'
    folder.mkdir()
    audio = folder / 'song.opus'
    audio.touch()
    keys = iter('"' + str(audio) + '"\r')
    monkeypatch.setattr(keyboard_input, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(keyboard_input, 'msvcrt', SimpleNamespace(
        getwch=lambda: next(keys),
        getch=lambda: next(keys).encode('cp1252', errors='replace'),
    ), raising=False)

    received = clean_path(keyboard_input.input_with_esc())
    assert received == str(audio)
    # No stems: stop immediately after the real file-existence check, before
    # loading models or trying to decode the placeholder audio file.
    with pytest.raises(RuntimeError, match='^Nothing selected\\.$'):
        separator.run([], received)
