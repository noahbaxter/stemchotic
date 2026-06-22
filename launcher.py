#!/usr/bin/env python3
"""
Stemchotic Launcher

Tiny launcher that fetches the app source from GitHub releases and runs it
in a uv-managed Python environment.
- Checks for updates on every launch
- Downloads and extracts new versions automatically
- Provisions Python + dependencies under .stemchotic/ on first run
- Handles directory changes (prompts to move/delete old data)
"""

import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import NoReturn
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LAUNCHER_VERSION = "1.0"
RELEASE_TAG = ""  # Injected to "dev-latest" for dev launcher builds
PYTHON_VERSION = "3.12"
UV_VERSION = "0.7.13"


def get_ssl_context():
    """Get SSL context with certifi certs, handling PyInstaller bundles."""
    try:
        import certifi

        if getattr(sys, "frozen", False):
            cafile = str(Path(sys._MEIPASS) / "certifi" / "cacert.pem")
        else:
            cafile = certifi.where()
        return ssl.create_default_context(cafile=cafile)
    except ImportError:
        return ssl.create_default_context()

_start_time = time.time()
_log_file = None

GITHUB_REPO = "noahbaxter/stemchotic"
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}/releases"


def get_release_url() -> str:
    """Get the release API URL, checking for test override and build-time channel."""
    for i, arg in enumerate(sys.argv):
        if arg == "--test-release" and i + 1 < len(sys.argv):
            tag = sys.argv[i + 1]
            print(f"  [TEST MODE] Using release: {tag}")
            return f"{GITHUB_API_BASE}/tags/{tag}"
    if RELEASE_TAG:
        return f"{GITHUB_API_BASE}/tags/{RELEASE_TAG}"
    return f"{GITHUB_API_BASE}/latest"


def is_offline_mode() -> bool:
    """Check if running in offline mode (skip update check)."""
    return "--offline" in sys.argv


def is_dev_mode() -> bool:
    """Check if running in dev mode (use local zip, no GitHub).

    Dev mode is active if:
    - --dev flag is passed, OR
    - A local app zip exists in the launcher directory (auto-detect for dev builds)
    """
    if "--dev" in sys.argv:
        return True
    # Auto-detect: if local zip exists, assume dev mode
    return get_local_zip_path().exists()


def is_clean_mode() -> bool:
    """Check if running in clean mode (delete installed app/env first)."""
    return "--clean" in sys.argv


def get_launcher_dir() -> Path:
    """Get directory containing the launcher (or .app bundle on macOS)."""
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable)
        # If inside a .app bundle, return folder containing the .app
        for parent in exe_path.parents:
            if parent.suffix == ".app":
                return parent.parent
        return exe_path.parent
    return Path(__file__).parent


def get_launcher_path() -> Path:
    """Get full path to the launcher exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return Path(__file__)


def should_relaunch_in_host(argv, has_terminal: bool, wezterm_exists: bool) -> bool:
    """True when we should re-exec into the bundled WezTerm host: a Finder
    double-click (no controlling terminal), not already hosted, and the WezTerm
    binary is present beside us. The `--hosted` sentinel is our own recursion
    guard (the hosted copy runs with a tty inside WezTerm)."""
    return "--hosted" not in argv and not has_terminal and wezterm_exists


def build_host_command(wezterm: str, lua: str, cwd: str, launcher_path: str, forward_args: list) -> list:
    """The argv to launch the bundled WezTerm GUI running this launcher as its
    program, in a dedicated process, with our config, forwarding the original
    args and appending the `--hosted` sentinel."""
    return [
        wezterm, "--config-file", lua,
        "start", "--always-new-process", "--cwd", cwd,
        "--", launcher_path, *forward_args, "--hosted",
    ]


def host_paths() -> tuple[Path, Path]:
    """(wezterm-gui, wezterm.lua) locations inside the bundle, relative to the
    launcher executable: wezterm-gui sits in Contents/MacOS beside the launcher,
    the config in Contents/Resources."""
    exe_dir = Path(sys.executable).parent
    return exe_dir / "wezterm-gui", exe_dir.parent / "Resources" / "wezterm.lua"


def get_app_dir() -> Path:
    """Get the extracted app directory. Dev channel uses separate dir to coexist with production."""
    subdir = "_app_dev" if RELEASE_TAG else "_app"
    return get_root_dir() / subdir


def get_root_dir() -> Path:
    """Get the .stemchotic directory."""
    return get_launcher_dir() / ".stemchotic"


def get_asset_name() -> str:
    """Get the release asset name (source zip, platform independent)."""
    return "app.zip"


def get_local_zip_path() -> Path:
    """Get path to local app zip (same folder as launcher)."""
    return get_launcher_dir() / get_asset_name()


def get_version_file() -> Path:
    """Get path to version marker file."""
    return get_app_dir() / ".version"


def get_installed_version() -> str:
    """Get version of currently extracted app."""
    version_file = get_version_file()
    if version_file.exists():
        return version_file.read_text().strip()
    return ""


# --- State file management ---

def get_state_dir() -> Path:
    """Get the directory for launcher state file."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "stemchotic"
    return Path.home() / ".stemchotic"


