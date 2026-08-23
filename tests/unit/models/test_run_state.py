import pytest
from pydantic import ValidationError

from notedesk.models.state import RunState, RunStatus


def test_run_state_tracks_pending_and_completed_steps() -> None:
    run_state = RunState(
        run_id="run-1",
        session_id="session-1",
        goal="Draft article",
        status=RunStatus.PENDING,
        pending_step_ids=["collect", "draft"],
        completed_step_ids=["normalize"],
    )

    assert run_state.status is RunStatus.PENDING
    assert run_state.pending_step_ids == ["collect", "draft"]


def test_run_state_rejects_duplicate_step_ids_across_status_lists() -> None:
    with pytest.raises(ValidationError):
        RunState(
            run_id="run-1",
            session_id="session-1",
            goal="Draft article",
            status=RunStatus.RUNNING,
            pending_step_ids=["draft"],
            completed_step_ids=["draft"],
        )
