#!/usr/bin/env python3
"""Bake the release channel into launcher.py at build time.

Dev launcher builds run `python packaging/set_release_channel.py dev-latest` to
flip RELEASE_TAG from "" to "dev-latest", so the binary reads
/releases/tags/dev-latest and installs to _app_dev (coexisting with production).
Kept as a committed helper rather than an inline workflow one-liner to dodge
cross-shell quoting and YAML comment pitfalls. See .github/workflows/dev-release.yml.
"""
import re
import sys
from pathlib import Path

tag = sys.argv[1] if len(sys.argv) > 1 else "dev-latest"
path = Path("launcher.py")
src = path.read_text(encoding="utf-8")
out = re.sub(r'^RELEASE_TAG = ""', f'RELEASE_TAG = "{tag}"', src, count=1, flags=re.M)
if out == src:
    sys.exit("set_release_channel: RELEASE_TAG anchor not found in launcher.py")
path.write_text(out, encoding="utf-8")
print(f"set_release_channel: RELEASE_TAG = {tag!r}")
