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
                    run_task.result()
                    await self.drain_events()
                    return
        finally:
            if not run_task.done():
                run_task.cancel()
                await asyncio.gather(run_task, return_exceptions=True)

    async def drain_events(self) -> None:
        while not self.runtime.ui_queue.empty():
            event = self.runtime.ui_queue.get_nowait()
            self._apply_event(event)

    def _apply_event(self, event: object) -> None:
        if isinstance(event, TextDeltaEvent):
            self.tui.append_transcript_delta(event.delta)
        elif isinstance(event, ToolLifecycleEvent):
            self.tui.append_transcript(f"Tool: {event.summary}")
        elif isinstance(event, PermissionRequestEvent):
            self.tui.show_permission_request(event)
        elif isinstance(event, TaskSnapshotEvent):
            self.tui.update_task_snapshot(event.snapshot)
        elif isinstance(event, ReplyLifecycleEvent):
            self.tui.set_status("Running" if event.phase == "start" else "Idle")
        elif isinstance(event, ArtifactReceipt):
            self.tui.show_artifact_receipt(event)
