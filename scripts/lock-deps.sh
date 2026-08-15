#!/usr/bin/env bash
# Regenerate requirements*.lock from requirements*.txt.
#
# The .txt files are the constraints we write by hand. The .lock files pin every
# transitive dep to an exact version, and are what the launcher actually installs.
# Nothing in the dependency tree moves until you run this.
#
# Run it when you change a .txt file, or deliberately to pick up upstream fixes.
# Commit the result: the release zip is built from `git ls-files`, so an
# uncommitted lock never reaches users.
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Use the same uv the launcher installs with, so the resolution users get on their
# machines matches the one locked here.
UV_VERSION="$(grep -oE '^UV_VERSION = "[^"]+"' "$ROOT/launcher.py" | cut -d'"' -f2)"
[ -n "$UV_VERSION" ] || { echo "could not read UV_VERSION from launcher.py" >&2; exit 1; }

case "$(uname -s)-$(uname -m)" in
    Darwin-arm64)  ASSET="uv-aarch64-apple-darwin" ;;
    Darwin-x86_64) ASSET="uv-x86_64-apple-darwin" ;;
    Linux-aarch64) ASSET="uv-aarch64-unknown-linux-gnu" ;;
    Linux-x86_64)  ASSET="uv-x86_64-unknown-linux-gnu" ;;
    *) echo "unsupported host: $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

UV_DIR="$ROOT/build/lock-uv/$UV_VERSION"
UV="$UV_DIR/uv"
if [ ! -x "$UV" ]; then
    echo "Fetching uv $UV_VERSION..."
    mkdir -p "$UV_DIR"
    curl -fsSL "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$ASSET.tar.gz" \
        | tar xz -C "$UV_DIR" --strip-components=1
fi

# --universal resolves for every platform at once (markers, not one lock per OS), so
# a mac can generate the lock Windows and Linux install from. --python-version must
# match PYTHON_VERSION in launcher.py.
PYTHON_VERSION="$(grep -oE '^PYTHON_VERSION = "[^"]+"' "$ROOT/launcher.py" | cut -d'"' -f2)"
for base in requirements requirements-gpu requirements-dml; do
    echo "Locking $base..."
    ( cd "$ROOT" && "$UV" pip compile --universal \
        --python-version "$PYTHON_VERSION" --emit-index-url \
        "$base.txt" -o "$base.lock" )
done

echo
echo "Done. Review the diff, then commit the .lock files."
