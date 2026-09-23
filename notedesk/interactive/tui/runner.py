from __future__ import annotations

import asyncio

from notedesk.agent.events import (
    PermissionRequestEvent,
    ReplyLifecycleEvent,
    TaskSnapshotEvent,
    TextDeltaEvent,
    ToolLifecycleEvent,
)
from notedesk.agent.runtime import AgentSessionRuntime
from notedesk.artifacts.models import ArtifactReceipt
from notedesk.interactive.tui.app import NoteDeskTUI


class TUISessionController:
    def __init__(self, tui: NoteDeskTUI, runtime: AgentSessionRuntime) -> None:
        self.tui = tui
        self.runtime = runtime

    async def submit_prompt(self, prompt: str) -> None:
        self.tui.set_status("Running")
        await self._run_with_event_pump(self.runtime.run_once(prompt))

    async def approve_permission(self) -> None:
        self.tui.set_status("Permission approved")
        await self._run_with_event_pump(self.runtime.resume_permission(True))

    async def deny_permission(self) -> None:
        self.tui.set_status("Permission denied")
        await self._run_with_event_pump(self.runtime.resume_permission(False))

    async def cancel(self) -> None:
        self.tui.set_status("Cancelling")
        await self._run_with_event_pump(self.runtime.cancel())

    async def _run_with_event_pump(self, operation) -> None:
        run_task = asyncio.create_task(operation)
        try:
            while True:
                event_task = asyncio.create_task(self.runtime.ui_queue.get())
                done, _ = await asyncio.wait(
                    {run_task, event_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if event_task in done:
                    self._apply_event(event_task.result())
                else:
                    event_task.cancel()
                    await asyncio.gather(event_task, return_exceptions=True)

                if run_task in done:
                    try:
                        run_task.result()
                    except Exception as exc:
                        self.tui.set_status(f"Error: {self._format_runtime_error(exc)}")
                        return
                    await self.drain_events()
                    return
        finally:
            if not run_task.done():
                run_task.cancel()
                await asyncio.gather(run_task, return_exceptions=True)

    @staticmethod
    def _format_runtime_error(exc: Exception) -> str:
        """Return a concise status-bar-safe description of a runtime failure."""
        detail = str(exc).strip() or type(exc).__name__
        return detail.splitlines()[0][:160]

    async def drain_events(self) -> None:
        while not self.runtime.ui_queue.empty():
            event = self.runtime.ui_queue.get_nowait()
            self._apply_event(event)

    def _apply_event(self, event: object) -> None:
        if isinstance(event, TextDeltaEvent):
            self.tui.append_reply_delta(event.delta)
        elif isinstance(event, ToolLifecycleEvent):
            # A call start proves that preceding text was interim progress.
            # Result phases remain status-only to avoid three history rows per
            # tool invocation.
            if event.phase == "call_start":
                self.tui.record_tool_call(event.tool_name, event.summary)
            self.tui.set_status(f"Tool: {event.summary}")
        elif isinstance(event, PermissionRequestEvent):
            self.tui.show_permission_request(event)
        elif isinstance(event, TaskSnapshotEvent):
            self.tui.update_task_snapshot(event.snapshot)
        elif isinstance(event, ReplyLifecycleEvent):
            if event.phase == "start":
                self.tui.start_reply(event.reply_id)
                self.tui.set_status("Running")
            else:
                self.tui.finish_reply(event.reply_id)
                if event.finished_reason == "exceed_max_iters":
                    self.tui.set_status("Stopped: max iterations reached")
                else:
                    self.tui.set_status("Idle")
        elif isinstance(event, ArtifactReceipt):
            self.tui.show_artifact_receipt(event)
