import sys

from src.core.progress import capture_tqdm


def test_capture_swaps_the_stderr_object_not_the_fd():
    # The Windows first-run download crash (OSError [WinError 1] Incorrect
    # function, CPython bpo-30555) came from os.dup2 on fd 2, which breaks
    # Python's _io._WindowsConsoleIO. Capture must replace the sys.stderr
    # *object* so it never touches the console handle.
    original = sys.stderr
    with capture_tqdm("Step"):
        assert sys.stderr is not original
    assert sys.stderr is original


def test_download_bar_renders_as_downloading_and_swallows_raw(capsys):
    with capture_tqdm("Separating"):
        sys.stderr.write("\r 42%|####  | 268M/639M [00:09<00:13, 28.0MiB/s]")
        sys.stderr.flush()
    captured = capsys.readouterr()
    assert "MiB/s" not in captured.err        # raw tqdm bar never leaks to stderr
    assert "Downloading models" in captured.out
    assert "42%" in captured.out


def test_inference_bar_uses_the_step_label(capsys):
    with capture_tqdm("Separating"):
        sys.stderr.write("\r 50%|#####     | 5/10 [00:01<00:01, 4.00it/s]")
        sys.stderr.flush()
    out = capsys.readouterr().out
    assert "Separating" in out
    assert "50%" in out


def test_proxy_delegates_unknown_attrs_to_real_stderr():
    # Libraries that introspect sys.stderr (fileno, encoding, buffer) during a
    # run must still get a working stream, not AttributeError.
    saved = sys.stderr
    with capture_tqdm("Step"):
        assert sys.stderr.fileno() == saved.fileno()
        assert sys.stderr.encoding == saved.encoding
        assert sys.stderr.buffer is saved.buffer
