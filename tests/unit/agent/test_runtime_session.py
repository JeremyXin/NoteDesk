import asyncio

from agentscope.agent import Agent
from agentscope.event import (
    ReplyEndEvent,
    RequireUserConfirmEvent,
    TextBlockDeltaEvent,
)
from agentscope.credential import DeepSeekCredential
from agentscope.formatter import FormatterBase
from agentscope.message import Msg, TextBlock, ToolCallBlock, ToolCallState
from agentscope.model import ChatModelBase, ChatResponse, ChatUsage
from agentscope.state import AgentState
from agentscope.types import ReplyFinishedReason

from notedesk.agent.factory import build_session_toolkit
from notedesk.agent.runtime import AgentSessionRuntime


class DummyFormatter(FormatterBase):
    async def format(self, *args, **kwargs):
        return []


class FakeStreamingModel(ChatModelBase):
    class Parameters(ChatModelBase.Parameters):
        pass

    def __init__(self) -> None:
        super().__init__(
            credential=DeepSeekCredential(api_key="fake", base_url="https://example.com"),
            model="fake-model",
            parameters=self.Parameters(),
            stream=True,
            max_retries=0,
            context_size=4096,
        )
        self.formatter = DummyFormatter()
        self.calls = 0

    async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
        self.calls += 1
        async def _stream():
            yield ChatResponse(content=[TextBlock(text="# Summary")], is_last=False)
            yield ChatResponse(content=[TextBlock(text="\n\n- Hello world")], is_last=False)
            yield ChatResponse(content=[TextBlock(text="# Summary\n\n- Hello world")], is_last=True)

        return _stream()


def test_agent_session_runtime_runs_real_reply_stream_and_persists_artifact(tmp_path) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    agent = Agent(
        name="notedesk",
        system_prompt="You are NoteDesk.",
        model=FakeStreamingModel(),
        toolkit=build_session_toolkit(tmp_path, []),
    )
    runtime = AgentSessionRuntime(
        agent=agent,
        ui_queue=queue,
        artifact_path=tmp_path / "reply.md",
    )

    receipt = asyncio.run(runtime.run_once("Summarize this"))

    assert receipt is not None
    assert receipt.path.exists()
    assert receipt.path.read_text() == "# Summary\n\n- Hello world"
    emitted = []
    while not queue.empty():
        emitted.append(queue.get_nowait())
    kinds = [event.kind for event in emitted if hasattr(event, "kind")]
    assert "reply_lifecycle" in kinds
    assert "text_delta" in kinds


def test_agent_session_runtime_emits_final_text_missing_from_partial_deltas(tmp_path) -> None:
    class PartialDeltaAgent:
        state = AgentState()

        async def reply_stream(self, input_event, yield_final_msg):
            yield TextBlockDeltaEvent(
                reply_id="reply-1",
                block_id="block-1",
                delta="# Summary",
            )
            yield Msg(
                name="notedesk",
                role="assistant",
                content=[TextBlock(text="# Summary\n\n- Complete result")],
            )

    queue: asyncio.Queue = asyncio.Queue()
    runtime = AgentSessionRuntime(
        agent=PartialDeltaAgent(),
        ui_queue=queue,
        artifact_path=tmp_path / "reply.md",
    )

    receipt = asyncio.run(runtime.run_once("Summarize this"))

    assert receipt is not None
    deltas = []
    while not queue.empty():
        event = queue.get_nowait()
        if getattr(event, "kind", None) == "text_delta":
            deltas.append(event.delta)
    assert "".join(deltas) == "# Summary\n\n- Complete result"


def test_agent_session_runtime_hides_framework_text_after_max_iterations(tmp_path) -> None:
    class PartialDeltaAgent:
        state = AgentState()

        async def reply_stream(self, input_event, yield_final_msg):
            yield TextBlockDeltaEvent(
                reply_id="reply-1",
                block_id="block-1",
                delta="## Need attention",
            )
            yield ReplyEndEvent(
                session_id="session-1",
                reply_id="reply-1",
                finished_reason=ReplyFinishedReason.EXCEED_MAX_ITERS,
            )
            yield Msg(
                name="notedesk",
                role="assistant",
                content=[TextBlock(text="## Need attention\n\n- Complete detail")],
                finished_reason=ReplyFinishedReason.EXCEED_MAX_ITERS,
            )

    queue: asyncio.Queue = asyncio.Queue()
    runtime = AgentSessionRuntime(
        agent=PartialDeltaAgent(),
        ui_queue=queue,
        artifact_path=tmp_path / "reply.md",
    )

    receipt = asyncio.run(runtime.run_once("Summarize this"))

    assert receipt is None
    deltas = []
    while not queue.empty():
        event = queue.get_nowait()
        if getattr(event, "kind", None) == "text_delta":
            deltas.append(event.delta)
    assert "".join(deltas) == "## Need attention"


