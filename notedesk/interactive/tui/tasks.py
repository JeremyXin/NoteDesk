from __future__ import annotations

from pydantic import BaseModel, Field

from notedesk.agent.middleware import TaskSnapshot


class TaskRowViewModel(BaseModel):
    id: str
    subject: str
    status_icon: str
    status_label: str


class TaskViewModel(BaseModel):
    rows: list[TaskRowViewModel] = Field(default_factory=list)
    total_count: int = 0
    completed_count: int = 0

    @classmethod
    def from_snapshot(cls, snapshot: TaskSnapshot) -> "TaskViewModel":
        rows = [
            TaskRowViewModel(
                id=task.id,
                subject=task.subject,
                status_icon=_status_icon(task.state),
                status_label=_status_label(task.state),
            )
            for task in snapshot.tasks
        ]
        completed = sum(1 for task in snapshot.tasks if task.state == "completed")
        return cls(
            rows=rows,
            total_count=len(snapshot.tasks),
            completed_count=completed,
        )


def _status_icon(state: str) -> str:
    return {
        "pending": "○",
        "in_progress": "◔",
        "completed": "●",
    }.get(state, "?")


def _status_label(state: str) -> str:
    return {
        "pending": "pending",
        "in_progress": "in progress",
        "completed": "completed",
    }.get(state, f"unknown: {state}")
