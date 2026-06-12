"""
Captures audio-separator's raw tqdm stderr output and renders one clean,
labeled, in-place progress line on stdout instead. audio-separator has no
progress callback; this is the only hook.
"""

import os
import re
import sys
import threading

_PCT = re.compile(rb"(\d{1,3})%\|")
_BYTES = re.compile(rb"\d+(\.\d+)?[kMG]?iB")   # download bars show byte totals


class capture_tqdm:
    """Context manager: while active, stderr is swallowed and tqdm progress
    is re-rendered as '\r  <label>  NN%'. Download bars (byte totals) are
    labeled 'Downloading models' instead of the step label."""

    def __init__(self, label: str):
        self.label = label
        self._saved = None
        self._read_fd = None
        self._write_fd = None
        self._thread = None
        self._rendered = False

    def __enter__(self):
        self._saved = os.dup(2)
        self._read_fd, self._write_fd = os.pipe()
        os.dup2(self._write_fd, 2)
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        try:
            os.dup2(self._saved, 2)            # restore real stderr first
        finally:
            os.close(self._saved)
            os.close(self._write_fd)           # last write end -> reader sees EOF
            self._thread.join(timeout=5)
            os.close(self._read_fd)
            if self._rendered:
                sys.stdout.write("\r" + " " * 70 + "\r")
                sys.stdout.flush()
        return False

    def _reader(self):
        buf = b""
        while True:
            try:
                chunk = os.read(self._read_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            frags = re.split(rb"[\r\n]", buf)
            buf = frags.pop()                  # keep the incomplete tail
            for frag in frags:
                self._render(frag)
        if buf:
            self._render(buf)

    def _render(self, frag: bytes):
        pcts = _PCT.findall(frag)
        if not pcts:
            return
        pct = min(int(pcts[-1]), 100)
        label = "Downloading models" if _BYTES.search(frag) else self.label
        sys.stdout.write(f"\r  {label}  {pct:3d}%   ")
        sys.stdout.flush()
        self._rendered = True
