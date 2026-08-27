import asyncio
from dataclasses import dataclass

from agentscope.agent import Agent
from agentscope.credential import DeepSeekCredential
from agentscope.formatter import FormatterBase
from agentscope.message import TextBlock, UserMsg
from agentscope.model import ChatModelBase, ChatResponse

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

    async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
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
