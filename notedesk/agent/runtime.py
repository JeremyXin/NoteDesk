from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Callable

from agentscope.agent import Agent
from agentscope.event import ConfirmResult, RequireUserConfirmEvent, UserConfirmResultEvent, UserInterruptEvent
from agentscope.message import Msg, TextBlock, UserMsg
from agentscope.state import AgentState, Task

from notedesk.agent.events import map_agent_event
from notedesk.agent.factory import build_agent_session
from notedesk.agent.middleware import publish_task_snapshot
from notedesk.artifacts.markdown import ArtifactValidationError, save_markdown_artifact
from notedesk.artifacts.models import ArtifactReceipt
from notedesk.config.models import AppSettings
from notedesk.model.config import ModelRoleMap, NamedModelConfig, Provider


class RuntimeFailure(RuntimeError):
    pass


def build_default_role_map(settings: AppSettings) -> ModelRoleMap:
    return ModelRoleMap(
        models={
            "default": NamedModelConfig(
                provider=Provider.DEEPSEEK,
                model=settings.deepseek.model,
                api_key=settings.deepseek.api_key,
                api_key_env=settings.deepseek.api_key_env,
                base_url=settings.deepseek.base_url,
                temperature=0.2,
                max_tokens=1200,
                retry=1,
                context_size=32768,
            )
        },
        roles={"agent": "default", "generator": "default"},
    )


class AgentSessionRuntime:
    def __init__(
        self,
        agent: Agent,
        ui_queue: asyncio.Queue,
        artifact_path: Path | None = None,
    ) -> None:
        self.agent = agent
        self.ui_queue = ui_queue
        self.artifact_path = artifact_path
        self.pending_permission_event: RequireUserConfirmEvent | None = None

    async def run_once(self, prompt: str):
        self.pending_permission_event = None
        return await self._consume_reply_stream(UserMsg(name="user", content=prompt))

    async def resume_permission(self, approved: bool):
        if self.pending_permission_event is None:
            return None
        pending = self.pending_permission_event
        self.pending_permission_event = None
        confirm_results = [
            ConfirmResult(
                confirmed=approved,
                tool_call=tool_call,
            )
            for tool_call in pending.tool_calls
        ]
        return await self._consume_reply_stream(
            UserConfirmResultEvent(
                reply_id=pending.reply_id,
                confirm_results=confirm_results,
            )
        )

    async def cancel(self):
        if self.pending_permission_event is None:
            return None
        pending = self.pending_permission_event
        self.pending_permission_event = None
        return await self._consume_reply_stream(
            UserInterruptEvent(reply_id=pending.reply_id)
        )

    async def _consume_reply_stream(self, input_event):
        final_msg: Msg | None = None

        async for chunk in self.agent.reply_stream(
            input_event,
            yield_final_msg=True,
        ):
            if isinstance(chunk, RequireUserConfirmEvent):
                self.pending_permission_event = chunk
            mapped = map_agent_event(chunk)
            if mapped is not None:
                await self.ui_queue.put(mapped)
            await publish_task_snapshot(self.ui_queue, self.agent.state)
            if isinstance(chunk, Msg):
                final_msg = chunk

        if self.artifact_path is None or final_msg is None:
            return None

        markdown = _extract_text(final_msg).strip()
        if not markdown:
            return None

        try:
            receipt = save_markdown_artifact(
                output_path=self.artifact_path,
                markdown=markdown,
                sources=["agentscope:reply_stream"],
            )
            await self.ui_queue.put(receipt)
            return receipt
        except ArtifactValidationError:
            return None


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


def _extract_text(message: Msg) -> str:
    if isinstance(message.content, str):
        return message.content
    return "".join(
        block.text for block in message.content if isinstance(block, TextBlock)
    )


async def run_live_smoke(
    settings: AppSettings,
    artifact_path: Path,
    ui_queue: asyncio.Queue,
    twitter_command: list[str],
    summary_prompt: str,
):
    tweets = _run_twitter_command(twitter_command)
    role_map = build_default_role_map(settings)
    agent = build_agent_session(settings=settings, role_map=role_map)
    runtime = AgentSessionRuntime(
        agent=agent,
        ui_queue=ui_queue,
        artifact_path=artifact_path,
    )
    prompt = (
        f"{summary_prompt}\n\n"
        "Summarize the following Twitter timeline into concise markdown.\n\n"
        f"```text\n{tweets}\n```"
    )
    receipt = await runtime.run_once(prompt)
    if receipt is None:
        raise RuntimeFailure("Live smoke did not produce a markdown artifact")
    return receipt


def _run_twitter_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeFailure(
            f"Twitter CLI failed with code {result.returncode}: "
            f"{_sanitize_diagnostic(result.stderr.strip())}"
        )
    return result.stdout.strip()


def _sanitize_diagnostic(text: str) -> str:
    sanitized = text
    patterns = [
        (r"token=[^\s]+", "token=[redacted]"),
        (r"cookie=[^\s]+", "cookie=[redacted]"),
        (r"authorization:\s*bearer\s+[^\s]+", "authorization: bearer [redacted]"),
    ]
    import re

    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    return sanitized
