import asyncio
from pathlib import Path

import pytest
from agentscope.exception import ToolNotFoundError
from agentscope.tool import Bash, TaskCreate, TaskGet, TaskList, TaskUpdate

from notedesk.agent.factory import build_session_toolkit


def test_build_session_toolkit_registers_native_tools_and_skills(tmp_path: Path) -> None:
    skill_dir = tmp_path / "twitter-cli"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: twitter-cli\ndescription: Twitter access\n---\nUse the tool.\n"
    )

    toolkit = build_session_toolkit(
        session_cwd=tmp_path,
        skill_directories=[str(skill_dir)],
    )

    assert isinstance(asyncio.run(toolkit.get_tool("Bash")), Bash)
    assert isinstance(asyncio.run(toolkit.get_tool("TaskCreate")), TaskCreate)
    assert isinstance(asyncio.run(toolkit.get_tool("TaskGet")), TaskGet)
    assert isinstance(asyncio.run(toolkit.get_tool("TaskList")), TaskList)
    assert isinstance(asyncio.run(toolkit.get_tool("TaskUpdate")), TaskUpdate)

    instructions = asyncio.run(toolkit.get_skill_instructions())
    assert "twitter-cli" in instructions


def test_build_session_toolkit_unknown_tool_is_rejected(tmp_path: Path) -> None:
    toolkit = build_session_toolkit(session_cwd=tmp_path, skill_directories=[])

    with pytest.raises(ToolNotFoundError):
        asyncio.run(toolkit.check_tool_available("MissingTool", []))
