from notedesk.agent.middleware import TaskSnapshot, TaskSnapshotItem
from notedesk.interactive.tui.tasks import TaskViewModel


def test_task_view_model_projects_rows_and_progress() -> None:
    snapshot = TaskSnapshot(
        tasks=[
            TaskSnapshotItem(
                id="task-1",
                subject="Collect tweets",
                description="Fetch timeline entries",
                state="pending",
                owner=None,
                metadata={},
            ),
            TaskSnapshotItem(
                id="task-2",
                subject="Draft summary",
                description="Write markdown",
                state="completed",
                owner="agent",
                metadata={},
            ),
        ]
    )

    view = TaskViewModel.from_snapshot(snapshot)

    assert view.completed_count == 1
    assert view.total_count == 2
    assert view.rows[0].status_icon == "○"
    assert view.rows[1].status_icon == "●"


def test_task_view_model_degrades_unknown_state_safely() -> None:
    snapshot = TaskSnapshot(
        tasks=[
            TaskSnapshotItem(
                id="task-1",
                subject="Unexpected",
                description="Unknown state",
                state="deleted",
                owner=None,
                metadata={},
            )
        ]
    )

    view = TaskViewModel.from_snapshot(snapshot)

    assert view.rows[0].status_icon == "?"
    assert "deleted" in view.rows[0].status_label
