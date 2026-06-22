#!/usr/bin/env bash
# Build an unsigned (ad-hoc signed) Stemchotic.app for LOCAL testing.
# Prove-it build: stemchotic launcher + bundled WezTerm, no Developer ID / notarization.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"   # CI sets PYTHON=python; local uses the venv
BUILD="$ROOT/build/macos"
DIST="$ROOT/dist"
WEZ_VER="20240203-110809-5046fc22"
WEZ_URL="https://github.com/wezterm/wezterm/releases/download/$WEZ_VER/WezTerm-macos-$WEZ_VER.zip"
WEZ_CACHE="$ROOT/build/wezterm-$WEZ_VER"

echo "==> Ensuring build deps (pyinstaller, certifi)"
"$PY" -m pip install -q pyinstaller certifi

echo "==> Building the launcher binary with PyInstaller"
rm -rf "$BUILD"; mkdir -p "$BUILD"
CERTIFI_PATH="$("$PY" -c 'import certifi; print(certifi.where())')"
"$PY" -m PyInstaller --onefile --name stemchotic-launcher --clean --noconfirm \
    --distpath "$BUILD/pyi" --workpath "$BUILD/work" --specpath "$BUILD" \
    --add-data "$CERTIFI_PATH:certifi" --hidden-import certifi \
    "$ROOT/launcher.py"

echo "==> Fetching WezTerm $WEZ_VER (cached after first run)"
if [ ! -d "$WEZ_CACHE" ]; then
    mkdir -p "$WEZ_CACHE"
    curl -fsSL -o "$WEZ_CACHE/wz.zip" "$WEZ_URL"
    ( cd "$WEZ_CACHE" && unzip -q wz.zip )
fi
WEZ_MACOS="$WEZ_CACHE/WezTerm-macos-$WEZ_VER/WezTerm.app/Contents/MacOS"

echo "==> Assembling Stemchotic.app"
APP="$DIST/Stemchotic.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BUILD/pyi/stemchotic-launcher" "$APP/Contents/MacOS/"
for b in wezterm wezterm-gui wezterm-mux-server strip-ansi-escapes; do
    cp "$WEZ_MACOS/$b" "$APP/Contents/MacOS/"
done
cp "$ROOT/packaging/macos/wezterm.lua" "$APP/Contents/Resources/"
cp "$ROOT/packaging/macos/WezTerm-LICENSE.txt" "$APP/Contents/Resources/"
cp "$ROOT/packaging/macos/Stemchotic.icns" "$APP/Contents/Resources/"
cp "$ROOT/packaging/macos/Info.plist" "$APP/Contents/"

echo "==> Building dev app.zip (local source, runs offline) next to the .app"
mkdir -p "$DIST"
rm -f "$DIST/app.zip"
( cd "$ROOT" && git ls-files | grep -v '^libs/chotic-ui$' | zip -q "$DIST/app.zip" -@ )
( cd "$ROOT/libs/chotic-ui" && git ls-files | sed 's|^|libs/chotic-ui/|' \
    | ( cd "$ROOT" && zip -q "$DIST/app.zip" -@ ) )
printf 'dev-local\n' > "$ROOT/.version"
( cd "$ROOT" && zip -q "$DIST/app.zip" .version )
rm -f "$ROOT/.version"

echo "==> Ad-hoc signing for Apple Silicon"
codesign --force --deep -s - "$APP"

echo ""
echo "Built: $APP"
echo "Dev source zip: $DIST/app.zip (launcher dev-mode will extract it)"
echo "Double-click Stemchotic.app in $DIST to test."
