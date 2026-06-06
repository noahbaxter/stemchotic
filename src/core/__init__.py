"""Core logic: templates and the separation wrapper."""

from .templates import Template, Stage, TEMPLATES, get_template
from .separator import separate

__all__ = ["Template", "Stage", "TEMPLATES", "get_template", "separate"]
