from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from notedesk.agent.events import PermissionRequestEvent
from notedesk.artifacts.models import ArtifactReceipt
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


def test_tui_welcome_panel_matches_cli_agent_style(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / ".notedesk" / "artifacts",
    )

    welcome = app.render_welcome_panel()

    assert "Welcome back!" in welcome
    assert "╭─▣─╮" in welcome
    assert "NoteDesk" in welcome
    assert "Tips for getting started" in welcome
    assert "Esc+Enter" in welcome
    assert ".notedesk/artifacts" in welcome


def test_tui_status_bar_uses_short_operational_footer(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / ".notedesk" / "artifacts",
    )

    status = app.render_status_bar()

    assert "Idle" in status
    assert "Ctrl-T tasks" in status
    assert str(tmp_path) not in status
    assert "Artifacts:" not in status


def test_tui_input_area_is_compact(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    assert app.input_field.window.height.max == 4


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


def test_tui_can_submit_and_clear_input(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    submitted: list[str] = []
    app.on_submit = submitted.append
    app.input_field.text = "Summarize this"

    app.handle_submit()

    assert submitted == ["Summarize this"]
    assert app.input_field.text == ""


def test_tui_cancel_path_updates_status(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    cancelled: list[bool] = []
    app.on_cancel = lambda: cancelled.append(True)

    app.handle_cancel()

    assert cancelled == [True]
    assert "Cancelling" in app.render_status_bar()


def test_tui_key_binding_ctrl_t_toggles_drawer(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    bindings = app._build_key_bindings().bindings

    assert any(str(binding.keys[0]) == "Keys.ControlT" for binding in bindings)

    app.toggle_task_drawer()

    assert app.task_drawer_open is True


def test_tui_can_insert_multiline_input(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    app.input_field.text = "line1"

    app.handle_insert_newline()

    assert app.input_field.text == "line1\n"


def test_tui_ctrl_c_clears_input_then_sets_exit_status(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    app.input_field.text = "pending"

    first = app.handle_ctrl_c()
    second = app.handle_ctrl_c()

    assert first == "cleared_input"
    assert second == "request_exit"


def test_tui_renders_permission_and_artifact_messages(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    app.show_permission_request(
        PermissionRequestEvent(
            tool_name="Bash",
            summary="Permission required for tool action",
        )
    )
    app.show_artifact_receipt(
        ArtifactReceipt(
            path=tmp_path / "summary.md",
            bytes_written=42,
            sources=["twitter:timeline"],
        )
    )

    assert "Permission required for tool action" in app.transcript_field.text
    assert "Ctrl-Y approve · Ctrl-N deny" in app.transcript_field.text
    assert "summary.md" in app.transcript_field.text


def test_tui_ctrl_c_requests_exit_when_input_is_empty(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    with create_pipe_input() as pipe_input:
        application = app.build_application(input=pipe_input, output=DummyOutput())
        app.input_field.text = ""

        outcome = app.handle_ctrl_c()

        assert outcome == "request_exit"
        assert application is not None
