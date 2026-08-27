import asyncio
from pathlib import Path

from notedesk.agent.events import PermissionRequestEvent, ReplyLifecycleEvent, TaskSnapshotEvent, TextDeltaEvent
from notedesk.agent.middleware import TaskSnapshot, TaskSnapshotItem
from notedesk.artifacts.models import ArtifactReceipt
from notedesk.interactive.tui.app import NoteDeskTUI
from notedesk.interactive.tui.runner import TUISessionController


class FakeRuntime:
    def __init__(self) -> None:
        self.ui_queue: asyncio.Queue = asyncio.Queue()
        self.submitted: list[str] = []
        self.approved = 0
        self.denied = 0
        self.cancelled = 0

    async def run_once(self, prompt: str):
        self.submitted.append(prompt)
        await self.ui_queue.put(ReplyLifecycleEvent(phase="start", reply_id="r1"))
        await self.ui_queue.put(TextDeltaEvent(delta="hello"))
        await self.ui_queue.put(
            TaskSnapshotEvent(
                snapshot=TaskSnapshot(
                    tasks=[
                        TaskSnapshotItem(
                            id="1",
                            subject="Collect tweets",
                            description="Fetch",
                            state="in_progress",
                            owner=None,
                            metadata={},
                        )
                    ]
                )
            )
        )
        await self.ui_queue.put(ReplyLifecycleEvent(phase="end", reply_id="r1"))
        return None

    async def resume_permission(self, approved: bool):
        if approved:
            self.approved += 1
        else:
            self.denied += 1
        await self.ui_queue.put(
            ArtifactReceipt(
                path=Path("summary.md"),
                bytes_written=12,
                sources=["twitter:timeline"],
            )
        )
        return None

    async def cancel(self):
        self.cancelled += 1
        return None


def test_tui_session_controller_submits_and_drains_events(tmp_path: Path) -> None:
    tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    runtime = FakeRuntime()
    controller = TUISessionController(tui, runtime)  # type: ignore[arg-type]

    asyncio.run(controller.submit_prompt("Summarize this"))

    assert runtime.submitted == ["Summarize this"]
    assert "hello" in tui.transcript_field.text
    assert "Collect tweets" in tui.task_field.text


def test_tui_session_controller_approves_permission_and_renders_receipt(tmp_path: Path) -> None:
    tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    runtime = FakeRuntime()
    controller = TUISessionController(tui, runtime)  # type: ignore[arg-type]
    tui.show_permission_request(
        PermissionRequestEvent(tool_name="Bash", summary="Permission required")
    )

    asyncio.run(controller.approve_permission())

    assert runtime.approved == 1
    assert "summary.md" in tui.transcript_field.text
