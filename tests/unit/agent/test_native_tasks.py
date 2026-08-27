import asyncio

from agentscope.state import AgentState, Task

from notedesk.agent.middleware import build_task_snapshot, publish_task_snapshot


def test_build_task_snapshot_reads_from_agentscope_tasks_context_only() -> None:
    state = AgentState()
    state.tasks_context.tasks.append(
        Task(
            id="task-1",
            subject="Collect tweets",
            description="Fetch timeline entries",
            metadata={"source": "twitter"},
            state="pending",
        )
    )

    snapshot = build_task_snapshot(state)

    assert [task.id for task in snapshot.tasks] == ["task-1"]
    assert snapshot.tasks[0].state == "pending"


def test_build_task_snapshot_is_immutable_copy() -> None:
    state = AgentState()
    state.tasks_context.tasks.append(
        Task(
            id="task-1",
            subject="Collect tweets",
            description="Fetch timeline entries",
            metadata={"source": "twitter"},
            state="in_progress",
        )
    )

    snapshot = build_task_snapshot(state)
    snapshot.tasks[0].state = "completed"

    assert state.tasks_context.tasks[0].state == "in_progress"


def test_publish_task_snapshot_enqueues_projection_without_mutating_state() -> None:
    state = AgentState()
    state.tasks_context.tasks.append(
        Task(
            id="task-1",
            subject="Write summary",
            description="Draft markdown",
            metadata={},
            state="completed",
        )
    )
    queue: asyncio.Queue = asyncio.Queue()

    asyncio.run(publish_task_snapshot(queue, state))
    snapshot = queue.get_nowait()

    assert snapshot.tasks[0].subject == "Write summary"
    assert state.tasks_context.tasks[0].state == "completed"
