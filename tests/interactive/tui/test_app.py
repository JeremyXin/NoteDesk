import asyncio
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import set_app
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.input.vt100_parser import Vt100Parser
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.keys import Keys
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType, Point
from prompt_toolkit.layout import VerticalAlign, WindowAlign
from prompt_toolkit.layout.containers import HSplit, VSplit
from prompt_toolkit.layout.scrollable_pane import ScrollablePane
from prompt_toolkit.output import DummyOutput

from notedesk.agent.events import PermissionRequestEvent
from notedesk.artifacts.models import ArtifactReceipt
from notedesk.agent.middleware import TaskSnapshot, TaskSnapshotItem
from notedesk.interactive.tui.app import COMMAND_C_KEY, SHIFT_PRINTABLE_KEY, NoteDeskTUI


def _parsed_keys(sequence: str) -> list[KeyPress]:
    parsed: list[KeyPress] = []
    parser = Vt100Parser(parsed.append)
    parser.feed(sequence)
    return parsed


def test_tui_parses_kitty_command_c_as_copy_key(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.register_kitty_keyboard_sequences()

    parsed = _parsed_keys("\x1b[99;9u")

    assert [key.key for key in parsed] == [COMMAND_C_KEY]


def test_tui_parses_kitty_command_v_as_ctrl_v(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.register_kitty_keyboard_sequences()

    parsed = _parsed_keys("\x1b[118;9u")

    assert [key.key for key in parsed] == [Keys.ControlV]


def test_tui_parses_kitty_ctrl_shift_c_as_ctrl_c(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.register_kitty_keyboard_sequences()

    parsed = _parsed_keys("\x1b[99;6u")

    assert [key.key for key in parsed] == [Keys.ControlC]


def test_tui_parses_xterm_command_c_as_copy_key(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.register_kitty_keyboard_sequences()

    parsed = _parsed_keys("\x1b[27;9;99~")

    assert [key.key for key in parsed] == [COMMAND_C_KEY]


def test_tui_parses_xterm_shift_letter_as_plain_character(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.register_kitty_keyboard_sequences()

    parsed = _parsed_keys("\x1b[27;2;66~")

    assert [key.key for key in parsed] == [SHIFT_PRINTABLE_KEY]


def test_tui_parses_xterm_shift_delete_as_backspace(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.register_kitty_keyboard_sequences()

    parsed = _parsed_keys("\x1b[27;2;127~")

    assert [key.key for key in parsed] == [Keys.Backspace]


def test_tui_parses_xterm_command_v_as_ctrl_v(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.register_kitty_keyboard_sequences()

    parsed = _parsed_keys("\x1b[27;9;118~")

    assert [key.key for key in parsed] == [Keys.ControlV]


def test_tui_enables_kitty_keyboard_on_supported_terminal(
    tmp_path: Path, monkeypatch
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    output = DummyOutput()
    writes: list[str] = []
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    output.write_raw = writes.append

    assert app.enable_kitty_keyboard(output) is True
    assert writes == ["\x1b[>1u\x1b[>4;2m"]


def test_tui_skips_kitty_keyboard_on_unknown_terminal(
    tmp_path: Path, monkeypatch
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    output = DummyOutput()
    writes: list[str] = []
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    output.write_raw = writes.append

    assert app.enable_kitty_keyboard(output) is False
    assert writes == []


def test_tui_disables_kitty_keyboard_after_run(
    tmp_path: Path, monkeypatch
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    output = DummyOutput()
    writes: list[str] = []
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    output.write_raw = writes.append

    app.enable_kitty_keyboard(output)
    app.disable_kitty_keyboard(output)

    assert writes == ["\x1b[>1u\x1b[>4;2m", "\x1b[>4m\x1b[<u"]


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
    assert application.full_screen is True
    assert application.erase_when_done is True
    assert application.layout.container.align == VerticalAlign.JUSTIFY
    assert app.transcript_field.window.height.weight == 1
    bottom_dock = application.layout.container.children[-1]
    assert isinstance(bottom_dock, HSplit)
    assert bottom_dock.height.preferred == 3
    assert app.input_field is not None
    assert app.transcript_field is not None


def test_tui_root_layout_anchors_input_dock_to_bottom(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    application = app.build_application()

    assert application.layout.container.align == VerticalAlign.JUSTIFY


def test_tui_welcome_area_uses_brand_and_runtime_columns(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / ".notedesk" / "artifacts",
    )

    application = app.build_application()
    root = application.layout.container

    assert isinstance(root, HSplit)
    scroll_pane = root.children[0]
    assert isinstance(scroll_pane, ScrollablePane)
    welcome = scroll_pane.content.children[0]
    frame_body = welcome.children[1]
    welcome_layout = frame_body.children[1].get_container()
    assert isinstance(welcome_layout, VSplit)
    assert isinstance(welcome_layout.children[0], HSplit)
    assert welcome_layout.children[2].width.preferred == 2
    assert isinstance(welcome_layout.children[3], HSplit)
    brand_column = welcome_layout.children[0]
    runtime_column = welcome_layout.children[3]
    assert len(runtime_column.children) == 8
    assert brand_column.children[0].align == WindowAlign.CENTER
    assert runtime_column.align == VerticalAlign.CENTER
    assert runtime_column.children[0].align == WindowAlign.LEFT
    assert "Welcome back!" in app.render_welcome_brand()
    assert "workspace:" in app.render_welcome_runtime()
    assert ".notedesk/artifacts" in app.render_welcome_runtime()
    assert "Tips for getting started" in app.render_welcome_tips_header()
    assert "permissions: confirm edits" in app.render_welcome_permissions()


def test_tui_places_welcome_panel_inside_transcript_scroll_pane(
    tmp_path: Path,
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    application = app.build_application()

    root = application.layout.container
    scroll_pane = root.children[0]

    assert isinstance(scroll_pane, ScrollablePane)
    assert scroll_pane.content.children[0] is not None
    assert scroll_pane.content.children[1] is app.transcript_field.window


def test_tui_welcome_panel_matches_cli_agent_style(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / ".notedesk" / "artifacts",
    )

    welcome = app.render_welcome_panel()

    assert "Welcome back!" in welcome
    assert "+-------+" in welcome
    assert "NOTE" in welcome
    assert "DESK" in welcome
    assert "| N/D |" not in welcome
    assert "NoteDesk" in welcome
    assert "Enter send" in welcome
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

    assert app.input_field.window.height.preferred == 1
    assert app.input_field.window.height.max == 4
    assert app.input_field.window.dont_extend_height() is True


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


def test_tui_keeps_transcript_cursor_at_end_after_append(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    app.append_transcript("> first")
    app.append_transcript_delta("first reply")
    app.append_transcript("> second")

    assert app.transcript_field.buffer.cursor_position == len(app.transcript_field.text)


def test_tui_formats_user_turns_and_keeps_transcript_scrollable(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    app.input_field.text = "hello"
    app.handle_submit()

    assert app.transcript_field.text == "You  > hello"
    assert not app.transcript_field.window.right_margins


def test_tui_visually_distinguishes_user_and_assistant_turns(tmp_path: Path) -> None:
    async def render_transcript() -> tuple[list, list]:
        app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
        with create_pipe_input() as pipe_input:
            application = app.build_application(
                input=pipe_input,
                output=DummyOutput(),
            )
            app.append_transcript("You  > hello")
            app.append_transcript_delta("answer")
            with set_app(application):
                content = app.transcript_field.control.create_content(80, 10)
                return content.get_line(0), content.get_line(1)

    user_line, assistant_line = asyncio.run(render_transcript())

    assert any(
        "transcript.user" in style and "You  > hello" in text
        for style, text, *_ in user_line
    )
    assert assistant_line[0][0].find("transcript.assistant-label") >= 0
    assert assistant_line[0][1] == "NoteDesk > "


def test_tui_uses_mouse_scrolling_without_visible_scrollbar(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    application = app.build_application()

    assert not app.transcript_field.window.right_margins
    assert application.mouse_support()


def test_tui_transcript_can_receive_focus_for_keyboard_selection(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    assert app.transcript_field.control.is_focusable()
    assert app.transcript_field.control.focus_on_click()


def test_tui_mouse_drag_focuses_transcript_from_input_focus(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    application = app.build_application()
    app.append_transcript("copy this text")

    with set_app(application):
        control = app.transcript_field.control
        control.mouse_handler(
            MouseEvent(Point(x=0, y=0), MouseEventType.MOUSE_DOWN, MouseButton.LEFT, frozenset())
        )
        control.mouse_handler(
            MouseEvent(
                Point(x=9, y=0),
                MouseEventType.MOUSE_MOVE,
                MouseButton.LEFT,
                frozenset(),
            )
        )

    assert application.layout.current_control is control


def test_tui_mouse_click_returns_focus_to_prompt(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    application = app.build_application()

    with set_app(application):
        control = app.transcript_field.control
        control.mouse_handler(
            MouseEvent(
                Point(x=0, y=0),
                MouseEventType.MOUSE_DOWN,
                MouseButton.LEFT,
                frozenset(),
            )
        )
        control.mouse_handler(
            MouseEvent(
                Point(x=0, y=0),
                MouseEventType.MOUSE_UP,
                MouseButton.LEFT,
                frozenset(),
            )
        )

    assert application.layout.current_control is app.input_field.control


def test_tui_copies_transcript_selection(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    app.append_transcript("copy this text")
    app.transcript_field.buffer.cursor_position = 0
    app.transcript_field.buffer.start_selection()
    app.transcript_field.buffer.cursor_position = len("copy this")

    copied = app.copy_transcript_selection()

    assert copied is not None
    assert copied.text == "copy this"
    assert app.transcript_field.buffer.selection_state is None


def test_tui_extends_transcript_selection_with_directional_movement(
    tmp_path: Path,
) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    app.append_transcript("select this")
    app.transcript_field.buffer.cursor_position = 0

    app.extend_transcript_selection("right")
    app.extend_transcript_selection("right")
    copied = app.copy_transcript_selection()

    assert copied is not None
    assert copied.text == "se"


def test_tui_copies_selection_to_system_clipboard(tmp_path: Path, monkeypatch) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    calls: list[tuple[list[str], str]] = []

    monkeypatch.setattr(
        "notedesk.interactive.tui.app.shutil.which",
        lambda command: "/usr/bin/pbcopy" if command == "pbcopy" else None,
    )
    monkeypatch.setattr(
        "notedesk.interactive.tui.app.subprocess.run",
        lambda command, *, input, text, check: calls.append((command, input)),
    )

    assert app.copy_to_system_clipboard("copy this") is True
    assert calls == [(["pbcopy"], "copy this")]


def test_tui_reads_from_macos_system_clipboard(
    tmp_path: Path, monkeypatch
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    calls: list[list[str]] = []

    monkeypatch.setattr("notedesk.interactive.tui.app.sys.platform", "darwin")
    monkeypatch.setattr(
        "notedesk.interactive.tui.app.shutil.which",
        lambda command: "/usr/bin/pbpaste" if command == "pbpaste" else None,
    )
    monkeypatch.setattr(
        "notedesk.interactive.tui.app.subprocess.run",
        lambda command, *, capture_output, text, check: calls.append(command)
        or type("Result", (), {"stdout": "pasted text\n"})(),
    )

    assert app.read_from_system_clipboard() == "pasted text\n"
    assert calls == [["pbpaste"]]


def test_tui_reads_from_linux_system_clipboard_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    calls: list[list[str]] = []

    monkeypatch.setattr("notedesk.interactive.tui.app.sys.platform", "linux")
    monkeypatch.setattr(
        "notedesk.interactive.tui.app.shutil.which",
        lambda command: "/usr/bin/xclip" if command == "xclip" else None,
    )
    monkeypatch.setattr(
        "notedesk.interactive.tui.app.subprocess.run",
        lambda command, *, capture_output, text, check: calls.append(command)
        or type("Result", (), {"stdout": "clipboard content"})(),
    )

    assert app.read_from_system_clipboard() == "clipboard content"
    assert calls == [["xclip", "-selection", "clipboard", "-o"]]


def test_tui_returns_none_when_system_clipboard_is_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")

    monkeypatch.setattr("notedesk.interactive.tui.app.sys.platform", "linux")
    monkeypatch.setattr("notedesk.interactive.tui.app.shutil.which", lambda _: None)

    assert app.read_from_system_clipboard() is None


def test_tui_pastes_system_clipboard_into_prompt(tmp_path: Path, monkeypatch) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.input_field.text = "before: "
    app.input_field.buffer.cursor_position = len(app.input_field.text)
    monkeypatch.setattr(
        app,
        "read_from_system_clipboard",
        lambda: "line one\r\nline two",
    )

    assert app.paste_from_system_clipboard() is True
    assert app.input_field.text == "before: line one\nline two"
    assert app.input_field.buffer.cursor_position == len(app.input_field.text)


def test_tui_registers_ctrl_v_paste_binding(tmp_path: Path) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")

    bindings = app._build_key_bindings().bindings

    assert any(str(binding.keys[0]) == "Keys.ControlV" for binding in bindings)


def test_tui_sigint_copies_transcript_selection(tmp_path: Path) -> None:
    async def scenario() -> tuple[list[str], str, bool]:
        with create_pipe_input() as pipe_input:
            app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
            application = app.build_application(
                input=pipe_input,
                output=DummyOutput(),
            )
            app.append_transcript("copy this")
            application.layout.current_control = app.transcript_field.control
            app.transcript_field.buffer.cursor_position = 0
            app.transcript_field.buffer.start_selection()
            app.transcript_field.buffer.cursor_position = len("copy this")
            copied: list[str] = []
            app.copy_to_system_clipboard = lambda text: copied.append(text) or True

            run_task = asyncio.create_task(application.run_async())
            await asyncio.sleep(0.01)
            application.key_processor.send_sigint()
            await asyncio.sleep(0.01)
            application.exit()
            await run_task
            return (
                copied,
                app.status_text,
                application.layout.current_control is app.input_field.control,
            )

    copied, status, input_focused = asyncio.run(scenario())

    assert copied == ["copy this"]
    assert status == "Copied 9 chars"
    assert input_focused is True


def test_tui_sigint_copies_selection_while_prompt_has_focus(tmp_path: Path) -> None:
    async def scenario() -> tuple[list[str], str, str]:
        with create_pipe_input() as pipe_input:
            app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
            application = app.build_application(
                input=pipe_input,
                output=DummyOutput(),
            )
            app.append_transcript("copy this")
            app.transcript_field.buffer.cursor_position = 0
            app.transcript_field.buffer.start_selection()
            app.transcript_field.buffer.cursor_position = len("copy this")
            app.input_field.text = "draft"
            copied: list[str] = []
            app.copy_to_system_clipboard = lambda text: copied.append(text) or True

            run_task = asyncio.create_task(application.run_async())
            await asyncio.sleep(0.01)
            application.key_processor.send_sigint()
            await asyncio.sleep(0.01)
            application.exit()
            await run_task
            return copied, app.status_text, app.input_field.text

    copied, status, prompt_text = asyncio.run(scenario())

    assert copied == ["copy this"]
    assert status == "Copied 9 chars"
    assert prompt_text == "draft"


def test_tui_command_c_does_not_exit_without_transcript_selection(
    tmp_path: Path,
) -> None:
    async def scenario() -> bool:
        with create_pipe_input() as pipe_input:
            app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
            application = app.build_application(
                input=pipe_input,
                output=DummyOutput(),
            )

            run_task = asyncio.create_task(application.run_async())
            await asyncio.sleep(0.01)
            application.key_processor.feed(KeyPress(COMMAND_C_KEY))
            application.key_processor.process_keys()
            await asyncio.sleep(0.01)
            still_running = not run_task.done()
            application.exit()
            await run_task
            return still_running

    assert asyncio.run(scenario()) is True


def test_tui_command_c_does_not_exit_after_copying_selection(
    tmp_path: Path,
) -> None:
    async def scenario() -> tuple[list[str], bool]:
        with create_pipe_input() as pipe_input:
            app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
            application = app.build_application(
                input=pipe_input,
                output=DummyOutput(),
            )
            app.append_transcript("copy this")
            app.transcript_field.buffer.cursor_position = 0
            app.transcript_field.buffer.start_selection()
            app.transcript_field.buffer.cursor_position = len("copy this")
            copied: list[str] = []
            app.copy_to_system_clipboard = lambda text: copied.append(text) or True

            run_task = asyncio.create_task(application.run_async())
            await asyncio.sleep(0.01)
            application.key_processor.feed(KeyPress(COMMAND_C_KEY))
            application.key_processor.process_keys()
            await asyncio.sleep(0.01)
            application.key_processor.feed(KeyPress(COMMAND_C_KEY))
            application.key_processor.process_keys()
            await asyncio.sleep(0.01)
            still_running = not run_task.done()
            application.exit()
            await run_task
            return copied, still_running

    copied, still_running = asyncio.run(scenario())

    assert copied == ["copy this"]
    assert still_running is True


def test_tui_keeps_welcome_panel_in_scroll_history_after_conversation_starts(
    tmp_path: Path,
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    application = app.build_application()
    scroll_pane = application.layout.container.children[0]
    assert isinstance(scroll_pane, ScrollablePane)
    welcome = scroll_pane.content.children[0]

    app.append_transcript("You  > hello")

    assert scroll_pane.content.children[0] is welcome


def test_tui_scroll_transcript_moves_cursor_through_history(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    app.append_transcript("\n".join(f"line {index}" for index in range(20)))
    end_position = app.transcript_field.buffer.cursor_position

    app.scroll_transcript(-3)

    assert app.transcript_field.buffer.cursor_position < end_position


def test_tui_preserves_transcript_view_when_new_text_arrives_after_scroll(
    tmp_path: Path,
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.append_transcript("\n".join(f"line {index}" for index in range(20)))

    app.scroll_transcript(-3)
    scrolled_position = app.transcript_field.window.vertical_scroll
    app.append_transcript("new line")

    assert app.transcript_field.window.vertical_scroll == scrolled_position


def test_tui_preserves_transcript_selection_when_new_text_arrives(
    tmp_path: Path,
) -> None:
    app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    app.append_transcript("copy this text")
    app.transcript_field.buffer.cursor_position = 0
    app.transcript_field.buffer.start_selection()
    app.transcript_field.buffer.cursor_position = len("copy this")

    app.append_transcript("new line")

    copied = app.copy_transcript_selection()
    assert copied is not None
    assert copied.text == "copy this"


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


def test_tui_input_arrows_recall_submitted_history(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    app.input_field.text = "first prompt"
    app.handle_submit()
    app.input_field.text = "second prompt"
    app.handle_submit()

    app.navigate_input_history(-1)
    assert app.input_field.text == "second prompt"
    app.navigate_input_history(-1)
    assert app.input_field.text == "first prompt"
    app.navigate_input_history(1)
    assert app.input_field.text == "second prompt"


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
    assert "summary.md" not in app.transcript_field.text
    assert app.status_text == "Artifact saved"


def test_tui_ctrl_c_requests_exit_when_input_is_empty(tmp_path: Path) -> None:
    app = NoteDeskTUI(
        workspace=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    with create_pipe_input() as pipe_input:
        application = app.build_application(input=pipe_input, output=DummyOutput())
        app.input_field.text = ""

        first = app.handle_ctrl_c()
        second = app.handle_ctrl_c()

        assert first == "awaiting_exit"
        assert second == "request_exit"
        assert application is not None


def test_tui_ctrl_c_requires_two_presses_to_exit(tmp_path: Path) -> None:
    async def scenario() -> tuple[bool, bool]:
        with create_pipe_input() as pipe_input:
            app = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
            application = app.build_application(
                input=pipe_input,
                output=DummyOutput(),
            )
            run_task = asyncio.create_task(application.run_async())
            await asyncio.sleep(0.01)

            application.key_processor.send_sigint()
            await asyncio.sleep(0.01)
            running_after_first = not run_task.done()

            application.key_processor.send_sigint()
            await asyncio.sleep(0.01)
            exited_after_second = run_task.done()
            await run_task
            return running_after_first, exited_after_second

    running_after_first, exited_after_second = asyncio.run(scenario())

    assert running_after_first is True
    assert exited_after_second is True
