from __future__ import annotations

import shutil
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, VerticalAlign, WindowAlign
from prompt_toolkit.layout.containers import ConditionalContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.scrollable_pane import ScrollablePane
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.filters import Condition
from prompt_toolkit.filters import has_focus
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import vt100_parser
from prompt_toolkit.styles import Style
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.processors import Processor, Transformation, TransformationInput
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import Frame, TextArea

from notedesk.agent.events import PermissionRequestEvent
from notedesk.agent.middleware import TaskSnapshot
from notedesk.artifacts.models import ArtifactReceipt
from notedesk.interactive.tui.tasks import TaskViewModel


# prompt_toolkit only accepts one-character custom keys. Keep Cmd+C separate
# from Ctrl+C so clipboard shortcuts cannot trigger the exit fallback.
COMMAND_C_KEY = "\ue000"
SHIFT_PRINTABLE_KEY = "\ue001"


class TranscriptTurnProcessor(Processor):
    """Apply distinct visual treatments to user and assistant turns."""

    USER_PREFIX = "You  > "
    ASSISTANT_PREFIX = "NoteDesk > "

    def apply_transformation(
        self,
        transformation_input: TransformationInput,
    ) -> Transformation:
        # Conversation spacing intentionally inserts blank rows between turns.
        # They are separators, not part of the user's highlighted row.
        if not transformation_input.document.lines[transformation_input.lineno].strip():
            return Transformation(transformation_input.fragments)
        mode = self._message_mode(
            transformation_input.document.lines,
            transformation_input.lineno,
        )
        if mode is None:
            return Transformation(transformation_input.fragments)

        fragments = self._style_fragments(
            transformation_input.fragments,
            mode,
            transformation_input.width,
        )
        return Transformation(fragments)

    def _message_mode(self, lines: list[str], lineno: int) -> str | None:
        mode: str | None = None
        for line in lines[: lineno + 1]:
            if line.startswith(self.USER_PREFIX):
                mode = "user"
            elif line.startswith(self.ASSISTANT_PREFIX):
                mode = "assistant"
        return mode

    def _style_fragments(self, fragments, mode: str, width: int):
        styled = []
        for fragment in fragments:
            style, text, *rest = fragment
            if mode == "user":
                style = f"{style} class:transcript.user".strip()
            elif text.startswith(self.ASSISTANT_PREFIX):
                prefix = text[: len(self.ASSISTANT_PREFIX)]
                remainder = text[len(self.ASSISTANT_PREFIX) :]
                styled.append(
                    (f"{style} class:transcript.assistant-label".strip(), prefix, *rest)
                )
                if remainder:
                    styled.append((style, remainder, *rest))
                continue
            styled.append((style, text, *rest))
        if mode == "user":
            line_width = sum(get_cwidth(text) for _, text, *_ in styled)
            padding = max(0, width - line_width)
            if padding:
                styled.append(("class:transcript.user", " " * padding))
        return styled


class TranscriptWindow(Window):
    """Reserve the wrapped tail rows omitted by ScrollablePane's size probe."""

    _WRAPPED_TAIL_GUARD_ROWS = 2

    def preferred_height(self, width: int, max_available_height: int) -> Dimension:
        dimension = super().preferred_height(width, max_available_height)
        return Dimension(
            min=dimension.min,
            max=dimension.max,
            preferred=min(
                dimension.max,
                dimension.preferred + self._WRAPPED_TAIL_GUARD_ROWS,
            ),
            weight=dimension.weight,
        )