def test_agent_session_runtime_hides_permission_waiting_placeholder(tmp_path) -> None:
    class WaitingAgent:
        state = AgentState()

        async def reply_stream(self, input_event, yield_final_msg):
            tool_call = ToolCallBlock(
                id="call-1",
                name="Bash",
                input='{"command":"twitter post \\"hello\\""}',
                state=ToolCallState.ASKING,
            )
            yield RequireUserConfirmEvent(reply_id="reply-1", tool_calls=[tool_call])
            yield Msg(
                name="notedesk",
                role="assistant",
                content=[
                    TextBlock(
                        text="I'm waiting for your permission or the external "
                        "execution to finish."
                    )
                ],
            )

    queue: asyncio.Queue = asyncio.Queue()
    runtime = AgentSessionRuntime(
        agent=WaitingAgent(),
        ui_queue=queue,
        artifact_path=tmp_path / "reply.md",
    )

    receipt = asyncio.run(runtime.run_once("Post an update"))

    assert receipt is None
    assert runtime.pending_permission_event is not None
    assert not [
        event
        for event in list(queue._queue)
        if getattr(event, "kind", None) == "text_delta"
    ]


def test_agent_session_runtime_continues_when_output_limit_is_reached(tmp_path) -> None:
    queue: asyncio.Queue = asyncio.Queue()

    class TruncatedThenCompletedModel(FakeStreamingModel):
        async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
            self.calls += 1

            async def _stream():
                if self.calls == 1:
                    yield ChatResponse(
                        content=[TextBlock(text="# Partial")],
                        is_last=True,
                        usage=ChatUsage(
                            input_tokens=10,
                            output_tokens=32_000,
                            time=0.1,
                        ),
                    )
                    return
                yield ChatResponse(
                    content=[TextBlock(text="\n\n# Continued")],
                    is_last=True,
                    usage=ChatUsage(
                        input_tokens=20,
                        output_tokens=10,
                        time=0.1,
                    ),
                )

            return _stream()

    model = TruncatedThenCompletedModel()
    agent = Agent(
        name="notedesk",
        system_prompt="You are NoteDesk.",
        model=model,
        toolkit=build_session_toolkit(tmp_path, []),
    )
    runtime = AgentSessionRuntime(
        agent=agent,
        ui_queue=queue,
        artifact_path=tmp_path / "reply.md",
    )

    receipt = asyncio.run(runtime.run_once("Write a long answer"))

    assert model.calls == 2
    assert receipt is not None
    assert receipt.path.read_text() == "# Partial\n\n# Continued"


def test_agent_session_runtime_skips_artifact_when_no_text_output(tmp_path) -> None:
    queue: asyncio.Queue = asyncio.Queue()

    class EmptyModel(FakeStreamingModel):
        async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
            async def _stream():
                yield ChatResponse(content=[], is_last=True)

            return _stream()

    agent = Agent(
        name="notedesk",
        system_prompt="You are NoteDesk.",
        model=EmptyModel(),
        toolkit=build_session_toolkit(tmp_path, []),
    )
    runtime = AgentSessionRuntime(
        agent=agent,
        ui_queue=queue,
        artifact_path=tmp_path / "reply.md",
    )

    receipt = asyncio.run(runtime.run_once("Summarize this"))

    assert receipt is None
    assert not (tmp_path / "reply.md").exists()


def test_agent_session_runtime_can_drive_native_task_tools(tmp_path) -> None:
    queue: asyncio.Queue = asyncio.Queue()

    class TaskPlanningModel(FakeStreamingModel):
        async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
            self.calls += 1

            async def _stream():
                if self.calls == 1:
                    yield ChatResponse(
                        content=[
                            ToolCallBlock(
                                id="tool-1",
                                name="TaskCreate",
                                input='{"subject":"Collect tweets","description":"Fetch timeline"}',
                            )
                        ],
                        is_last=True,
                    )
                elif self.calls == 2:
                    yield ChatResponse(
                        content=[
                            ToolCallBlock(
                                id="tool-2",
                                name="TaskUpdate",
                                input='{"task_id":"1","status":"completed"}',
                            )
                        ],
                        is_last=True,
                    )
                else:
                    yield ChatResponse(
                        content=[TextBlock(text="# Summary\n\n- Done")],
                        is_last=True,
                    )

            return _stream()

    agent = Agent(
        name="notedesk",
        system_prompt="You are NoteDesk.",
        model=TaskPlanningModel(),
        toolkit=build_session_toolkit(tmp_path, []),
    )
    runtime = AgentSessionRuntime(
        agent=agent,
        ui_queue=queue,
        artifact_path=tmp_path / "reply.md",
    )

    receipt = asyncio.run(runtime.run_once("Summarize this"))

    assert receipt is not None
    assert len(agent.state.tasks_context.tasks) == 1
    assert agent.state.tasks_context.tasks[0].subject == "Collect tweets"
    assert agent.state.tasks_context.tasks[0].state == "completed"


def test_agent_session_runtime_tracks_pending_permission_event(tmp_path) -> None:
    queue: asyncio.Queue = asyncio.Queue()

    class PermissionModel(FakeStreamingModel):
        async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
            async def _stream():
                yield ChatResponse(
                    content=[
                        ToolCallBlock(
                            id="tool-1",
                            name="Bash",
                            input='{"command":"twitter post \\"hello\\""}',
                        )
                    ],
                    is_last=True,
                )

            return _stream()

    agent = Agent(
        name="notedesk",
        system_prompt="You are NoteDesk.",
        model=PermissionModel(),
        toolkit=build_session_toolkit(tmp_path, []),
    )
    runtime = AgentSessionRuntime(
        agent=agent,
        ui_queue=queue,
        artifact_path=tmp_path / "reply.md",
    )

    receipt = asyncio.run(runtime.run_once("Summarize this"))

    assert receipt is None
    assert isinstance(runtime.pending_permission_event, RequireUserConfirmEvent)
