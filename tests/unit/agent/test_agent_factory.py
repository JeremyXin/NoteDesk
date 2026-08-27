from pathlib import Path

import pytest
from agentscope.agent import Agent

from notedesk.agent.factory import build_agent_session
from notedesk.config.models import (
    AppSettings,
    ArtifactSettings,
    DeepSeekSettings,
    PermissionMode,
    PermissionSettings,
    SkillRootSettings,
)
from notedesk.model.config import ModelRoleMap, NamedModelConfig, Provider


def test_build_agent_session_creates_agentscope_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")
    skills = tmp_path / "skills"
    skills.mkdir()
    settings = AppSettings(
        workspace=tmp_path,
        deepseek=DeepSeekSettings(
            model="deepseek-chat",
            api_key_env="DEEPSEEK_API_KEY",
        ),
        artifacts=ArtifactSettings(root=tmp_path / "artifacts"),
        permissions=PermissionSettings(mode=PermissionMode.ACCEPT_EDITS),
        skill_roots=[
            SkillRootSettings(path=skills, resolved_path=skills),
        ],
    )
    role_map = ModelRoleMap(
        models={
            "default": NamedModelConfig(
                provider=Provider.DEEPSEEK,
                model="deepseek-chat",
                api_key_env="DEEPSEEK_API_KEY",
            )
        },
        roles={"agent": "default", "generator": "default"},
    )

    agent = build_agent_session(
        settings=settings,
        role_map=role_map,
    )

    assert isinstance(agent, Agent)
    assert agent.name == "notedesk"
