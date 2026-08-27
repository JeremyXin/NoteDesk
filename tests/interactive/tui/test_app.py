from pathlib import Path

from notedesk.interactive.tui.app import NoteDeskTUI


def test_tui_summary_includes_task_progress_and_artifact_dir(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    summary = app.render_launch_summary()

    assert "NoteDesk" in summary
    assert str(tmp_path / "artifacts") in summary
