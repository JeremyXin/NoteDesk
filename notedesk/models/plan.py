from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class PlanStep(BaseModel):
    step_id: str
    title: str
    description: str | None = None


class TaskPlan(BaseModel):
    plan_id: str
    goal: str
    user_request: str
    expected_output: str
    steps: list[PlanStep] = Field(default_factory=list)
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_steps: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "TaskPlan":
        known_steps = {step.step_id for step in self.steps}

        for step_id, dependency_ids in self.dependencies.items():
            if step_id not in known_steps:
                raise ValueError(f"Dependency target '{step_id}' is not a declared step")
            missing = [dependency_id for dependency_id in dependency_ids if dependency_id not in known_steps]
            if missing:
                raise ValueError(
                    f"Step '{step_id}' depends on unknown steps: {', '.join(missing)}"
                )

        return self
