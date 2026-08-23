from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class RunState(BaseModel):
    run_id: str
    session_id: str
    goal: str
    status: RunStatus
    pending_step_ids: list[str] = Field(default_factory=list)
    completed_step_ids: list[str] = Field(default_factory=list)
    current_step_id: str | None = None
    failure_reason: str | None = None
    suspend_reason: str | None = None

    @model_validator(mode="after")
    def validate_step_membership(self) -> "RunState":
        duplicates = set(self.pending_step_ids).intersection(self.completed_step_ids)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"Steps cannot be both pending and completed: {duplicate_list}")
        return self
