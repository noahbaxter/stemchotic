"""Core logic: engines, selection resolution, and the separation wrapper."""

from .engines import (
    STEM_OPTIONS,
    StemOption,
    CLI_PRESETS,
    Pass,
    resolve,
    plan_text,
)
from .separator import run

__all__ = [
    "STEM_OPTIONS",
    "StemOption",
    "CLI_PRESETS",
    "Pass",
    "resolve",
    "plan_text",
    "run",
]
