from pathlib import Path

from prompt_toolkit.application import Application

from notedesk.agent.middleware import TaskSnapshot, TaskSnapshotItem
from notedesk.interactive.tui.app import NoteDeskTUI


def test_tui_summary_includes_task_progress_and_artifact_dir(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    summary = app.render_launch_summary()

    assert "NoteDesk" in summary
    assert str(tmp_path / "artifacts") in summary


def test_tui_builds_prompt_toolkit_application(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    application = app.build_application()

    assert isinstance(application, Application)
    assert app.input_field is not None
    assert app.transcript_field is not None


def test_tui_task_drawer_can_toggle_and_render_snapshot(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    snapshot = TaskSnapshot(
        tasks=[
            TaskSnapshotItem(
                id="task-1",
                subject="Collect tweets",
                description="Fetch",
                state="pending",
                owner=None,
                metadata={},
            )
        ]
    )

    app.update_task_snapshot(snapshot)
    app.toggle_task_drawer()

    assert app.task_drawer_open is True
    assert "Collect tweets" in app.task_field.text


def test_tui_appends_transcript_and_updates_status(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    app.append_transcript("Assistant: hello")
    app.set_status("Running")

    assert "Assistant: hello" in app.transcript_field.text
    assert "Running" in app.render_status_bar()
