from src.core.updates import launcher_outdated, LATEST_LAUNCHER


def test_outdated_when_launcher_is_behind(monkeypatch):
    monkeypatch.setenv("STEMCHOTIC_LAUNCHER_VERSION", "1.0")
    # only meaningful if the build expects something newer than 1.0
    assert _parse(LATEST_LAUNCHER) > (1, 0)
    assert launcher_outdated() is True


def test_not_outdated_when_current(monkeypatch):
    monkeypatch.setenv("STEMCHOTIC_LAUNCHER_VERSION", LATEST_LAUNCHER)
    assert launcher_outdated() is False


def test_not_outdated_when_ahead(monkeypatch):
    monkeypatch.setenv("STEMCHOTIC_LAUNCHER_VERSION", "99.0")
    assert launcher_outdated() is False


def test_silent_when_launcher_version_absent(monkeypatch):
    # dev runs and pre-notifier launchers don't set the var: never nag
    monkeypatch.delenv("STEMCHOTIC_LAUNCHER_VERSION", raising=False)
    assert launcher_outdated() is False


def _parse(v):
    return tuple(int(x) for x in v.split("."))
