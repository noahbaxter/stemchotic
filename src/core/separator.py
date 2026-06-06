"""
Thin wrapper over python-audio-separator.

Runs a Template (one or more model stages) against an input file. The heavy
dependency (audio_separator -> torch/onnxruntime) is imported lazily so the TUI
launches instantly without it installed.
"""

from pathlib import Path

from .templates import Template, Stage


DEFAULT_OUTPUT_DIR = "stems"


def _load_separator(model_dir: str, output_dir: str):
    """Lazily construct an audio_separator Separator. Raises a friendly error if
    the dependency is missing."""
    try:
        from audio_separator.separator import Separator
    except ImportError as e:
        raise RuntimeError(
            "audio-separator is not installed. Run: pip install -r requirements.txt"
        ) from e
    return Separator(model_file_dir=model_dir, output_dir=output_dir)


def run_stage(separator, stage: Stage, input_file: str) -> list[str]:
    """Run one model pass, return the output stem file paths."""
    separator.load_model(model_filename=stage.model)
    return separator.separate(input_file)


def separate(
    template: Template,
    input_file: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    model_dir: str = "/tmp/audio-separator-models",
    progress=None,
) -> list[str]:
    """
    Run a template against one input file.

    For a single-stage template this is one separation. For a cascade, the first
    kept stem of each stage feeds the next stage.

    Returns the list of final output stem paths.

    NOTE (skeleton): cascade stem-routing and the drumsep checkpoint are not yet
    verified end to end. Single-stage templates are the supported path for v1.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    separator = _load_separator(model_dir, output_dir)

    current_input = input_file
    outputs: list[str] = []

    for i, stage in enumerate(template.stages):
        if progress:
            progress(f"Stage {i + 1}/{len(template.stages)}: {stage.model}")
        outputs = run_stage(separator, stage, current_input)

        # Cascade: feed the first kept stem of this stage into the next one.
        if i < len(template.stages) - 1:
            current_input = _pick_cascade_input(outputs, stage)

    return outputs


def _pick_cascade_input(outputs: list[str], stage: Stage) -> str:
    """Choose which produced stem becomes the next stage's input.

    Matches the first `keep` stem name against the produced filenames. Falls back
    to the first output if no match (skeleton heuristic - tighten once drumsep is
    verified)."""
    if stage.keep:
        target = stage.keep[0].lower()
        for path in outputs:
            if target in Path(path).stem.lower():
                return path
    return outputs[0]
