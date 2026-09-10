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
        await self.ui_queue.put(TextDeltaEvent(delta=" world"))
        await self.ui_queue.put(TextDeltaEvent(delta="\nnext"))
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


class StreamingRuntime:
    def __init__(self) -> None:
        self.ui_queue: asyncio.Queue = asyncio.Queue()
        self.first_delta_emitted = asyncio.Event()
        self.release_second_delta = asyncio.Event()

    async def run_once(self, prompt: str):
        await self.ui_queue.put(ReplyLifecycleEvent(phase="start", reply_id="r1"))
        await self.ui_queue.put(TextDeltaEvent(delta="first"))
        self.first_delta_emitted.set()
        await self.release_second_delta.wait()
        await self.ui_queue.put(TextDeltaEvent(delta=" second"))
        await self.ui_queue.put(ReplyLifecycleEvent(phase="end", reply_id="r1"))
        return None

    async def resume_permission(self, approved: bool):
        return None

    async def cancel(self):
        return None


def test_tui_session_controller_submits_and_drains_events(tmp_path: Path) -> None:
    tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    runtime = FakeRuntime()
    controller = TUISessionController(tui, runtime)  # type: ignore[arg-type]

    asyncio.run(controller.submit_prompt("Summarize this"))

    assert runtime.submitted == ["Summarize this"]
    assert "NoteDesk > hello world" in tui.transcript_field.text
    assert "hello\n world" not in tui.transcript_field.text
    assert tui.transcript_field.text.count("NoteDesk >") == 1
    assert "hello world\nnext" in tui.transcript_field.text
    assert "Collect tweets" in tui.task_field.text


def test_tui_session_controller_renders_streaming_deltas_before_run_finishes(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
        runtime = StreamingRuntime()
        controller = TUISessionController(tui, runtime)  # type: ignore[arg-type]

        submit_task = asyncio.create_task(controller.submit_prompt("Stream this"))
        await runtime.first_delta_emitted.wait()
        await asyncio.sleep(0.01)

        assert "NoteDesk > first" in tui.transcript_field.text
        assert "second" not in tui.transcript_field.text

        runtime.release_second_delta.set()
        await submit_task
        assert "NoteDesk > first second" in tui.transcript_field.text

    asyncio.run(scenario())


def test_tui_session_controller_approves_permission_and_renders_receipt(tmp_path: Path) -> None:
    tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
    runtime = FakeRuntime()
    controller = TUISessionController(tui, runtime)  # type: ignore[arg-type]
    tui.show_permission_request(
        PermissionRequestEvent(tool_name="Bash", summary="Permission required")
    )

    asyncio.run(controller.approve_permission())

    assert runtime.approved == 1
    assert "summary.md" not in tui.transcript_field.text
    assert tui.status_text == "Artifact saved"
