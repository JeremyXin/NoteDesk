import asyncio
from pathlib import Path

from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import DummyOutput

from notedesk.agent.events import (
    PermissionRequestEvent,
    ReplyLifecycleEvent,
    TaskSnapshotEvent,
    TextDeltaEvent,
)
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


class PermissionRuntime(AcceptanceRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.approved = asyncio.Event()

    async def run_once(self, prompt: str):
        self.submitted.append(prompt)
        await self.ui_queue.put(
            PermissionRequestEvent(
                tool_name="Bash",
                summary="Permission required for tool action",
                details="command: gh pr view https://github.com/apache/seatunnel/pull/11841",
            )
        )
        await self.approved.wait()
        await self.ui_queue.put(TextDeltaEvent(delta="approved result"))
        await self.ui_queue.put(
            ReplyLifecycleEvent(
                phase="end",
                reply_id="r1",
                finished_reason="exceed_max_iters",
            )
        )
        return None

    async def resume_permission(self, approved: bool):
        if approved:
            self.approved.set()


class FailingPermissionRuntime(AcceptanceRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.blocked = asyncio.Event()

    async def run_once(self, prompt: str):
        self.submitted.append(prompt)
        await self.ui_queue.put(
            PermissionRequestEvent(
                tool_name="Bash",
                summary="Permission required for tool action",
                details="command: gh pr view https://github.com/apache/seatunnel/pull/11841",
            )
        )
        await self.blocked.wait()

    async def resume_permission(self, approved: bool):
        raise RuntimeError("stream connection lost")


class ScreenshotSizedOutput(DummyOutput):
    """Approximate the rows and columns of the reported terminal screenshot."""

    def get_size(self) -> Size:
        return Size(rows=27, columns=200)

    def get_rows_below_cursor_position(self) -> int:
        return 27


def _rendered_screen_text(harness: TUIHarness) -> str:
    screen = harness.application.renderer.last_rendered_screen
    return "\n".join(
        "".join(cell.char for cell in row.values())
        for row in screen.data_buffer.values()
    )


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


def test_tui_harness_drives_claude_style_permission_selection(tmp_path: Path) -> None:
    async def scenario() -> None:
        runtime = PermissionRuntime()
        harness = TUIHarness(NoteDeskTUI(tmp_path, tmp_path / "artifacts"), runtime)
        await harness.start()
        try:
            await harness.type_text("Read the PR")
            await harness.press("enter")
            await harness.wait_until(
                lambda: harness.status() == "Waiting for permission"
            )
            assert "Bash command" not in harness.transcript()
            assert "❯ 1. Yes, proceed" in harness.tui.render_permission_prompt_text()
            assert harness.tui.input_field.buffer.read_only()
            await harness.wait_until(
                lambda: "Bash command" in _rendered_screen_text(harness)
            )
            pending_frame = _rendered_screen_text(harness)
            assert "Bash command" in pending_frame
            assert "Enter to select · ↑/↓ to navigate · Esc to cancel" in pending_frame
            assert "Waiting for permission · Tasks closed · Enter send" not in pending_frame

            await harness.press("down")
            await harness.wait_until(
                lambda: "❯ 2. No, deny" in harness.tui.render_permission_prompt_text()
            )
            await harness.press("up")
            await harness.wait_until(
                lambda: "❯ 1. Yes, proceed" in harness.tui.render_permission_prompt_text()
            )
            await harness.press("enter")
            await harness.wait_until(lambda: "approved result" in harness.transcript())
            assert harness.tui.pending_permission is None
            assert harness.tui.render_permission_prompt_text() == ""
            assert not harness.tui.input_field.buffer.read_only()
            assert "> " in _rendered_screen_text(harness)
            assert harness.status() == "Stopped: max iterations reached"
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_keeps_application_alive_after_permission_resume_failure(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        runtime = FailingPermissionRuntime()
        harness = TUIHarness(NoteDeskTUI(tmp_path, tmp_path / "artifacts"), runtime)
        await harness.start()
        try:
            await harness.type_text("Read the PR")
            await harness.press("enter")
            await harness.wait_until(
                lambda: harness.status() == "Waiting for permission"
            )

            await harness.press("ctrl-y")
            await harness.wait_until(
                lambda: harness.status() == "Error: stream connection lost"
            )
            assert not harness.tui.input_field.buffer.read_only()
            assert not harness._run_task.done()
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_shows_wrapped_final_paragraph_at_transcript_bottom(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
        harness = TUIHarness(
            tui,
            AcceptanceRuntime(),
            output=ScreenshotSizedOutput(),
        )
        final_marker = "FINAL-MARKER"
        final_paragraph = (
            f"{final_marker} 本地无 Flink CDC 仓库与 Maven 制品（CDC 在独立仓库），"
            "故 CDC 侧细节基于既有笔记与官方文档；Flink 侧框架契约已逐文件核对源码。"
            "若需要，我可以补一份可编译的最小 Demo 工程（Java 8 + Maven 已就绪）。"
        )
        reply = "\n\n".join(
            [f"{index}. 前置内容用于填充视口。" for index in range(23)]
            + ["## 说明", "", final_paragraph]
        )

        await harness.start()
        try:
            tui.append_transcript_delta(reply)
            await harness.wait_until(
                lambda: final_marker in harness.transcript()
            )
            await asyncio.sleep(0.02)

            assert final_marker in _rendered_screen_text(harness)
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
        harness = TUIHarness(tui, AcceptanceRuntime())
        await harness.start()
        try:
            tui.append_transcript("\n".join(f"line {index}" for index in range(100)))
            await harness.wait_until(
                lambda: (
                    tui._transcript_scroll_pane is not None
                    and tui._transcript_scroll_pane.vertical_scroll > 0
                )
            )

            for _ in range(10):
                await harness.press("page-up")

            await harness.wait_until(
                lambda: (
                    tui._transcript_scroll_pane is not None
                    and tui._transcript_scroll_pane.vertical_scroll == 0
                )
            )
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_expands_transcript_after_conversation_starts(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
        harness = TUIHarness(tui, AcceptanceRuntime())
        await harness.start()
        try:
            initial = tui.transcript_field.window.render_info
            assert initial is not None
            initial_height = initial.window_height

            tui.append_transcript("\n".join(f"line {index}" for index in range(100)))

            await harness.wait_until(
                lambda: (
                    tui.transcript_field.window.render_info is not None
                    and tui.transcript_field.window.render_info.window_height
                    > initial_height
                )
            )
        finally:
            await harness.stop()

    asyncio.run(scenario())


def test_tui_harness_scrolls_shared_transcript_with_mouse_wheel(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        tui = NoteDeskTUI(tmp_path, tmp_path / "artifacts")
        harness = TUIHarness(tui, AcceptanceRuntime())
        await harness.start()
        try:
            tui.append_transcript("\n".join(f"line {index}" for index in range(100)))
            await harness.wait_until(
                lambda: (
                    tui._transcript_scroll_pane is not None
                    and tui._transcript_scroll_pane.vertical_scroll > 0
                )
            )
            initial_scroll = tui._transcript_scroll_pane.vertical_scroll

            for _ in range(5):
                await harness.send_terminal_sequence("\x1b[<64;10;20M")

            await harness.wait_until(
                lambda: (
                    tui._transcript_scroll_pane is not None
                    and tui._transcript_scroll_pane.vertical_scroll < initial_scroll
                )
            )
        finally:
            await harness.stop()

    asyncio.run(scenario())
