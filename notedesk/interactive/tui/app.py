from __future__ import annotations

from pathlib import Path
from typing import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, VerticalAlign, WindowAlign
from prompt_toolkit.layout.containers import ConditionalContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.filters import Condition
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from notedesk.agent.events import PermissionRequestEvent
from notedesk.agent.middleware import TaskSnapshot
from notedesk.artifacts.models import ArtifactReceipt
from notedesk.interactive.tui.tasks import TaskViewModel


class NoteDeskTUI:
    def __init__(self, workspace: Path, artifact_root: Path) -> None:
        self.workspace = workspace
        self.artifact_root = artifact_root
        self.task_drawer_open = False
        self.status_text = "Idle"
        self.on_submit: Callable[[str], None] = lambda text: None
        self.on_cancel: Callable[[], None] = lambda: None
        self.on_approve_permission: Callable[[], None] = lambda: None
        self.on_deny_permission: Callable[[], None] = lambda: None
        self.pending_permission: PermissionRequestEvent | None = None

        self.transcript_field = TextArea(
            text="",
            read_only=True,
            scrollbar=False,
            focusable=False,
            height=Dimension(weight=1),
        )
        self.input_field = TextArea(
            text="",
            multiline=True,
            prompt="> ",
            height=Dimension(min=1, max=4, preferred=1),
            dont_extend_height=True,
        )
        self.task_field = TextArea(
            text="No active tasks.",
            read_only=True,
            focusable=False,
        )

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
        welcome_panel = Frame(
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
                            self._welcome_window(self.render_welcome_shortcuts),
                        ],
                        align=VerticalAlign.TOP,
                        width=Dimension(weight=5),
                    ),
                ]
            ),
            title="NoteDesk",
            height=Dimension(min=11, max=11, preferred=11),
        )
        root = HSplit(
            [
                welcome_panel,
                Window(
                    content=FormattedTextControl(self.render_setup_notice),
                    height=1,
                ),
                self.transcript_field,
                task_drawer,
                Window(char="-", height=1),
                self.input_field,
                Window(char="-", height=1),
                Window(
                    content=FormattedTextControl(self.render_status_bar),
                    height=1,
                ),
            ],
            align=VerticalAlign.TOP,
        )
        return Application(
            layout=Layout(root, focused_element=self.input_field),
            key_bindings=self._build_key_bindings(),
            full_screen=True,
            erase_when_done=True,
            style=Style.from_dict(
                {
                    "welcome.heading": "bold",
                    "welcome.logo": "bold",
                    "welcome.meta": "",
                    "welcome.value": "bold",
                }
            ),
            input=input,
            output=output,
        )

    def toggle_task_drawer(self) -> None:
        self.task_drawer_open = not self.task_drawer_open

    def update_task_snapshot(self, snapshot: TaskSnapshot) -> None:
        view = TaskViewModel.from_snapshot(snapshot)
        lines = [
            f"{row.status_icon} {row.subject} ({row.status_label})"
            for row in view.rows
        ]
        footer = f"{view.completed_count}/{view.total_count} completed"
        self.task_field.text = "\n".join(lines + [footer]) if lines else "No active tasks."

    def append_transcript(self, line: str) -> None:
        prefix = "\n" if self.transcript_field.text else ""
        self.transcript_field.text += f"{prefix}{line}"

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
                self.render_welcome_shortcuts(),
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

    def render_welcome_shortcuts(self) -> str:
        return "Ctrl-T tasks · Ctrl-Y approve · Ctrl-N deny · /doctor"

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
        submitted = self.input_field.text.strip()
        if not submitted:
            return
        self.append_transcript(f"> {submitted}")
        self.on_submit(submitted)
        self.input_field.text = ""
        self.set_status("Submitted")

    def handle_cancel(self) -> None:
        self.on_cancel()
        self.set_status("Cancelling")

    def handle_insert_newline(self) -> None:
        self.input_field.text += "\n"

    def handle_ctrl_c(self) -> str:
        if self.input_field.text:
            self.input_field.text = ""
            self.set_status("Input cleared")
            return "cleared_input"
        self.set_status("Exit requested")
        return "request_exit"

    def show_permission_request(self, event: PermissionRequestEvent) -> None:
        self.pending_permission = event
        self.append_transcript(
            f"! Permission needed: {event.summary} · Ctrl-Y approve · Ctrl-N deny"
        )
        self.set_status("Waiting for permission")

    def show_artifact_receipt(self, receipt: ArtifactReceipt) -> None:
        self.append_transcript(
            f"* Saved artifact: {self._display_path(receipt.path)} ({receipt.bytes_written} bytes)"
        )
        self.set_status("Artifact saved")

    def handle_approve_permission(self) -> None:
        if self.pending_permission is None:
            return
        self.on_approve_permission()
        self.pending_permission = None
        self.set_status("Permission approved")

    def handle_deny_permission(self) -> None:
        if self.pending_permission is None:
            return
        self.on_deny_permission()
        self.pending_permission = None
        self.set_status("Permission denied")

    def _build_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("enter")
        def _submit(event) -> None:
            self.handle_submit()
            event.app.invalidate()

        @kb.add("escape")
        def _cancel(event) -> None:
            self.handle_cancel()
            event.app.invalidate()

        @kb.add("escape", "enter")
        def _newline(event) -> None:
            self.handle_insert_newline()
            event.app.invalidate()

        @kb.add("c-c")
        def _ctrl_c(event) -> None:
            outcome = self.handle_ctrl_c()
            if outcome == "request_exit":
                event.app.exit()
            event.app.invalidate()

        @kb.add("c-y")
        def _approve(event) -> None:
            self.handle_approve_permission()
            event.app.invalidate()

        @kb.add("c-n")
        def _deny(event) -> None:
            self.handle_deny_permission()
            event.app.invalidate()

        @kb.add("c-t")
        def _toggle_tasks(event) -> None:
            self.toggle_task_drawer()
            event.app.invalidate()

        return kb

    def _display_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.workspace))
        except ValueError:
            return str(path)
