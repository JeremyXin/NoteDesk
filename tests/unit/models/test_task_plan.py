import pytest
from pydantic import ValidationError

from notedesk.models.plan import PlanStep, TaskPlan


def test_task_plan_accepts_dependency_graph_for_declared_steps() -> None:
    plan = TaskPlan(
        plan_id="plan-1",
        goal="Create a research brief",
        user_request="Summarize topic X",
        expected_output="Markdown brief",
        steps=[
            PlanStep(step_id="collect", title="Collect sources"),
            PlanStep(step_id="summarize", title="Summarize sources"),
        ],
        dependencies={"summarize": ["collect"]},
    )

    assert plan.dependencies["summarize"] == ["collect"]
    assert [step.step_id for step in plan.steps] == ["collect", "summarize"]


def test_task_plan_rejects_unknown_dependency_targets() -> None:
    with pytest.raises(ValidationError):
        TaskPlan(
            plan_id="plan-2",
            goal="Create a research brief",
            user_request="Summarize topic X",
            expected_output="Markdown brief",
            steps=[PlanStep(step_id="collect", title="Collect sources")],
            dependencies={"collect": ["missing-step"]},
        )
