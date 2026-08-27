from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from agentscope.state import AgentState, Task

from notedesk.agent.middleware import publish_task_snapshot
from notedesk.artifacts.markdown import ArtifactValidationError, save_markdown_artifact


class RuntimeFailure(RuntimeError):
    pass


class CoreMVPRuntime:
    def __init__(self, artifact_path: Path, ui_queue: asyncio.Queue) -> None:
        self.artifact_path = artifact_path
        self.ui_queue = ui_queue
        self.state = AgentState()

    async def run_twitter_to_markdown(
        self,
        request: str,
        fetch_tweets: Callable[[], list[str]],
        generate_markdown: Callable[[list[str]], str],
    ):
        fetch_task = Task(
            subject="Fetch Twitter timeline",
            description=request,
            metadata={"provider": "twitter"},
            state="pending",
        )
        write_task = Task(
            subject="Write markdown artifact",
            description="Generate summary markdown",
            metadata={"artifact_path": str(self.artifact_path)},
            state="pending",
        )
        self.state.tasks_context.tasks = [fetch_task, write_task]
        await publish_task_snapshot(self.ui_queue, self.state)

        try:
            self.state.tasks_context.tasks[0].state = "in_progress"
            await publish_task_snapshot(self.ui_queue, self.state)
            tweets = fetch_tweets()
            self.state.tasks_context.tasks[0].state = "completed"

            self.state.tasks_context.tasks[1].state = "in_progress"
            await publish_task_snapshot(self.ui_queue, self.state)
            markdown = generate_markdown(tweets)
            receipt = save_markdown_artifact(
                output_path=self.artifact_path,
                markdown=markdown,
                sources=["twitter:timeline"],
            )
            self.state.tasks_context.tasks[1].state = "completed"
            await publish_task_snapshot(self.ui_queue, self.state)
            return receipt
        except (ArtifactValidationError, Exception) as exc:
            raise RuntimeFailure(str(exc)) from exc
