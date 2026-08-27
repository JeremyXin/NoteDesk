from __future__ import annotations

from pathlib import Path
from typing import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.layout.containers import ConditionalContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.filters import Condition
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

        self.transcript_field = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            focusable=False,
        )
        self.input_field = TextArea(
            text="",
            multiline=True,
            prompt="> ",
            height=Dimension(min=3),
        )
        self.task_field = TextArea(
            text="No tasks yet.",
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
            content=Frame(self.task_field, title="Tasks"),
            filter=Condition(lambda: self.task_drawer_open),
        )
        root = HSplit(
            [
                Frame(self.transcript_field, title="Transcript"),
                task_drawer,
                Frame(self.input_field, title="Input"),
                Window(
                    content=FormattedTextControl(self.render_status_bar),
                    height=1,
                ),
            ]
        )
        return Application(
            layout=Layout(root, focused_element=self.input_field),
            key_bindings=self._build_key_bindings(),
            full_screen=False,
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
        self.task_field.text = "\n".join(lines + [footer]) if lines else "No tasks yet."

    def append_transcript(self, line: str) -> None:
        prefix = "\n" if self.transcript_field.text else ""
        self.transcript_field.text += f"{prefix}{line}"

    def set_status(self, status: str) -> None:
        self.status_text = status

    def render_status_bar(self) -> str:
        drawer = "Tasks: open" if self.task_drawer_open else "Tasks: closed"
        return f"{self.status_text} | {drawer} | Artifacts: {self.artifact_root}"

    def handle_submit(self) -> None:
        submitted = self.input_field.text.strip()
        if not submitted:
            return
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
        self.append_transcript(f"Permission: {event.summary}")
        self.set_status("Waiting for permission")

    def show_artifact_receipt(self, receipt: ArtifactReceipt) -> None:
        self.append_transcript(
            f"Artifact saved: {receipt.path.name} ({receipt.bytes_written} bytes)"
        )
        self.set_status("Artifact saved")

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
            self.handle_ctrl_c()
            event.app.invalidate()

        @kb.add("c-t")
        def _toggle_tasks(event) -> None:
            self.toggle_task_drawer()
            event.app.invalidate()

        return kb
