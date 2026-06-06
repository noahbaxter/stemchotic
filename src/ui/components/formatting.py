"""
Generic formatting helpers.

Trimmed from synchotic's formatting module - only the app-agnostic pieces.
"""

from ..primitives.terminal import strip_ansi


def calc_percent(current: float, total: float) -> int:
    """Percentage of current/total, clamped to 0-100."""
    if total <= 0:
        return 0
    return max(0, min(100, int(round((current / total) * 100))))


__all__ = ["strip_ansi", "calc_percent"]
