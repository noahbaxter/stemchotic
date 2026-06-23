"""
Captures audio-separator's raw tqdm stderr output and renders one clean,
labeled, in-place progress line on stdout instead. audio-separator has no
progress callback; this is the only hook.

tqdm resolves `file=None` to the `sys.stderr` *object* at construction, so we
capture by swapping that object out for a proxy. We deliberately do NOT
redirect OS fd 2 (os.dup2): on Windows that breaks Python's console stream
(_io._WindowsConsoleIO, CPython bpo-30555). WriteConsoleW on the redirected
pipe handle raises OSError [WinError 1] Incorrect function, which crashed the
first-run model download in the beta.
"""

import re
import sys

_PCT = re.compile(r"(\d{1,3})%\|")
_BYTES = re.compile(r"\d+(\.\d+)?[kMG]?iB")   # download bars show byte totals


class capture_tqdm:
    """Context manager: while active, sys.stderr is replaced by this proxy,
    which swallows raw tqdm writes and re-renders the progress as
    '\r  <label>  NN%' on stdout. Download bars (byte totals) are labeled
    'Downloading models' instead of the step label."""

    def __init__(self, label: str):
        self.label = label
        self._saved = None
        self._buf = ""
        self._rendered = False

    def __enter__(self):
        self._saved = sys.stderr
        sys.stderr = self
        return self

    def __exit__(self, *exc):
        sys.stderr = self._saved
        if self._rendered:
            sys.stdout.write("\r" + " " * 70 + "\r")
            sys.stdout.flush()
        return False

    # --- minimal file-like surface tqdm writes to (no fileno: tqdm guards it) ---

    def write(self, s: str) -> int:
        self._buf += s
        frags = re.split(r"[\r\n]", self._buf)
        self._buf = frags.pop()            # keep the incomplete tail
        for frag in frags:
            self._render(frag)
        return len(s)

    def flush(self) -> None:
        # tqdm writes a whole bar then flushes with no trailing \r/\n, so render
        # the buffered tail here to keep the bar advancing live, then drop it.
        if self._buf:
            self._render(self._buf)
            self._buf = ""

    def isatty(self) -> bool:
        return False

    def __getattr__(self, name):
        # Delegate anything we don't override (fileno, buffer, encoding, ...) to
        # the real stderr, so libraries that introspect the stream during a run
        # still see a normal one. Guarded so attribute access during __init__
        # (before _saved is set) doesn't recurse.
        saved = self.__dict__.get("_saved")
        if saved is None:
            raise AttributeError(name)
        return getattr(saved, name)

    def _render(self, frag: str) -> None:
        pcts = _PCT.findall(frag)
        if not pcts:
            return
        pct = min(int(pcts[-1]), 100)
        label = "Downloading models" if _BYTES.search(frag) else self.label
        sys.stdout.write(f"\r  {label}  {pct:3d}%   ")
        sys.stdout.flush()
        self._rendered = True