class NoteDeskTUI:
    def __init__(self, workspace: Path, artifact_root: Path) -> None:
        self.workspace = workspace
        self.artifact_root = artifact_root
        self.task_drawer_open = False
        self.status_text = "Idle"
        self._transcript_line_boundary = False
        self._transcript_turn_boundary = False
        self._transcript_follow_bottom = True
        self._kitty_keyboard_enabled = False
        self._ctrl_c_exit_pending = False
        self._transcript_scroll_pane: ScrollablePane | None = None
        self.register_kitty_keyboard_sequences()
        self.on_submit: Callable[[str], None] = lambda text: None
        self.on_cancel: Callable[[], None] = lambda: None
        self.on_approve_permission: Callable[[], None] = lambda: None
        self.on_deny_permission: Callable[[], None] = lambda: None
        self.pending_permission: PermissionRequestEvent | None = None
        self._permission_choice = 0
        self.input_history = InMemoryHistory()
        self._input_history_index: int | None = None

        self.transcript_field = TextArea(
            text="",
            read_only=True,
            scrollbar=False,
            focusable=True,
            focus_on_click=True,
            height=Dimension(weight=1),
            input_processors=[TranscriptTurnProcessor()],
        )
        self.transcript_field.window = TranscriptWindow(
            content=self.transcript_field.control,
            height=Dimension(weight=1),
            style="class:text-area ",
            wrap_lines=True,
        )
        self.input_field = TextArea(
            text="",
            multiline=True,
            history=self.input_history,
            prompt="> ",
            height=Dimension(min=1, max=4, preferred=1),
            dont_extend_height=True,
        )
        self.input_field.buffer.read_only = Condition(
            lambda: self.pending_permission is not None
        )
        self.task_field = TextArea(
            text="No active tasks.",
            read_only=True,
            focusable=False,
        )
        self._enable_transcript_mouse_selection()

    def _enable_transcript_mouse_selection(self) -> None:
        """Focus the transcript before prompt_toolkit handles a drag start."""
        control = self.transcript_field.control
        original_mouse_handler = control.mouse_handler

        def mouse_handler(mouse_event: MouseEvent):
            if mouse_event.event_type == MouseEventType.SCROLL_UP:
                self.scroll_transcript(-3)
                get_app().invalidate()
                return None
            if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
                self.scroll_transcript(3)
                get_app().invalidate()
                return None
            if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
                get_app().layout.current_control = control
            result = original_mouse_handler(mouse_event)
            if (
                mouse_event.event_type == MouseEventType.MOUSE_UP
                and control.buffer.selection_state is None
            ):
                get_app().layout.focus(self.input_field)
            return result

        control.mouse_handler = mouse_handler

    def register_kitty_keyboard_sequences(self) -> None:
        """Map Kitty super-key sequences to prompt_toolkit key events.

        Terminals that enable the Kitty keyboard protocol encode Cmd/Super
        modifiers as CSI-u sequences. prompt_toolkit does not currently map
        these sequences, so register only the clipboard shortcuts NoteDesk
        handles. Legacy terminals continue to use their native Ctrl bindings.
        """
        shift_sequences = {
            f"\x1b[27;2;{code}~": SHIFT_PRINTABLE_KEY
            for code in range(ord(" "), ord("~") + 1)
        }
        vt100_parser.ANSI_SEQUENCES.update(
            {
                **shift_sequences,
                "\x1b[27;2;127~": Keys.Backspace,
                "\x1b[99;6u": Keys.ControlC,
                "\x1b[99;9u": COMMAND_C_KEY,
                "\x1b[118;9u": Keys.ControlV,
                "\x1b[27;6;99~": Keys.ControlC,
                "\x1b[27;9;99~": COMMAND_C_KEY,
                "\x1b[27;9;118~": Keys.ControlV,
            }
        )
        vt100_parser._IS_PREFIX_OF_LONGER_MATCH_CACHE.clear()

    def _supports_extended_keyboard(self) -> bool:
        terminal = os.environ.get("TERM", "")
        terminal_program = os.environ.get("TERM_PROGRAM", "")
        return (
            terminal_program in {"iTerm.app", "WezTerm", "ghostty"}
            or "kitty" in terminal
            or bool(os.environ.get("TMUX"))
            or bool(os.environ.get("WT_SESSION"))
        )

    def enable_kitty_keyboard(self, output=None) -> bool:
        if not self._supports_extended_keyboard():
            return False
        if output is None:
            output = get_app().output
        output.write_raw("\x1b[>1u\x1b[>4;2m")
        output.flush()
        self._kitty_keyboard_enabled = True
        return True

    def disable_kitty_keyboard(self, output=None) -> None:
        if not self._kitty_keyboard_enabled:
            return
        if output is None:
            output = get_app().output
        output.write_raw("\x1b[>4m\x1b[<u")
        output.flush()
        self._kitty_keyboard_enabled = False

    def render_launch_summary(self) -> str:
        return (
            "Launching NoteDesk TUI\n"
            f"Workspace: {self.workspace}\n"
            f"Artifacts: {self.artifact_root}"
        )

    def build_application(self, input=None, output=None) -> Application:
        task_drawer = ConditionalContainer(
            content=HSplit(
                [
                    Window(char="-", height=1),
                    Window(
                        content=FormattedTextControl(self.render_task_header),
                        height=1,
                    ),
                    self.task_field,
                ]
            ),
            filter=Condition(lambda: self.task_drawer_open),
        )
        welcome_panel_content = Frame(
            body=VSplit(
                [
                    HSplit(
                        [
                            self._welcome_window(
                                self.render_brand_welcome,
                                align=WindowAlign.CENTER,
                                style="class:welcome.heading",
                            ),
                            Window(height=1),
                            self._welcome_window(
                                self.render_logo_top,
                                align=WindowAlign.CENTER,
                                style="class:welcome.logo",
                            ),
                            self._welcome_window(
                                self.render_logo_note,
                                align=WindowAlign.CENTER,
                                style="class:welcome.logo",
                            ),
                            self._welcome_window(
                                self.render_logo_desk,
                                align=WindowAlign.CENTER,
                                style="class:welcome.logo",
                            ),
                            self._welcome_window(
                                self.render_logo_bottom,
                                align=WindowAlign.CENTER,
                                style="class:welcome.logo",
                            ),
                            Window(height=1),
                            self._welcome_window(
                                self.render_brand_model,
                                align=WindowAlign.CENTER,
                                style="class:welcome.meta",
                            ),
                            self._welcome_window(
                                self.render_brand_workspace,
                                align=WindowAlign.CENTER,
                                style="class:welcome.meta",
                            ),
                        ],
                        align=VerticalAlign.CENTER,
                        width=Dimension(weight=3),
                    ),
                    Window(char="│", width=1),
                    Window(
                        char=" ",
                        width=Dimension(min=2, max=2, preferred=2),
                    ),
                    HSplit(
                        [
                            self._welcome_window(
                                self.render_welcome_tips_header,
                                style="class:welcome.heading",
                            ),
                            self._welcome_window(self.render_welcome_tips_body),
                            Window(char="─", height=1),
                            self._welcome_window(
                                self.render_welcome_session_header,
                                style="class:welcome.heading",
                            ),
                            self._welcome_window(
                                self.render_welcome_model,
                                style="class:welcome.value",
                            ),
                            self._welcome_window(self.render_welcome_workspace),
                            self._welcome_window(self.render_welcome_artifacts),
                            self._welcome_window(
                                self.render_welcome_permissions,
                                style="class:welcome.notice",
                            ),
                        ],
                        align=VerticalAlign.CENTER,
                        width=Dimension(weight=5),
                    ),
                ]
            ),
            title="NoteDesk",
            height=Dimension(min=11, max=11, preferred=11),
        )
        self._permission_divider = Window(
            char="─", height=1, style="class:permission.divider"
        )
        permission_prompt = ConditionalContainer(
            content=HSplit(
                [
                    self._permission_divider,
                    Window(
                        content=FormattedTextControl(self.render_permission_prompt),
                        wrap_lines=True,
                    ),
                ]
            ),
            filter=Condition(lambda: self.pending_permission is not None),
        )
        main_content = HSplit(
            [
                welcome_panel_content,
                self.transcript_field,
                task_drawer,
                permission_prompt,
            ],
            align=VerticalAlign.TOP,
        )
        self._transcript_scroll_pane = ScrollablePane(
            content=main_content,
            keep_cursor_visible=False,
            keep_focused_window_visible=False,
            show_scrollbar=False,
            display_arrows=False,
            height=Dimension(weight=1),
        )
        bottom_dock = HSplit(
            [
                Window(char="-", height=1),
                self.input_field,
                Window(char="-", height=1),
                Window(
                    content=FormattedTextControl(self.render_status_bar),
                    height=1,
                    wrap_lines=False,
                ),
            ],
            height=Dimension(min=3, max=6, preferred=3),
            align=VerticalAlign.TOP,
        )
        root = HSplit(
            [self._transcript_scroll_pane, bottom_dock],
            align=VerticalAlign.JUSTIFY,
        )
        return Application(
            layout=Layout(root, focused_element=self.input_field),
            key_bindings=self._build_key_bindings(),
            full_screen=True,
            erase_when_done=True,
            mouse_support=True,
            style=Style.from_dict(
                {
                    "welcome.heading": "bold",
                    "welcome.logo": "bold",
                    "welcome.meta": "",
                    "welcome.value": "bold",
                    "welcome.notice": "",
                    "transcript.user": "bg:#f1f3f5 #111111",
                    "transcript.assistant-label": "bold #808080",
                    "permission.divider": "#4c6fd8",
                    "permission.title": "bold #6d8cff",
                    "permission.detail": "#808080",
                    "permission.selected": "bold #80a0ff",
                }
            ),
            input=input,
            output=output,
        )

    def toggle_task_drawer(self) -> None:
        self.task_drawer_open = not self.task_drawer_open

    def _transcript_viewport_height(self) -> int:
        try:
            output = get_app().output
            rows = output.get_size().rows
            input_height = self.input_field.window.render_info.window_height
            return max(1, rows - input_height - 3)
        except (AttributeError, RuntimeError):
            return 10

    def _transcript_scroll_max(self) -> int:
        if self._transcript_scroll_pane is None:
            return 0
        try:
            application = get_app()
            if not application.is_running:
                return 0
            output = application.output
            width = output.get_size().columns
            content_height = self._transcript_scroll_pane.content.preferred_height(
                width,
                self._transcript_scroll_pane.max_available_height,
            ).preferred
        except (AttributeError, RuntimeError):
            return 0
        return max(0, content_height - self._transcript_viewport_height())

    def scroll_transcript(self, lines: int) -> None:
        if self._transcript_scroll_pane is not None:
            scroll_max = self._transcript_scroll_max()
            next_scroll = min(
                scroll_max,
                self._transcript_scroll_pane.vertical_scroll + lines,
            )
            self._transcript_scroll_pane.vertical_scroll = max(0, next_scroll)
            if lines < 0:
                self._transcript_follow_bottom = False
            elif lines > 0 and next_scroll >= scroll_max:
                self._transcript_follow_bottom = True
            return
        if lines < 0:
            self.transcript_field.buffer.cursor_up(-lines)
            self._transcript_follow_bottom = False
        elif lines > 0:
            self.transcript_field.buffer.cursor_down(lines)
            if self.transcript_field.buffer.cursor_position >= len(
                self.transcript_field.text
            ):
                self._transcript_follow_bottom = True
        self.transcript_field.window.vertical_scroll = max(
            0,
            self.transcript_field.window.vertical_scroll + lines,
        )

    def page_scroll_transcript(self, direction: int) -> None:
        """Move the transcript by one visible page without changing its text."""
        render_info = self.transcript_field.window.render_info
        page_size = max(1, render_info.window_height - 1) if render_info else 10
        if self._transcript_scroll_pane is not None:
            page_size = max(1, self._transcript_viewport_height() - 1)
        self.scroll_transcript(direction * page_size)

    def scroll_transcript_to_top(self) -> None:
        if self._transcript_scroll_pane is not None:
            self._transcript_scroll_pane.vertical_scroll = 0
            self._transcript_follow_bottom = False
            return
        self.transcript_field.buffer.cursor_position = 0
        self.transcript_field.window.vertical_scroll = 0
        self._transcript_follow_bottom = False

    def scroll_transcript_to_bottom(self) -> None:
        if self._transcript_scroll_pane is not None:
            self._transcript_scroll_pane.vertical_scroll = self._transcript_scroll_max()
            self._transcript_follow_bottom = True
            return
        self.transcript_field.buffer.cursor_position = len(self.transcript_field.text)
        self.transcript_field.window.vertical_scroll = 10**9
        self._transcript_follow_bottom = True

    def copy_transcript_selection(self):
        if self.transcript_field.buffer.selection_state is None:
            return None
        return self.transcript_field.buffer.copy_selection()

    def copy_input_selection(self):
        if self.input_field.buffer.selection_state is None:
            return None
        return self.input_field.buffer.copy_selection()

    def _system_clipboard_commands(self, operation: str) -> list[list[str]]:
        if operation == "read":
            if sys.platform == "darwin":
                return [["pbpaste"]]
            if sys.platform == "win32":
                return [
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-Command",
                        "Get-Clipboard",
                    ],
                    ["Get-Clipboard"],
                ]
            return [
                ["wl-paste", "--no-newline"],
                ["xclip", "-selection", "clipboard", "-o"],
                ["xsel", "--clipboard", "--output"],
            ]

        if sys.platform == "darwin":
            return [["pbcopy"]]
        if sys.platform == "win32":
            return [["clip.exe"]]
        return [
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ]

    def read_from_system_clipboard(self) -> str | None:
        command = next(
            (
                candidate
                for candidate in self._system_clipboard_commands("read")
                if shutil.which(candidate[0])
            ),
            None,
        )
        if command is None:
            return None

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return result.stdout

    def paste_from_system_clipboard(self) -> bool:
        text = self.read_from_system_clipboard()
        if text is None:
            return False
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        buffer = self.input_field.buffer
        before = buffer.document.text_before_cursor
        after = buffer.document.text_after_cursor
        buffer.set_document(
            Document(
                f"{before}{normalized}{after}",
                cursor_position=len(before) + len(normalized),
            )
        )
        return True

    def copy_to_system_clipboard(self, text: str) -> bool:
        command = next(
            (
                candidate
                for candidate in self._system_clipboard_commands("write")
                if shutil.which(candidate[0])
            ),
            None,
        )
        if command is None:
            return False

        try:
            subprocess.run(command, input=text, text=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            return False
        return True

    def extend_transcript_selection(self, movement: str) -> None:
        buffer = self.transcript_field.buffer
        if not buffer.text:
            return
        if buffer.selection_state is None:
            buffer.start_selection()

        if movement == "left":
            buffer.cursor_left()
        elif movement == "right":
            buffer.cursor_right()
        elif movement == "up":
            buffer.cursor_up()
        elif movement == "down":
            buffer.cursor_down()
        elif movement == "home":
            buffer.cursor_position += buffer.document.get_start_of_line_position(
                after_whitespace=False
            )
        elif movement == "end":
            buffer.cursor_position += buffer.document.get_end_of_line_position()

        selection_state = buffer.selection_state
        if (
            selection_state is not None
            and buffer.cursor_position == selection_state.original_cursor_position
        ):
            buffer.exit_selection()

    def navigate_input_history(self, direction: int) -> None:
        if direction == 0:
            return
        history = self.input_history.get_strings()
        if not history:
            return

        if self._input_history_index is None:
            self._input_history_index = len(history) if direction > 0 else len(history) - 1
        else:
            self._input_history_index += direction
            self._input_history_index = max(
                0,
                min(self._input_history_index, len(history)),
            )

        if self._input_history_index == len(history):
            self.input_field.text = ""
        else:
            self.input_field.text = history[self._input_history_index]
            self.input_field.buffer.cursor_position = len(self.input_field.text)

    def update_task_snapshot(self, snapshot: TaskSnapshot) -> None:
        view = TaskViewModel.from_snapshot(snapshot)
        lines = [
            f"{row.status_icon} {row.subject} ({row.status_label})"
            for row in view.rows
        ]
        footer = f"{view.completed_count}/{view.total_count} completed"
        self.task_field.text = "\n".join(lines + [footer]) if lines else "No active tasks."

    def append_transcript(self, line: str, *, user_turn: bool | None = None) -> None:
        if user_turn is None:
            user_turn = line.startswith(TranscriptTurnProcessor.USER_PREFIX)
        prefix = (
            ("\n\n" if user_turn else "\n")
            if self.transcript_field.text and not self.transcript_field.text.endswith("\n")
            else ""
        )
        self._set_transcript_text(f"{self.transcript_field.text}{prefix}{line}")
        self._transcript_line_boundary = True
        self._transcript_turn_boundary = user_turn

    def append_transcript_delta(self, delta: str) -> None:
        if not delta:
            return
        text = self.transcript_field.text
        if self._transcript_line_boundary and text and not text.endswith("\n"):
            text += "\n\n" if self._transcript_turn_boundary else "\n"
        if self._transcript_line_boundary or not text:
            text += "NoteDesk > "
        self._set_transcript_text(f"{text}{delta}")
        self._transcript_line_boundary = False
        self._transcript_turn_boundary = False

    def _set_transcript_text(self, text: str) -> None:
        buffer = self.transcript_field.buffer
        selection_state = buffer.selection_state
        preserve_view = not self._transcript_follow_bottom or selection_state is not None
        cursor_position = (
            min(buffer.cursor_position, len(text)) if preserve_view else len(text)
        )
        buffer.set_document(
            Document(text, cursor_position=cursor_position),
            bypass_readonly=True,
        )
        if selection_state is not None:
            buffer.selection_state = selection_state
        if not preserve_view:
            self.scroll_transcript_to_bottom()

    def set_status(self, status: str) -> None:
        self.status_text = status

    def render_welcome_panel(self) -> str:
        """Return a text-only representation for non-layout callers and tests."""
        return f"NoteDesk\n{self.render_welcome_brand()}\n{self.render_welcome_runtime()}"

    def render_welcome_brand(self) -> str:
        return (
            f"{self.render_logo_top()}\n"
            f"{self.render_logo_note()}\n"
            f"{self.render_logo_desk()}\n"
            f"{self.render_logo_bottom()}\n"
            f"{self.render_brand_welcome()}\n"
            f"{self.render_brand_model()}\n"
            f"{self.render_brand_workspace()}"
        )

    def render_welcome_runtime(self) -> str:
        return "\n".join(
            [
                self.render_welcome_session_header(),
                self.render_welcome_model(),
                self.render_welcome_workspace(),
                self.render_welcome_artifacts(),
                self.render_welcome_tips_body(),
                self.render_welcome_permissions(),
            ]
        )

    def render_brand_welcome(self) -> str:
        return "Welcome back!"

    def render_logo_top(self) -> str:
        return "+-------+"

    def render_logo_note(self) -> str:
        return "| NOTE  |"

    def render_logo_desk(self) -> str:
        return "| DESK  |"

    def render_logo_bottom(self) -> str:
        return "+-------+"

    def render_brand_model(self) -> str:
        return "deepseek-chat · local-first"

    def render_brand_workspace(self) -> str:
        return self._display_path(self.workspace)

    def render_welcome_tips_header(self) -> str:
        return "Tips for getting started"

    def render_welcome_tips_body(self) -> str:
        return "Enter send · Esc+Enter newline"

    def render_welcome_session_header(self) -> str:
        return "Session overview · ready"

    def render_welcome_model(self) -> str:
        return "model:      deepseek-chat"

    def render_welcome_workspace(self) -> str:
        return f"workspace:  {self._display_path(self.workspace)}"

    def render_welcome_artifacts(self) -> str:
        artifact_path = self._display_path(self.artifact_root)
        return f"artifacts:  {artifact_path}"

    def render_welcome_permissions(self) -> str:
        return "permissions: confirm edits"

    def _welcome_window(
        self,
        renderer: Callable[[], str],
        *,
        align: WindowAlign = WindowAlign.LEFT,
        style: str = "",
    ) -> Window:
        return Window(
            content=FormattedTextControl(renderer),
            height=1,
            align=align,
            style=style,
        )

    def render_setup_notice(self) -> str:
        return "! confirm mode enabled · Ctrl-Y approve · Ctrl-N deny · /doctor"

    def render_task_header(self) -> str:
        return "Tasks · read-only snapshot"

    def render_status_bar(self) -> str:
        drawer = "Tasks open" if self.task_drawer_open else "Tasks closed"
        return (
            f"{self.status_text} · {drawer} · Enter send · "
            "Esc+Enter newline · Ctrl-T tasks · Ctrl-C clear/exit"
        )

    def handle_submit(self) -> None:
        if self.pending_permission is not None:
            return
        submitted = self.input_field.text.strip()
        if not submitted:
            return
        self.input_history.append_string(submitted)
        self._input_history_index = None
        self.append_transcript(f"You  > {submitted}", user_turn=True)
        self.on_submit(submitted)
        self.input_field.buffer.reset()
        self.set_status("Submitted")

    def handle_cancel(self) -> None:
        self.on_cancel()
        self.set_status("Cancelling")

    def handle_insert_newline(self) -> None:
        self.input_field.text += "\n"

    def handle_ctrl_c(self) -> str:
        if self.input_field.text:
            self._ctrl_c_exit_pending = True
            self.input_field.text = ""
            self.set_status("Input cleared")
            return "cleared_input"
        if not self._ctrl_c_exit_pending:
            self._ctrl_c_exit_pending = True
            self.set_status("Press Ctrl-C again to exit")
            return "awaiting_exit"
        self._ctrl_c_exit_pending = False
        self.set_status("Exit requested")
        return "request_exit"

    def show_permission_request(self, event: PermissionRequestEvent) -> None:
        self.pending_permission = event
        self._permission_choice = 0
        self.set_status("Waiting for permission")
        self.scroll_transcript_to_bottom()
        try:
            get_app().invalidate()
        except RuntimeError:
            pass

    def render_permission_prompt_text(self) -> str:
        if self.pending_permission is None:
            return ""
        event = self.pending_permission
        operation = event.details or "The tool requests permission to continue."
        if operation.startswith("command: "):
            operation = operation.removeprefix("command: ")
        selected_yes = "❯" if self._permission_choice == 0 else " "
        selected_no = "❯" if self._permission_choice == 1 else " "
        return (
            f"{event.tool_name} command\n\n"
            f"  {operation}\n"
            f"  {event.summary}\n\n"
            "This command requires approval\n\n"
            "Do you want to proceed?\n"
            f"{selected_yes} 1. Yes, proceed\n"
            f"{selected_no} 2. No, deny\n\n"
            "Esc to cancel · Ctrl-Y approve · Ctrl-N deny"
        )

    def render_permission_prompt(self):
        if self.pending_permission is None:
            return []
        lines = self.render_permission_prompt_text().splitlines(keepends=True)
        fragments = []
        for line in lines:
            if line.startswith(f"{self.pending_permission.tool_name} command"):
                style = "class:permission.title"
            elif line.startswith("  "):
                style = "class:permission.detail"
            elif line.startswith("❯"):
                style = "class:permission.selected"
            elif line.startswith("Esc to cancel"):
                style = "class:permission.detail"
            else:
                style = ""
            fragments.append((style, line))
        return fragments

    def move_permission_selection(self, direction: int) -> None:
        if self.pending_permission is None:
            return
        self._permission_choice = (self._permission_choice + direction) % 2

    def handle_permission_selection(self) -> None:
        if self._permission_choice == 0:
            self.handle_approve_permission()
        else:
            self.handle_deny_permission()

    def show_artifact_receipt(self, receipt: ArtifactReceipt) -> None:
        self.set_status("Artifact saved")

    def handle_approve_permission(self) -> None:
        if self.pending_permission is None:
            return
        self.on_approve_permission()
        self.pending_permission = None
        self._permission_choice = 0
        self.set_status("Permission approved")

    def handle_deny_permission(self) -> None:
        if self.pending_permission is None:
            return
        self.on_deny_permission()
        self.pending_permission = None
        self._permission_choice = 0
        self.set_status("Permission denied")

    def _build_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        def _copy_selection(event) -> bool:
            copied = self.copy_transcript_selection()
            if copied is None:
                copied = self.copy_input_selection()
            if copied is None:
                return False
            event.app.clipboard.set_data(copied)
            if self.copy_to_system_clipboard(copied.text):
                self.set_status(f"Copied {len(copied.text)} chars")
            else:
                self.set_status("Copied to session clipboard")
            event.app.layout.focus(self.input_field)
            return True

        @kb.add("enter", filter=has_focus(self.input_field))
        def _submit(event) -> None:
            if self.pending_permission is not None:
                self.handle_permission_selection()
            else:
                self.handle_submit()
            event.app.invalidate()

        @kb.add("escape")
        def _cancel(event) -> None:
            if self.pending_permission is not None:
                self.handle_deny_permission()
                event.app.invalidate()
                return
            if event.current_buffer is self.transcript_field.buffer:
                event.app.layout.focus(self.input_field)
                self.set_status("Input focused")
                event.app.invalidate()
                return
            self.handle_cancel()
            event.app.invalidate()

        @kb.add("escape", "enter", filter=has_focus(self.input_field))
        def _newline(event) -> None:
            self.handle_insert_newline()
            event.app.invalidate()

        @kb.add(COMMAND_C_KEY)
        def _command_c(event) -> None:
            _copy_selection(event)
            event.app.invalidate()

        @kb.add(SHIFT_PRINTABLE_KEY, filter=has_focus(self.input_field))
        def _shift_printable(event) -> None:
            match = re.fullmatch(r"\x1b\[27;2;(\d+)~", event.data)
            if match is None:
                return
            code = int(match.group(1))
            if ord(" ") <= code <= ord("~"):
                event.current_buffer.insert_text(chr(code))
            event.app.invalidate()

        @kb.add("c-c")
        @kb.add("<sigint>")
        def _ctrl_c(event) -> None:
            if _copy_selection(event):
                event.app.invalidate()
                return
            if event.current_buffer is self.transcript_field.buffer:
                event.app.layout.focus(self.input_field)
                self.set_status("Input focused")
                event.app.invalidate()
                return
            outcome = self.handle_ctrl_c()
            if outcome == "request_exit":
                event.app.exit()
            event.app.invalidate()

        @kb.add("c-v")
        def _paste(event) -> None:
            event.app.layout.focus(self.input_field)
            if self.paste_from_system_clipboard():
                self.set_status("Pasted from system clipboard")
            else:
                self.set_status("System clipboard unavailable")
            event.app.invalidate()

        @kb.add("c-y")
        def _approve(event) -> None:
            self.handle_approve_permission()
            event.app.invalidate()

        @kb.add("c-n")
        def _deny(event) -> None:
            self.handle_deny_permission()
            event.app.invalidate()

        @kb.add(
            "up",
            filter=Condition(lambda: self.pending_permission is not None),
            eager=True,
        )
        def _permission_up(event) -> None:
            self.move_permission_selection(-1)
            event.app.invalidate()

        @kb.add(
            "down",
            filter=Condition(lambda: self.pending_permission is not None),
            eager=True,
        )
        def _permission_down(event) -> None:
            self.move_permission_selection(1)
            event.app.invalidate()

        @kb.add("c-t")
        def _toggle_tasks(event) -> None:
            self.toggle_task_drawer()
            event.app.invalidate()

        @kb.add("<scroll-up>")
        def _scroll_up(event) -> None:
            self.scroll_transcript(-3)
            event.app.invalidate()

        @kb.add("<scroll-down>")
        def _scroll_down(event) -> None:
            self.scroll_transcript(3)
            event.app.invalidate()

        @kb.add("pageup")
        @kb.add("c-u")
        def _page_up(event) -> None:
            self.page_scroll_transcript(-1)
            event.app.invalidate()

        @kb.add("pagedown")
        @kb.add("c-d")
        def _page_down(event) -> None:
            self.page_scroll_transcript(1)
            event.app.invalidate()

        @kb.add("home", filter=has_focus(self.transcript_field))
        def _transcript_home(event) -> None:
            self.scroll_transcript_to_top()
            event.app.invalidate()

        @kb.add("end", filter=has_focus(self.transcript_field))
        def _transcript_end(event) -> None:
            self.scroll_transcript_to_bottom()
            event.app.invalidate()

        @kb.add("s-left", filter=has_focus(self.transcript_field))
        @kb.add("s-right", filter=has_focus(self.transcript_field))
        @kb.add("s-up", filter=has_focus(self.transcript_field))
        @kb.add("s-down", filter=has_focus(self.transcript_field))
        @kb.add("s-home", filter=has_focus(self.transcript_field))
        @kb.add("s-end", filter=has_focus(self.transcript_field))
        def _extend_transcript_selection(event) -> None:
            key = str(event.key_sequence[0].key)
            movement = {
                "Keys.ShiftLeft": "left",
                "Keys.ShiftRight": "right",
                "Keys.ShiftUp": "up",
                "Keys.ShiftDown": "down",
                "Keys.ShiftHome": "home",
                "Keys.ShiftEnd": "end",
            }.get(key)
            if movement is not None:
                self.extend_transcript_selection(movement)
                event.app.invalidate()

        @kb.add("up", filter=has_focus(self.input_field))
        def _history_up(event) -> None:
            self.navigate_input_history(-1)
            event.app.invalidate()

        @kb.add("down", filter=has_focus(self.input_field))
        def _history_down(event) -> None:
            self.navigate_input_history(1)
            event.app.invalidate()

        return kb

    def _display_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.workspace))
        except ValueError:
            return str(path)
