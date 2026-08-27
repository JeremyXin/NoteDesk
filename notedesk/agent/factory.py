from __future__ import annotations

from pathlib import Path

from agentscope.tool import Bash, LocalBackend, TaskCreate, TaskGet, TaskList, TaskUpdate, Toolkit


def build_session_toolkit(session_cwd: Path, skill_directories: list[str]) -> Toolkit:
    tools = [
        TaskCreate(),
        TaskGet(),
        TaskList(),
        TaskUpdate(),
        Bash(cwd=session_cwd, backend=LocalBackend()),
    ]
    return Toolkit(
        tools=tools,
        skills_or_loaders=skill_directories,
    )
