import json

import pytest

from src.core import device


# --- pure: what CUDA_VISIBLE_DEVICES becomes for a preference ---

def test_cpu_pref_masks_cuda():
    for start in ({}, {"CUDA_VISIBLE_DEVICES": "0"}, {"CUDA_VISIBLE_DEVICES": ""}):
        env = dict(start)
        device.apply_to_env("cpu", env)
        assert env["CUDA_VISIBLE_DEVICES"] == ""


def test_gpu_pref_only_undoes_a_mask():
    env = {"CUDA_VISIBLE_DEVICES": ""}
    device.apply_to_env("gpu", env)
    assert "CUDA_VISIBLE_DEVICES" not in env

    env = {}
    device.apply_to_env("gpu", env)
    assert env == {}

    env = {"CUDA_VISIBLE_DEVICES": "0"}
    device.apply_to_env("gpu", env)
    assert env == {"CUDA_VISIBLE_DEVICES": "0"}


# --- startup applies in-process: a saved CPU pref must never restart the app ---

def test_startup_cpu_pref_masks_without_restarting(monkeypatch, tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"hardware": "gpu", "device": "cpu"}))
    monkeypatch.setattr(device.appstate, "state_file", lambda: p)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    def boom(*a, **k):
        raise AssertionError("startup must not restart the process")
    monkeypatch.setattr(device.os, "execve", boom)
    monkeypatch.setattr(device.subprocess, "run", boom)

    device.apply_pref_at_startup()
    assert device.os.environ["CUDA_VISIBLE_DEVICES"] == ""


# --- toggling restarts: real exec on POSIX, child process on Windows ---

def test_switch_on_windows_runs_child_and_exits_with_its_code(monkeypatch, tmp_path):
    p = tmp_path / "state.json"
    monkeypatch.setattr(device.appstate, "state_file", lambda: p)
    monkeypatch.setattr(device.sys, "platform", "win32")
    monkeypatch.setattr(device.os, "execve",
                        lambda *a: (_ for _ in ()).throw(AssertionError("no execve on Windows")))
    seen = {}

    class R:
        returncode = 3

    def fake_run(argv, env):
        seen["argv"], seen["env"] = argv, env
        return R()
    monkeypatch.setattr(device.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as e:
        device.switch_device("cpu")
    assert e.value.code == 3
    assert seen["env"]["CUDA_VISIBLE_DEVICES"] == ""
    assert seen["argv"][0] == device.sys.executable
    assert device.read_device_pref(p) == "cpu"


def test_switch_on_posix_execs(monkeypatch, tmp_path):
    monkeypatch.setattr(device.appstate, "state_file", lambda: tmp_path / "state.json")
    monkeypatch.setattr(device.sys, "platform", "linux")
    seen = {}

    def fake_execve(exe, argv, env):
        seen["env"] = env
        raise SystemExit(0)
    monkeypatch.setattr(device.os, "execve", fake_execve)

    with pytest.raises(SystemExit):
        device.switch_device("cpu")
    assert seen["env"]["CUDA_VISIBLE_DEVICES"] == ""


# --- pref persistence in state.json ---

def test_device_pref_defaults_to_gpu_when_absent(tmp_path):
    assert device.read_device_pref(tmp_path / "state.json") == "gpu"


def test_device_pref_round_trips(tmp_path):
    p = tmp_path / "state.json"
    device.write_device_pref("cpu", p)
    assert device.read_device_pref(p) == "cpu"


def test_writing_pref_preserves_other_state_keys(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"hardware": "gpu", "something": 1}))
    device.write_device_pref("cpu", p)
    data = json.loads(p.read_text())
    assert data["hardware"] == "gpu" and data["something"] == 1 and data["device"] == "cpu"


# --- the toggle only exists when the GPU env is installed ---

def test_toggle_available_only_for_gpu_tier(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"hardware": "gpu"}))
    assert device.gpu_toggle_available(p) is True
    p.write_text(json.dumps({"hardware": "cpu"}))
    assert device.gpu_toggle_available(p) is False
    p.write_text(json.dumps({"hardware": "dml"}))
    assert device.gpu_toggle_available(p) is False


def test_toggle_unavailable_when_state_missing(tmp_path):
    assert device.gpu_toggle_available(tmp_path / "nope.json") is False
