import asyncio
from pathlib import Path

from notedesk.agent.events import ReplyLifecycleEvent, TaskSnapshotEvent, TextDeltaEvent
from notedesk.agent.middleware import TaskSnapshot, TaskSnapshotItem
from notedesk.interactive.tui.app import NoteDeskTUI
from tests.interactive.tui.harness import TUIHarness


class AcceptanceRuntime:
    def __init__(self) -> None:
        self.ui_queue: asyncio.Queue = asyncio.Queue()
        self.submitted: list[str] = []

    async def run_once(self, prompt: str):
        self.submitted.append(prompt)
        await self.ui_queue.put(ReplyLifecycleEvent(phase="start", reply_id="r1"))
        await self.ui_queue.put(
            TaskSnapshotEvent(
                snapshot=TaskSnapshot(
                    tasks=[
                        TaskSnapshotItem(
                            id="task-1",
                            subject="Collect tweets",
                            description="Fetch timeline",
                            state="in_progress",
                            owner=None,
                            metadata={},
                        )
                    ]
                )
            )
        )
        await self.ui_queue.put(TextDeltaEvent(delta="# Summary"))
        await self.ui_queue.put(TextDeltaEvent(delta="\n\n- Done"))
        await self.ui_queue.put(ReplyLifecycleEvent(phase="end", reply_id="r1"))
        return None

    async def resume_permission(self, approved: bool):
        return None

    async def deny_permission(self):
        return None

    async def cancel(self):
        return None


def test_tui_harness_drives_real_input_to_streamed_reply(tmp_path: Path) -> None:
    async def scenario() -> None:
        runtime = AcceptanceRuntime()
        harness = TUIHarness(NoteDeskTUI(tmp_path, tmp_path / "artifacts"), runtime)
        await harness.start()
        try:
            await harness.type_text("Summarize this")
            await harness.press("enter")
            await harness.wait_until(lambda: runtime.submitted == ["Summarize this"])
            await harness.wait_until(lambda: "# Summary" in harness.transcript())

            assert "Summarize this" in harness.transcript()
            assert "- Done" in harness.transcript()
            assert "Collect tweets" in harness.tasks()
            assert harness.status() == "Idle"
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_timeout_includes_current_state(tmp_path: Path) -> None:
    async def scenario() -> None:
        harness = TUIHarness(
            NoteDeskTUI(tmp_path, tmp_path / "artifacts"),
            AcceptanceRuntime(),
        )
        await harness.start()
        try:
            try:
                await harness.wait_until(lambda: False, timeout=0.01)
            except AssertionError as exc:
                message = str(exc)
                assert "Transcript:" in message
                assert "Status:" in message
            else:
                raise AssertionError("wait_until should time out")
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_copies_selected_prompt_text_with_command_c(tmp_path: Path) -> None:
    async def scenario() -> None:
        runtime = AcceptanceRuntime()
        tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
        copied: list[str] = []
        tui.copy_to_system_clipboard = lambda text: copied.append(text) or True
        harness = TUIHarness(tui, runtime)
        await harness.start()
        try:
            await harness.type_text("copy this prompt")
            await harness.press("ctrl-a")
            await harness.press("shift+end")
            await harness.send_terminal_sequence("\x1b[27;9;99~")
            await harness.wait_until(lambda: copied == ["copy this prompt"])

            assert harness.tui.input_field.text == "copy this prompt"
            assert harness.application.clipboard.get_data().text == "copy this prompt"
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_decodes_xterm_shift_letters_as_prompt_text(tmp_path: Path) -> None:
    async def scenario() -> None:
        harness = TUIHarness(
            NoteDeskTUI(tmp_path, tmp_path / "artifacts"),
            AcceptanceRuntime(),
        )
        await harness.start()
        try:
            for letter in "GDSQ":
                await harness.send_terminal_sequence(f"\x1b[27;2;{ord(letter)}~")

            await harness.wait_until(lambda: harness.tui.input_field.text == "GDSQ")
            assert "[27;2;" not in harness.tui.input_field.text
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_handles_xterm_shift_delete_as_backspace(tmp_path: Path) -> None:
    async def scenario() -> None:
        harness = TUIHarness(
            NoteDeskTUI(tmp_path, tmp_path / "artifacts"),
            AcceptanceRuntime(),
        )
        await harness.start()
        try:
            await harness.type_text("AB")
            await harness.send_terminal_sequence("\x1b[27;2;127~")

            await harness.wait_until(lambda: harness.tui.input_field.text == "A")
            assert "[27;2;127~" not in harness.tui.input_field.text
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_pages_through_long_transcript_to_the_top(tmp_path: Path) -> None:
    async def scenario() -> None:
        tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
        tui.append_transcript("\n".join(f"line {index}" for index in range(100)))
        harness = TUIHarness(tui, AcceptanceRuntime())
        await harness.start()
        try:
            initial = tui.transcript_field.window.render_info
            assert initial is not None
            assert initial.first_visible_line() > 0

            for _ in range(10):
                await harness.press("page-up")

            await harness.wait_until(
                lambda: (
                    tui.transcript_field.window.render_info is not None
                    and tui.transcript_field.window.render_info.first_visible_line() == 0
                )
            )
        finally:
            await harness.stop()

    asyncio.run(scenario())
