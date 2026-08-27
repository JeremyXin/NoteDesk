from agentscope.event import (
    ReplyEndEvent,
    ReplyStartEvent,
    RequireUserConfirmEvent,
    TextBlockDeltaEvent,
    ToolCallStartEvent,
    ToolResultEndEvent,
    ToolResultStartEvent,
)
from agentscope.message import ToolCallBlock, ToolCallState, ToolResultState

from notedesk.agent.events import (
    PermissionRequestEvent,
    ReplyLifecycleEvent,
    TaskSnapshotEvent,
    TextDeltaEvent,
    ToolLifecycleEvent,
    map_agent_event,
)
from notedesk.agent.middleware import TaskSnapshot, TaskSnapshotItem


def test_map_agent_event_projects_text_delta() -> None:
    event = TextBlockDeltaEvent(reply_id="reply-1", block_id="block-1", delta="hello")

    mapped = map_agent_event(event)

    assert isinstance(mapped, TextDeltaEvent)
    assert mapped.delta == "hello"


def test_map_agent_event_projects_tool_lifecycle_without_arguments() -> None:
    start = ToolCallStartEvent(
        reply_id="reply-1",
        tool_call_id="call-1",
        tool_call_name="Bash",
    )
    result = ToolResultStartEvent(
        reply_id="reply-1",
        tool_call_id="call-1",
        tool_call_name="Bash",
    )
    end = ToolResultEndEvent(
        reply_id="reply-1",
        tool_call_id="call-1",
        state=ToolResultState.SUCCESS,
        metadata={"stdout": "secret output"},
    )

    mapped_start = map_agent_event(start)
    mapped_result = map_agent_event(result)
    mapped_end = map_agent_event(end)

    assert isinstance(mapped_start, ToolLifecycleEvent)
    assert mapped_start.phase == "call_start"
    assert mapped_start.summary == "Running tool"
    assert "secret" not in mapped_start.model_dump_json()

    assert isinstance(mapped_result, ToolLifecycleEvent)
    assert mapped_result.phase == "result_start"

    assert isinstance(mapped_end, ToolLifecycleEvent)
    assert mapped_end.phase == "result_end"
    assert mapped_end.status == "success"
    assert "secret" not in mapped_end.model_dump_json()


def test_map_agent_event_projects_permission_request_as_semantic_summary() -> None:
    event = RequireUserConfirmEvent(
        reply_id="reply-1",
        tool_calls=[
            ToolCallBlock(
                id="call-1",
                name="Bash",
                input='{"command":"twitter post \\"hello\\""}',
                state=ToolCallState.ASKING,
            )
        ],
    )

    mapped = map_agent_event(event)

    assert isinstance(mapped, PermissionRequestEvent)
    assert mapped.tool_name == "Bash"
    assert mapped.summary == "Permission required for tool action"
    assert "twitter post" not in mapped.model_dump_json()


def test_map_agent_event_projects_reply_lifecycle() -> None:
    start = ReplyStartEvent(session_id="session-1", reply_id="reply-1", name="NoteDesk")
    end = ReplyEndEvent(session_id="session-1", reply_id="reply-1")

    mapped_start = map_agent_event(start)
    mapped_end = map_agent_event(end)

    assert isinstance(mapped_start, ReplyLifecycleEvent)
    assert mapped_start.phase == "start"
    assert isinstance(mapped_end, ReplyLifecycleEvent)
    assert mapped_end.phase == "end"


def test_map_agent_event_accepts_task_snapshot_side_channel() -> None:
    snapshot = TaskSnapshot(
        tasks=[
            TaskSnapshotItem(
                id="task-1",
                subject="Collect tweets",
                description="Fetch timeline",
                state="pending",
                owner=None,
                metadata={},
            )
        ]
    )

    mapped = map_agent_event(snapshot)

    assert isinstance(mapped, TaskSnapshotEvent)
    assert mapped.snapshot.tasks[0].id == "task-1"
