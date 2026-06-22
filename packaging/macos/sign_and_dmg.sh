#!/usr/bin/env bash
# Sign (Developer ID, hardened runtime, inside-out), notarize, and DMG the built
# Stemchotic.app. Works locally (uses your keychain identity + notarytool profile)
# and in CI (override IDENTITY / NOTARY_PROFILE via env after importing the cert).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/Stemchotic.app"
DMG="$DIST/Stemchotic.dmg"
ENTITLEMENTS="$ROOT/packaging/macos/entitlements.plist"
IDENTITY="${MACOS_SIGN_IDENTITY:-Developer ID Application: Noah Baxter (KUP5WU7WPC)}"
NOTARY_PROFILE="${NOTARY_PROFILE:-notarytool-profile}"

[ -d "$APP" ] || { echo "No $APP. Run build_app.sh first."; exit 1; }

echo "==> Signing inside-out (hardened runtime + secure timestamp)"
# WezTerm's helper binaries first (no special entitlements needed).
for b in wezterm wezterm-mux-server strip-ansi-escapes wezterm-gui; do
    codesign --force --options runtime --timestamp -s "$IDENTITY" "$APP/Contents/MacOS/$b"
done
# The launcher needs the hardened-runtime exceptions above.
codesign --force --options runtime --timestamp --entitlements "$ENTITLEMENTS" \
    -s "$IDENTITY" "$APP/Contents/MacOS/stemchotic-launcher"
# Finally the bundle itself (same entitlements as its main executable).
codesign --force --options runtime --timestamp --entitlements "$ENTITLEMENTS" \
    -s "$IDENTITY" "$APP"
codesign --verify --strict --verbose=2 "$APP"

echo "==> Notarizing the app"
ZIP="$DIST/Stemchotic-app.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"
xcrun notarytool submit "$ZIP" --keychain-profile "$NOTARY_PROFILE" --wait
rm -f "$ZIP"
xcrun stapler staple "$APP"

echo "==> Building DMG"
rm -f "$DMG"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Stemchotic" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"
codesign --force --timestamp -s "$IDENTITY" "$DMG"   # sign the DMG itself too

echo "==> Notarizing the DMG"
xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$DMG"

echo ""
echo "Signed + notarized: $DMG"
spctl -a -t open --context context:primary-signature -v "$DMG" 2>&1 || true
spctl -a -v "$APP" 2>&1 || true
