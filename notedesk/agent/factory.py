from __future__ import annotations

from pathlib import Path

from agentscope.agent import Agent, InjectionConfig, ReActConfig
from agentscope.state import AgentState
from agentscope.tool import Bash, LocalBackend, TaskCreate, TaskGet, TaskList, TaskUpdate, Toolkit

from notedesk.agent.permissions import build_permission_engine
from notedesk.agent.prompts import default_system_prompt
from notedesk.config.models import AppSettings
from notedesk.model.config import ModelRoleMap
from notedesk.model.factory import ModelFactory
from notedesk.skills.discovery import discover_skill_catalog
from notedesk.skills.resolver import resolve_skill_loaders

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


def build_agent_session(settings: AppSettings, role_map: ModelRoleMap) -> Agent:
    model_factory = ModelFactory(role_map)
    catalog = discover_skill_catalog([root.resolved_path for root in settings.skill_roots])
    toolkit = build_session_toolkit(
        session_cwd=settings.workspace,
        skill_directories=resolve_skill_loaders(catalog),
    )
    state = AgentState()
    state.permission_context = build_permission_engine(
        workspace=settings.workspace,
        interactive=settings.permissions.mode.value == "accept_edits",
    ).context
    return Agent(
        name="notedesk",
        system_prompt=default_system_prompt(),
        model=model_factory.resolve("agent"),
        toolkit=toolkit,
        state=state,
        react_config=ReActConfig(max_iters=8),
        injection_config=InjectionConfig(timezone="Asia/Shanghai"),
    )
