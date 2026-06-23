import io
import sys

from src.core import applog


def test_write_is_noop_before_init():
    applog._log_file = None
    applog.write("nothing should happen")   # must not raise


def test_tee_dual_writes_and_strips_ansi_on_file_side():
    stream, fp = io.StringIO(), io.StringIO()
    tee = applog._Tee(stream, fp)
    tee.write("\x1b[31mred\x1b[0m\rline")
    assert stream.getvalue() == "\x1b[31mred\x1b[0m\rline"   # terminal sees raw
    assert fp.getvalue() == "redline"                          # file is clean


def test_init_creates_dated_log_and_mirrors_stderr(tmp_path, monkeypatch):
    monkeypatch.setattr(applog, "log_dir", lambda: tmp_path)
    applog._log_file = None
    saved = sys.stderr
    try:
        applog.init("0.9.1")
        applog.write("hello-marker")
        print("stderr-marker", file=sys.stderr)
    finally:
        sys.stderr = saved
        applog._log_file = None

    log = next(tmp_path.glob("app-*.log")).read_text()
    assert "Session start: stemchotic 0.9.1" in log
    assert "hello-marker" in log
    assert "stderr-marker" in log     # stderr was mirrored into the file
