#!/usr/bin/env bash
# Stemchotic build helper. Builds the app by default.
#   ./build.sh          build the app
#   ./build.sh clean    clean up local installs first, then build
#   ./build.sh test     run the test suites
#   ./build.sh dev      run the TUI from source (not the packaged app)
# 'clean' can prefix any action, e.g. ./build.sh clean dev
set -eo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/.venv/bin/python"

if [ "${1:-}" = "clean" ]; then
    echo "Removing build output and anything the app installed locally..."
    rm -rf "$ROOT/build" "$ROOT/dist" "$HOME/.stemchotic" /tmp/audio-separator-models
    shift
fi

case "${1:-build}" in
    build | "")
        bash "$ROOT/packaging/macos/build_app.sh"
        ;;
    test)
        ( cd "$ROOT/libs/chotic-ui" && "$PY" -m pytest tests/ -q )
        ( cd "$ROOT" && "$PY" -m pytest tests/ -q )
        ;;
    dev)
        shift
        exec "$PY" "$ROOT/stemchotic.py" "$@"
        ;;
    *)
        echo "Usage: ./build.sh [clean] [build|test|dev]   (default: build)"
        exit 1
        ;;
esac
