import launcher


def test_should_relaunch_true_when_no_tty_no_sentinel_and_wezterm_present():
    assert launcher.should_relaunch_in_host([], has_terminal=False, wezterm_exists=True) is True


def test_should_relaunch_false_when_already_hosted():
    assert launcher.should_relaunch_in_host(["--hosted"], has_terminal=False, wezterm_exists=True) is False


def test_should_relaunch_false_when_has_terminal():
    assert launcher.should_relaunch_in_host([], has_terminal=True, wezterm_exists=True) is False


def test_should_relaunch_false_when_no_wezterm():
    assert launcher.should_relaunch_in_host([], has_terminal=False, wezterm_exists=False) is False


def test_build_host_command_shape():
    cmd = launcher.build_host_command(
        "/A/wezterm-gui", "/A/wezterm.lua", "/work", "/A/stemchotic-launcher", ["--offline"]
    )
    assert cmd == [
        "/A/wezterm-gui", "--config-file", "/A/wezterm.lua",
        "start", "--always-new-process", "--cwd", "/work",
        "--", "/A/stemchotic-launcher", "--offline", "--hosted",
    ]


def test_build_host_command_with_no_forward_args():
    cmd = launcher.build_host_command(
        "/A/wezterm-gui", "/A/wezterm.lua", "/work", "/A/stemchotic-launcher", []
    )
    assert cmd == [
        "/A/wezterm-gui", "--config-file", "/A/wezterm.lua",
        "start", "--always-new-process", "--cwd", "/work",
        "--", "/A/stemchotic-launcher", "--hosted",
    ]
