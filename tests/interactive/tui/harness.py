from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from notedesk.interactive.tui.app import NoteDeskTUI
from notedesk.interactive.tui.runner import TUISessionController


class TUIHarness:
    """Drive the real TUI through deterministic terminal-like input."""

    _KEY_SEQUENCES = {
        "ctrl-a": "\x01",
        "enter": "\r",
        "shift+enter": "\x1b\r",
        "shift+end": "\x1b[1;2F",
        "escape": "\x1b",
        "ctrl-c": "\x03",
        "ctrl-n": "\x0e",
        "ctrl-t": "\x14",
        "ctrl-v": "\x16",
        "ctrl-y": "\x19",
        "page-up": "\x1b[5~",
        "page-down": "\x1b[6~",
        "ctrl-u": "\x15",
        "ctrl-d": "\x04",
    }

    def __init__(self, tui: NoteDeskTUI, runtime: Any) -> None:
        self.tui = tui
        self.runtime = runtime
        self._pipe_input_context = create_pipe_input()
        self._pipe_input = self._pipe_input_context.__enter__()
        self.application = tui.build_application(
            input=self._pipe_input,
            output=DummyOutput(),
        )
        self.controller = TUISessionController(tui=tui, runtime=runtime)
        self._run_task: asyncio.Task | None = None

        self.tui.on_submit = lambda text: self.application.create_background_task(
            self.controller.submit_prompt(text)
        )
        self.tui.on_cancel = lambda: self.application.create_background_task(
            self.controller.cancel()
        )
        self.tui.on_approve_permission = lambda: self.application.create_background_task(
            self.controller.approve_permission()
        )
        self.tui.on_deny_permission = lambda: self.application.create_background_task(
            self.controller.deny_permission()
        )

    async def start(self) -> None:
        if self._run_task is not None:
            raise RuntimeError("TUIHarness has already started")
        self._run_task = asyncio.create_task(self.application.run_async())
        await asyncio.sleep(0)

    async def stop(self) -> None:
        if self._run_task is not None and not self._run_task.done():
            self.application.exit()
            await self._run_task
        if self._pipe_input_context is not None:
            self._pipe_input_context.__exit__(None, None, None)
            self._pipe_input_context = None

    async def type_text(self, text: str) -> None:
        self._pipe_input.send_text(text)
        await asyncio.sleep(0)

    async def press(self, key: str) -> None:
        try:
            sequence = self._KEY_SEQUENCES[key]
        except KeyError as exc:
            raise ValueError(f"Unsupported harness key: {key}") from exc
        self._pipe_input.send_text(sequence)
        await asyncio.sleep(0)

    async def send_terminal_sequence(self, sequence: str) -> None:
        self._pipe_input.send_text(sequence)
        await asyncio.sleep(0)

    async def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        timeout: float = 1.0,
    ) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            await asyncio.sleep(0.001)

        snapshot = self.snapshot()
        raise AssertionError(
            "TUI Harness wait_until timed out\n"
            f"Transcript: {snapshot['transcript']}\n"
            f"Status: {snapshot['status']}\n"
            f"Tasks: {snapshot['tasks']}"
        )

    def transcript(self) -> str:
        return self.tui.transcript_field.text

    def status(self) -> str:
        return self.tui.status_text

    def tasks(self) -> str:
        return self.tui.task_field.text

    def screen_text(self) -> str:
        return "\n".join(
            [
                self.tui.render_welcome_panel(),
                self.transcript(),
                self.tasks(),
                self.status(),
            ]
        )

    def snapshot(self) -> dict[str, str]:
        return {
            "transcript": self.transcript(),
            "status": self.status(),
            "tasks": self.tasks(),
            "screen": self.screen_text(),
        }
