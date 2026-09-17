from __future__ import annotations

import json
from typing import Literal

from agentscope.event import (
    ReplyEndEvent,
    ReplyStartEvent,
    RequireUserConfirmEvent,
    TextBlockDeltaEvent,
    ToolCallStartEvent,
    ToolResultEndEvent,
    ToolResultStartEvent,
)
from agentscope.message import ToolResultState
from pydantic import BaseModel

from notedesk.agent.middleware import TaskSnapshot


class TextDeltaEvent(BaseModel):
    kind: Literal["text_delta"] = "text_delta"
    delta: str


class ToolLifecycleEvent(BaseModel):
    kind: Literal["tool_lifecycle"] = "tool_lifecycle"
    phase: Literal["call_start", "result_start", "result_end"]
    tool_name: str
    status: str | None = None
    summary: str


class PermissionRequestEvent(BaseModel):
    kind: Literal["permission_request"] = "permission_request"
    tool_name: str
    summary: str
    details: str | None = None


class ReplyLifecycleEvent(BaseModel):
    kind: Literal["reply_lifecycle"] = "reply_lifecycle"
    phase: Literal["start", "end"]
    reply_id: str
    finished_reason: str | None = None


class TaskSnapshotEvent(BaseModel):
    kind: Literal["task_snapshot"] = "task_snapshot"
    snapshot: TaskSnapshot


NoteDeskEvent = (
    TextDeltaEvent
    | ToolLifecycleEvent
    | PermissionRequestEvent
    | ReplyLifecycleEvent
    | TaskSnapshotEvent
    | None
)


def map_agent_event(event: object) -> NoteDeskEvent:
    if isinstance(event, TaskSnapshot):
        return TaskSnapshotEvent(snapshot=event)
    if isinstance(event, TextBlockDeltaEvent):
        return TextDeltaEvent(delta=event.delta)
    if isinstance(event, ReplyStartEvent):
        return ReplyLifecycleEvent(phase="start", reply_id=event.reply_id)
    if isinstance(event, ReplyEndEvent):
        reason = getattr(event, "finished_reason", None)
        return ReplyLifecycleEvent(
            phase="end",
            reply_id=event.reply_id,
            finished_reason=(
                getattr(reason, "value", reason) if reason is not None else None
            ),
        )
    if isinstance(event, ToolCallStartEvent):
        return ToolLifecycleEvent(
            phase="call_start",
            tool_name=event.tool_call_name,
            summary="Running tool",
        )
    if isinstance(event, ToolResultStartEvent):
        return ToolLifecycleEvent(
            phase="result_start",
            tool_name=event.tool_call_name,
            summary="Receiving tool result",
        )
    if isinstance(event, ToolResultEndEvent):
        return ToolLifecycleEvent(
            phase="result_end",
            tool_name="tool",
            status=_tool_result_status(event.state),
            summary="Tool finished",
        )
    if isinstance(event, RequireUserConfirmEvent):
        tool_call = event.tool_calls[0] if event.tool_calls else None
        tool_name = tool_call.name if tool_call else "tool"
        return PermissionRequestEvent(
            tool_name=tool_name,
            summary="Permission required for tool action",
            details=_permission_details(tool_call),
        )
    return None


def _tool_result_status(state: ToolResultState) -> str:
    return str(state.value if hasattr(state, "value") else state).lower()


def _permission_details(tool_call: object | None) -> str | None:
    """Extract a concise, human-readable operation for the approval panel."""
    if tool_call is None:
        return None
    raw_input = getattr(tool_call, "input", None)
    if not isinstance(raw_input, str) or not raw_input.strip():
        return None
    try:
        parsed = json.loads(raw_input)
    except json.JSONDecodeError:
        return " ".join(raw_input.split())[:240]
    if isinstance(parsed, dict):
        for key in ("command", "path", "description"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return f"{key}: {' '.join(value.split())}"[:240]
    return " ".join(raw_input.split())[:240]
