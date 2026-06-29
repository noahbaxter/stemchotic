import json

from src.core import device


# --- pure: what CUDA_VISIBLE_DEVICES should become for a preference ---

def test_target_visible_cpu_masks_cuda():
    assert device.target_visible("cpu") == ""


def test_target_visible_gpu_leaves_cuda_alone():
    assert device.target_visible("gpu") is None


# --- pure: when a startup re-exec is needed (and never loops) ---

def test_cpu_pref_reexecs_when_cuda_is_visible():
    assert device.needs_reexec("cpu", None, already_applied=False) is True
    assert device.needs_reexec("cpu", "0", already_applied=False) is True


def test_cpu_pref_no_reexec_when_already_masked():
    assert device.needs_reexec("cpu", "", already_applied=False) is False


def test_gpu_pref_reexecs_only_to_unmask():
    assert device.needs_reexec("gpu", "", already_applied=False) is True
    assert device.needs_reexec("gpu", None, already_applied=False) is False
    assert device.needs_reexec("gpu", "0", already_applied=False) is False


def test_sentinel_blocks_any_further_reexec():
    # The re-exec'd child must never bounce again, whatever the state.
    assert device.needs_reexec("cpu", None, already_applied=True) is False
    assert device.needs_reexec("gpu", "", already_applied=True) is False


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
