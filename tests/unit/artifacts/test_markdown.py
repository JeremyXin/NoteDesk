from pathlib import Path

import pytest

from notedesk.artifacts.markdown import ArtifactValidationError, save_markdown_artifact


def test_save_markdown_artifact_writes_atomically_on_valid_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "summary.md"

    receipt = save_markdown_artifact(
        output_path=output_path,
        markdown="# Summary\n\n- point\n",
        sources=["twitter:timeline"],
    )

    assert output_path.exists()
    assert output_path.read_text() == "# Summary\n\n- point\n"
    assert receipt.path == output_path
    assert receipt.bytes_written > 0
    assert receipt.sources == ["twitter:timeline"]


def test_save_markdown_artifact_rejects_blank_content_without_creating_file(tmp_path: Path) -> None:
    output_path = tmp_path / "summary.md"

    with pytest.raises(ArtifactValidationError):
        save_markdown_artifact(
            output_path=output_path,
            markdown="   \n",
            sources=[],
        )

    assert not output_path.exists()


def test_save_markdown_artifact_rejects_non_markdown_like_content(tmp_path: Path) -> None:
    output_path = tmp_path / "summary.md"

    with pytest.raises(ArtifactValidationError):
        save_markdown_artifact(
            output_path=output_path,
            markdown="plain text without markdown markers",
            sources=[],
        )
