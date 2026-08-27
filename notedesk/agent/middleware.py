from __future__ import annotations

import asyncio

from agentscope.state import AgentState
from pydantic import BaseModel, Field


class TaskSnapshotItem(BaseModel):
    id: str
    subject: str
    description: str
    state: str
    owner: str | None
    metadata: dict = Field(default_factory=dict)


class TaskSnapshot(BaseModel):
    tasks: list[TaskSnapshotItem] = Field(default_factory=list)


def build_task_snapshot(state: AgentState) -> TaskSnapshot:
    return TaskSnapshot(
        tasks=[
            TaskSnapshotItem(
                id=task.id,
                subject=task.subject,
                description=task.description,
                state=task.state,
                owner=task.owner,
                metadata=dict(task.metadata),
            )
            for task in state.tasks_context.tasks
        ]
    )


async def publish_task_snapshot(
    queue: asyncio.Queue,
    state: AgentState,
) -> None:
    await queue.put(build_task_snapshot(state))