def get_state_file() -> Path:
    """Get path to state file."""
    return get_state_dir() / "state.json"


def read_state() -> dict:
    """Read launcher state from file."""
    state_file = get_state_file()
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def write_state(state: dict):
    """Write launcher state to file."""
    state_file = get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


# --- Logging ---

def init_logging():
    """Initialize daily log file."""
    global _log_file
    log_dir = get_root_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d")
    log_path = log_dir / f"launcher-{date_str}.log"
    try:
        _log_file = open(log_path, "a", encoding="utf-8")
        log(f"=== Launcher started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    except Exception:
        pass


def log(message: str):
    """Write message to log file."""
    if _log_file:
        try:
            timestamp = time.strftime("%H:%M:%S")
            _log_file.write(f"[{timestamp}] {message}\n")
            _log_file.flush()
        except Exception:
            pass


def close_logging():
    """Close log file."""
    global _log_file
    if _log_file:
        try:
            log("=== Launcher exiting ===")
            _log_file.close()
        except Exception:
            pass
        _log_file = None


# --- Directory change handling ---

def _state_key() -> str:
    """State key prefix so dev and prod launchers don't share state."""
    return "dev" if RELEASE_TAG else "prod"


def _save_launcher_state(current_path: str):
    """Save current launcher path to state file."""
    key = _state_key()
    state = read_state()
    state[f"launcher_path_{key}"] = current_path
    state[f"last_run_{key}"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Migrate: remove old shared keys so they don't cause false triggers
    state.pop("launcher_path", None)
    state.pop("last_run", None)
    write_state(state)


def _has_terminal() -> bool:
    """Check if we have an interactive terminal for prompts."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _prompt_directory_action() -> str:
    """Prompt user for directory change action. Returns 'M', 'D', or 'I'."""
    # No terminal - auto-ignore to avoid blocking
    if not _has_terminal():
        log("No terminal available, auto-ignoring old data")
        return "I"

    print("\nWhat would you like to do?")
    print("  [M] Move the data to the new location (faster startup)")
    print("  [D] Delete the old data (fresh download)")
    print("  [I] Ignore (leave old data, download fresh here)")

    while True:
        try:
            choice = input("\nChoice [M/D/I]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(1)

        if choice in ("M", "D", "I"):
            return choice
        print("Please enter M, D, or I.")


def _do_delete(old_root: Path):
    """Delete old .stemchotic folder."""
    log(f"Deleting old data: {old_root}")
    print(f"\nDeleting old data at {old_root}...")
    try:
        shutil.rmtree(old_root)
        print("Done!")
    except Exception as e:
        log(f"Delete failed: {e}")
        print(f"Warning: Failed to delete: {e}")
        print("Continuing anyway...")


def _do_move(old_root: Path) -> bool:
    """Move old .stemchotic to new location. Returns True on success."""
    new_root = get_root_dir()
    log(f"Moving data: {old_root} -> {new_root}")

    if new_root.exists():
        print(f"\nNote: {new_root} already exists, removing it first...")
        try:
            shutil.rmtree(new_root)
        except Exception as e:
            log(f"Failed to remove existing folder: {e}")
            print(f"Failed to remove existing folder: {e}")
            return False

    print("\nMoving data to new location...")
    try:
        shutil.move(str(old_root), str(new_root))
        print("Done!")
        return True
    except Exception as e:
        log(f"Move failed: {e}")
        print(f"Failed to move: {e}")
        return False


def _prompt_fallback() -> str:
    """Prompt for fallback action after move fails. Returns 'D' or 'I'."""
    # No terminal - auto-ignore
    if not _has_terminal():
        log("No terminal available, auto-ignoring after move failure")
        return "I"

    print("\nWould you like to:")
    print("  [D] Delete the old data instead")
    print("  [I] Ignore and download fresh")

    while True:
        try:
            choice = input("\nChoice [D/I]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(1)

        if choice in ("D", "I"):
            return choice
        print("Please enter D or I.")


def handle_directory_change():
    """Check if launcher moved and handle old .stemchotic folder."""
    current_path = str(get_launcher_path())
    key = _state_key()
    state = read_state()
    old_path = state.get(f"launcher_path_{key}") or state.get("launcher_path")

    # First run or same location
    if not old_path or old_path == current_path:
        _save_launcher_state(current_path)
        return

    old_root = Path(old_path).parent / ".stemchotic"

    # Old location has no data
    if not old_root.exists():
        _save_launcher_state(current_path)
        return

    log(f"Launcher moved: {old_path} -> {current_path}")

    # Prompt user
    print(f"\nIt looks like you moved the launcher from:")
    print(f"  {Path(old_path).parent}")
    print(f"\nFound cached app data at old location.")

    choice = _prompt_directory_action()
    log(f"User chose: {choice}")

    if choice == "M":
        if not _do_move(old_root):
            choice = _prompt_fallback()

    if choice == "D":
        _do_delete(old_root)
    elif choice == "I":
        log("Ignoring old data")
        print("\nIgnoring old data, will download fresh.")

    _save_launcher_state(current_path)
    print()


# --- GitHub API ---

def fetch_latest_release() -> dict:
    """Fetch latest release info from GitHub API."""
    url = get_release_url()
    req = Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "stemchotic-launcher")

    try:
        with urlopen(req, timeout=30, context=get_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 403:
            error_exit("GitHub API rate limit reached. Try again in a few minutes.")
        elif e.code == 404:
            error_exit("Release not found. Check the repository URL.")
        else:
            error_exit(f"GitHub API error: HTTP {e.code}")
    except URLError as e:
        reason = str(e.reason)
        if "WRONG_VERSION_NUMBER" in reason:
            error_exit(
                "Could not reach GitHub: SSL/TLS error.\n\n"
                "This usually means a proxy or firewall is intercepting the connection.\n"
                "Try disabling VPN/proxy or using a different network.\n"
                f"\nDetails: {reason}"
            )
        elif "CERTIFICATE" in reason:
            error_exit(
                f"Could not reach GitHub: SSL certificate error.\n\n"
                f"Launcher v{LAUNCHER_VERSION} - update at https://github.com/{GITHUB_REPO}/releases\n"
                f"\nDetails: {reason}"
            )
        else:
            error_exit(f"Could not reach GitHub. Check your internet connection.\n\nDetails: {reason}")
    except Exception as e:
        error_exit(f"Unexpected error checking for updates: {e}")


def get_download_url(release: dict) -> tuple[str, str]:
    """Get download URL and version from release info.

    For dev builds, uses asset's updated_at as version since the tag
    (dev-latest) never changes but the asset does on every push.
    """
    version = release.get("tag_name", "").lstrip("v")
    asset_name = get_asset_name()

    for asset in release.get("assets", []):
        if asset.get("name") == asset_name:
            if RELEASE_TAG:
                version = asset.get("updated_at", version)
            return asset.get("browser_download_url"), version

    error_exit(f"Release asset '{asset_name}' not found.\nThis platform may not be supported yet.")


def download_with_progress(url: str, dest: Path):
    """Download file with progress bar."""
    req = Request(url)
    req.add_header("User-Agent", "stemchotic-launcher")

    try:
        with urlopen(req, timeout=120, context=get_ssl_context()) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024

            dest.parent.mkdir(parents=True, exist_ok=True)

            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        pct = downloaded * 100 // total_size
                        bar_len = 30
                        filled = pct * bar_len // 100
                        bar = "=" * filled + "-" * (bar_len - filled)
                        mb_down = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        print(f"\r  [{bar}] {pct:3}% ({mb_down:.1f}/{mb_total:.1f} MB)", end="", flush=True)

            print()

    except HTTPError as e:
        error_exit(f"Failed to download update: HTTP {e.code}")
    except URLError as e:
        reason = str(e.reason)
        if "WRONG_VERSION_NUMBER" in reason:
            error_exit(
                "Download failed: SSL/TLS error.\n\n"
                "This usually means a proxy or firewall is intercepting the connection.\n"
                "Try disabling VPN/proxy or using a different network.\n"
                f"\nDetails: {reason}"
            )
        elif "CERTIFICATE" in reason:
            error_exit(
                f"Download failed: SSL certificate error.\n\n"
                f"Launcher v{LAUNCHER_VERSION} - update at https://github.com/{GITHUB_REPO}/releases\n"
                f"\nDetails: {reason}"
            )
        else:
            error_exit(f"Download failed. Check your connection.\n\nDetails: {reason}")
    except Exception as e:
        error_exit(f"Download failed: {e}")


# --- Extraction ---

def extract_app(zip_path: Path, version: str):
    """Extract app zip to .stemchotic/_app/ atomically."""
    app_dir = get_app_dir()
    temp_dir = app_dir.parent / "_app_temp"
    old_dir = app_dir.parent / "_app_old"

    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    print("  Extracting...")
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        # Swap: rename old out of the way, move new in, then delete old.
        # If anything fails mid-swap, at least one copy survives.
        if old_dir.exists():
            shutil.rmtree(old_dir)
        if app_dir.exists():
            app_dir.rename(old_dir)

        temp_dir.rename(app_dir)
        (app_dir / ".version").write_text(version)

        # Clean up old version
        if old_dir.exists():
            shutil.rmtree(old_dir, ignore_errors=True)

    except zipfile.BadZipFile:
        error_exit("Downloaded file is corrupted. Please try again.")
    except PermissionError as e:
        error_exit(f"Permission denied during extraction.\n\nDetails: {e}")
    except Exception as e:
        error_exit(f"Extraction failed: {e}")
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


# --- uv bootstrap ---

def get_uv_path() -> Path:
    """Get path to the launcher-managed uv binary."""
    name = "uv.exe" if sys.platform == "win32" else "uv"
    return get_root_dir() / "bin" / name


def _uv_target() -> tuple[str, str]:
    """(release asset name, archive member) for this platform/arch.

    >>> name, member = _uv_target()
    >>> name.startswith("uv-") and member in ("uv", "uv.exe")
    True
    """
    import platform as plat
    arch = plat.machine().lower()
    if sys.platform == "win32":
        return ("uv-x86_64-pc-windows-msvc.zip", "uv.exe")
    if sys.platform == "darwin":
        t = "aarch64-apple-darwin" if arch == "arm64" else "x86_64-apple-darwin"
        return (f"uv-{t}.tar.gz", "uv")
    t = "aarch64-unknown-linux-gnu" if arch in ("arm64", "aarch64") else "x86_64-unknown-linux-gnu"
    return (f"uv-{t}.tar.gz", "uv")


def ensure_uv() -> Path:
    """Download the pinned standalone uv binary on first run."""
    uv = get_uv_path()
    if uv.exists():
        return uv
    asset, member = _uv_target()
    url = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{asset}"
    print("  Fetching uv (package manager, ~15MB)...")
    log(f"Downloading uv: {url}")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / asset
        download_with_progress(url, archive)
        uv.parent.mkdir(parents=True, exist_ok=True)
        tmp = uv.with_suffix(".tmp")
        if asset.endswith(".zip"):
            with zipfile.ZipFile(archive) as zf:
                names = [n for n in zf.namelist() if n.endswith(member)]
                if not names:
                    error_exit(f"uv archive layout unexpected ({asset}); please report this.")
                with zf.open(names[0]) as src, open(tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        else:
            import tarfile
            with tarfile.open(archive) as tf:
                names = [n for n in tf.getnames() if n.endswith("/" + member) or n == member]
                if not names:
                    error_exit(f"uv archive layout unexpected ({asset}); please report this.")
                with tf.extractfile(names[0]) as src, open(tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        if sys.platform != "win32":
            os.chmod(tmp, 0o755)
        os.replace(tmp, uv)
    return uv


# --- Hardware questionnaire ---

def detect_nvidia() -> bool:
    """Check for an NVIDIA GPU via nvidia-smi."""
    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, timeout=10)
        return r.returncode == 0 and b"GPU" in r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def hardware_choice() -> str:
    """'gpu' | 'dml' | 'cpu'. Persisted; --setup re-asks."""
    state = read_state()
    if "--setup" not in sys.argv and state.get("hardware") in ("gpu", "dml", "cpu"):
        return state["hardware"]
    if sys.platform == "darwin":
        choice = "cpu"                      # CoreML/MPS comes with the cpu extra
    elif detect_nvidia():
        print("  NVIDIA GPU detected: using GPU acceleration.")
        choice = "gpu"
    elif sys.platform == "win32" and _has_terminal():
        print("\n  No NVIDIA GPU detected.")
        print("  [A] I have an AMD or Intel GPU (use DirectML acceleration)")
        print("  [C] CPU only (safe default)")
        try:
            ans = input("  Choice [A/C]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            ans = "C"
        choice = "dml" if ans == "A" else "cpu"
    else:
        choice = "cpu"
    state["hardware"] = choice
    write_state(state)
    return state["hardware"]


REQUIREMENTS_FOR = {"cpu": "requirements.txt", "gpu": "requirements-gpu.txt", "dml": "requirements-dml.txt"}


# --- Environment provisioning ---

def get_env_dir() -> Path:
    """Get the app venv directory."""
    return get_root_dir() / "_env"


def env_python() -> Path:
    """Get the env's python executable."""
    if sys.platform == "win32":
        return get_env_dir() / "Scripts" / "python.exe"
    return get_env_dir() / "bin" / "python"


def _fingerprint(req_path: Path, hardware: str) -> str:
    """Hash of everything that should trigger an env rebuild. App version is
    deliberately NOT included: app-only releases keep the env as is, deps
    re-sync only when a requirements file actually changes.

    >>> import tempfile
    >>> p = Path(tempfile.mkdtemp()) / "req.txt"
    >>> _ = p.write_text("torch==1.0\\n")
    >>> a = _fingerprint(p, "cpu")
    >>> a == _fingerprint(p, "cpu"), a == _fingerprint(p, "gpu")
    (True, False)
    """
    import hashlib
    h = hashlib.sha256()
    h.update(req_path.read_bytes())
    h.update(sys.platform.encode())
    h.update(hardware.encode())
    return h.hexdigest()


def ensure_env(hardware: str | None = None):
    """Create/refresh the app venv. No-op when the fingerprint matches.
    `hardware` forces a tier (used by the CPU fallback so a failing GPU
    install can't re-detect gpu and recurse under --setup)."""
    hardware = hardware or hardware_choice()
    req = get_app_dir() / REQUIREMENTS_FOR[hardware]
    fp_file = get_env_dir() / ".fingerprint"
    fp = _fingerprint(req, hardware)
    if fp_file.exists() and fp_file.read_text().strip() == fp and env_python().exists():
        log("Env up to date")
        print("  Env up to date.")
        return

    first_run = not fp_file.exists()
    if first_run:
        print("\n  First-time setup: Python runtime + audio dependencies.")
        print("  This downloads roughly 2.5GB and uses about 5GB of disk.")
        print("  (Separation models download later, per use, with their own prompt.)")
        if _has_terminal():
            ans = input("  Continue? [Y/n] ").strip().lower()
            if ans not in ("", "y", "yes"):
                error_exit("Setup declined. Nothing was installed.")
    else:
        print("  Updating dependencies...")

    uv = ensure_uv()
    env = os.environ.copy()
    env["UV_PYTHON_INSTALL_DIR"] = str(get_root_dir() / "python")
    env["STEMCHOTIC_ROOT"] = str(get_launcher_dir())   # so prep steps write to the side-folder

    def uv_run(*args):
        r = subprocess.run([str(uv), *args], cwd=get_app_dir(), env=env)
        if r.returncode != 0:
            error_exit(f"Setup step failed: uv {' '.join(args)}\nSee output above.")

    print("  Installing Python " + PYTHON_VERSION + "...")
    uv_run("python", "install", PYTHON_VERSION)
    # uv venv behavior on existing non-empty dirs varies across versions
    # (refuse vs prompt vs clobber); deleting first is deterministic.
    if get_env_dir().exists():
        shutil.rmtree(get_env_dir())
    uv_run("venv", "--python", PYTHON_VERSION, str(get_env_dir()))
    print("  Installing dependencies (the big download)...")
    r = subprocess.run([str(uv), "pip", "install", "--python", str(env_python()),
                        "-r", str(req)], cwd=get_app_dir(), env=env)
    if r.returncode != 0:
        if hardware != "cpu":
            print("\n  GPU install failed. Falling back to CPU (re-run with --setup to retry GPU).")
            log("GPU install failed, falling back to cpu")
            state = read_state(); state["hardware"] = "cpu"; write_state(state)
            ensure_env(hardware="cpu")
            return
        error_exit("Dependency install failed. See uv output above.")
    # Pre-fetch deps that download binaries on first use, so the first run needs
    # no extra download. static-ffmpeg pulls ffmpeg/ffprobe here. Best-effort:
    # if it fails (e.g. offline), the app fetches them lazily on first use.
    print("  Fetching ffmpeg...")
    subprocess.run([str(env_python()), "-c",
                    "import static_ffmpeg; static_ffmpeg.add_paths()"],
                   cwd=get_app_dir(), env=env)
    # Build the model-list cache now (pays the one-time torch import here, during
    # install) so the Models screen opens instantly from the very first launch.
    print("  Preparing model list...")
    subprocess.run([str(env_python()), "-c",
                    "from src.screens.model_picker import _load_catalog; _load_catalog()"],
                   cwd=get_app_dir(), env=env)
    fp_file.parent.mkdir(parents=True, exist_ok=True)
    fp_file.write_text(fp)


# --- Main ---

def wait_for_keypress():
    """Wait for any key press."""
    if sys.platform == "win32":
        import msvcrt
        msvcrt.getch()
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def error_exit(message: str) -> NoReturn:
    """Print error message and exit."""
    log(f"ERROR: {message}")
    close_logging()
    print(f"\n{'=' * 40}")
    print("ERROR")
    print("=" * 40)
    print(f"\n{message}")
    print("\nPress any key to exit...")
    try:
        wait_for_keypress()
    except (EOFError, KeyboardInterrupt, Exception):
        pass
    sys.exit(1)


def set_terminal_size(cols: int = 90, rows: int = 40):
    """Set terminal window size. Works on cmd.exe and PowerShell, not Windows Terminal."""
    if sys.platform == "win32":
        os.system(f"mode con: cols={cols} lines={rows}")
    else:
        # macOS/Linux: ANSI escape sequence
        print(f"\x1b[8;{rows};{cols}t", end="", flush=True)


def clean_install():
    """Delete the installed app, env, and tooling. Keeps models unless confirmed."""
    root = get_root_dir()
    log(f"Clean mode - cleaning {root}")
    print(f"  Cleaning {root}...")
    for sub in ("_app", "_app_dev", "_env", "bin", "python"):
        p = root / sub
        if p.exists():
            shutil.rmtree(p)
    models = root / "models"
    if models.exists() and _has_terminal():
        ans = input("  Also delete downloaded models (the big files)? [y/N] ").strip().lower()
        if ans in ("y", "yes"):
            shutil.rmtree(models)


def main():
    wezterm, lua = host_paths()
    if should_relaunch_in_host(sys.argv, _has_terminal(), wezterm.exists()):
        cmd = build_host_command(
            str(wezterm), str(lua), str(get_launcher_dir()),
            str(get_launcher_path()), sys.argv[1:],
        )
        os.execv(str(wezterm), cmd)  # replaces this process; does not return

    set_terminal_size(90, 40)
    init_logging()
    log(f"Launcher v{LAUNCHER_VERSION}")

    if RELEASE_TAG:
        print(f"\nStemchotic Launcher v{LAUNCHER_VERSION} [DEV]")
    else:
        print(f"\nStemchotic Launcher v{LAUNCHER_VERSION}")
    print("=" * 40)

    if is_clean_mode():
        clean_install()

    # Handle --dev: local development mode
    if is_dev_mode():
        log("Dev mode")
        print("[DEV MODE]")

        local_zip = get_local_zip_path()
        app_dir = get_app_dir()

        if local_zip.exists():
            # Zip found: replace _app only, delete zip after
            log(f"Found local zip: {local_zip}")
            print(f"  Found: {local_zip.name}")

            # Remove old _app if exists
            if app_dir.exists():
                shutil.rmtree(app_dir)

            extract_app(local_zip, "dev")
            print("  Extracted!")

            # Delete the zip
            local_zip.unlink()
            log("Deleted zip after extraction")
            print("  Zip deleted.")
        elif app_dir.exists():
            # No zip, but _app exists - use it
            log("No zip found, using existing _app")
            print("  No zip found, using existing app.")
        else:
            error_exit("No local zip and no existing app. Place app.zip next to the launcher first.")

    elif is_offline_mode():
        log("Offline mode - skipping update check")
        print("[OFFLINE MODE] Skipping update check...")
        if not (get_app_dir() / "stemchotic.py").exists():
            error_exit("No cached app found. Run without --offline to download.")
    else:
        handle_directory_change()

        print("Checking for updates...")
        release = fetch_latest_release()
        download_url, remote_version = get_download_url(release)
        log(f"Remote version: v{remote_version}")

        installed_version = get_installed_version()
        log(f"Installed version: v{installed_version}" if installed_version else "No version installed")

        needs_download = False
        if not (get_app_dir() / "stemchotic.py").exists():
            log("App not installed, will download")
            print(f"  App not installed, downloading v{remote_version}...")
            needs_download = True
        elif installed_version != remote_version:
            log(f"Update available: v{installed_version} -> v{remote_version}")
            print(f"  Update available: v{installed_version} -> v{remote_version}")
            needs_download = True
        else:
            log("Already up to date")
            print(f"  Up to date (v{installed_version})")

        if needs_download:
            with tempfile.TemporaryDirectory() as tmp:
                zip_path = Path(tmp) / "app.zip"
                print("\nDownloading...")
                log(f"Downloading from: {download_url}")
                download_with_progress(download_url, zip_path)
                extract_app(zip_path, remote_version)
                log(f"Extracted v{remote_version}")
                print("  Done!")

    ensure_env()
    app_entry = get_app_dir() / "stemchotic.py"
    if not app_entry.exists():
        error_exit(f"App entry not found after installation:\n{app_entry}")
    log("Launching stemchotic")
    print("\nLaunching stemchotic...\n" + "=" * 40 + "\n")
    launcher_flags = {"--offline", "--dev", "--clean", "--setup", "--hosted"}
    launcher_opts = {"--test-release"}  # These consume the next arg too
    filtered_args = []
    skip_next = False
    for arg in sys.argv[1:]:
        if skip_next:
            skip_next = False
        elif arg in launcher_opts:
            skip_next = True
        elif arg not in launcher_flags:
            filtered_args.append(arg)
    args = [str(env_python()), str(app_entry)] + filtered_args
    env = os.environ.copy()
    env["STEMCHOTIC_ROOT"] = str(get_launcher_dir())
    close_logging()
    sys.stdout.flush()  # execve discards unflushed buffers (piped stdout)
    if sys.platform == "win32":
        result = subprocess.run(args, env=env)
        sys.exit(result.returncode)
    else:
        os.execve(str(env_python()), args, env)


if __name__ == "__main__":
    main()
