from notedesk.models.state import RunState, RunStatus
from notedesk.storage.repositories import RunRepository
from notedesk.storage.schema import initialize_database


def test_run_repository_persists_and_loads_run_state(tmp_path) -> None:
    db_path = tmp_path / "notedesk.db"
    initialize_database(db_path)
    repository = RunRepository(db_path)
    run_state = RunState(
        run_id="run-1",
        session_id="session-1",
        goal="Write a learning plan",
        status=RunStatus.PENDING,
        pending_step_ids=["plan"],
    )

    repository.upsert(run_state)
    loaded = repository.get("run-1")

    assert loaded.run_id == "run-1"
    assert loaded.goal == "Write a learning plan"
    assert loaded.pending_step_ids == ["plan"]


def test_run_repository_updates_existing_run_status(tmp_path) -> None:
    db_path = tmp_path / "notedesk.db"
    initialize_database(db_path)
    repository = RunRepository(db_path)
    run_state = RunState(
        run_id="run-1",
        session_id="session-1",
        goal="Write a learning plan",
        status=RunStatus.PENDING,
    )

    repository.upsert(run_state)
    repository.upsert(run_state.model_copy(update={"status": RunStatus.ABORTED}))

    loaded = repository.get("run-1")
    assert loaded.status is RunStatus.ABORTED
