from __future__ import annotations

import os
from pathlib import Path

from notedesk.artifacts.models import ArtifactReceipt


class ArtifactValidationError(ValueError):
    pass


def save_markdown_artifact(
    output_path: Path,
    markdown: str,
    sources: list[str],
) -> ArtifactReceipt:
    _validate_markdown(markdown)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(markdown)
    os.replace(temp_path, output_path)
    return ArtifactReceipt(
        path=output_path,
        bytes_written=output_path.stat().st_size,
        sources=sources,
    )


def _validate_markdown(markdown: str) -> None:
    if not markdown.strip():
        raise ArtifactValidationError("Markdown artifact must not be blank")

    markers = ("# ", "## ", "- ", "* ", "1. ", "```")
    if not any(marker in markdown for marker in markers):
        raise ArtifactValidationError("Content does not look like markdown")
