import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from notedesk.config.loader import load_settings
from notedesk.config.models import PermissionMode


def test_load_settings_resolves_workspace_relative_skill_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    relative_root = workspace / "skills"
    relative_root.mkdir(parents=True)
    (workspace / "artifacts").mkdir()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    config_path = workspace / "notedesk.toml"
    config_path.write_text(
        """
workspace = "."

[deepseek]
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = "artifacts"

[permissions]
mode = "accept_edits"

[[skill_roots]]
path = "skills"
""".strip()
    )

    settings = load_settings(config_path)

    assert settings.workspace == workspace.resolve()
    assert settings.skill_roots[0].resolved_path == relative_root.resolve()
    assert settings.permissions.mode is PermissionMode.ACCEPT_EDITS


def test_load_settings_requires_existing_workspace_relative_skill_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "artifacts").mkdir()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    config_path = workspace / "notedesk.toml"
    config_path.write_text(
        """
workspace = "."

[deepseek]
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = "artifacts"

[permissions]
mode = "dont_ask"

[[skill_roots]]
path = "missing-skills"
""".strip()
    )

    with pytest.raises(FileNotFoundError):
        load_settings(config_path)


def test_load_settings_rejects_unknown_permission_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    skill_root = workspace / "skills"
    skill_root.mkdir(parents=True)
    (workspace / "artifacts").mkdir()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    config_path = workspace / "notedesk.toml"
    config_path.write_text(
        """
workspace = "."

[deepseek]
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = "artifacts"

[permissions]
mode = "unsafe"

[[skill_roots]]
path = "skills"
""".strip()
    )

    with pytest.raises(ValidationError):
        load_settings(config_path)


def test_load_settings_requires_configured_api_key_env_to_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    skill_root = workspace / "skills"
    skill_root.mkdir(parents=True)
    (workspace / "artifacts").mkdir()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    config_path = workspace / "notedesk.toml"
    config_path.write_text(
        """
workspace = "."

[deepseek]
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = "artifacts"

[permissions]
mode = "accept_edits"

[[skill_roots]]
path = "skills"
""".strip()
    )

    with pytest.raises(EnvironmentError):
        load_settings(config_path)


def test_load_settings_rejects_relative_workspace_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")
    config_path = tmp_path / "notedesk.toml"
    config_path.write_text(
        """
workspace = "workspace"

[deepseek]
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = "artifacts"

[permissions]
mode = "accept_edits"
""".strip()
    )

    with pytest.raises(FileNotFoundError):
        load_settings(config_path)

