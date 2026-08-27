from __future__ import annotations

import os
import tomllib
from pathlib import Path

from notedesk.config.models import (
    AppSettings,
    ArtifactSettings,
    DeepSeekSettings,
    PermissionSettings,
    SkillRootSettings,
)

ROOT_CONFIG_PATH = Path("config.toml")
LEGACY_CONFIG_PATH = Path(".notedesk/config.toml")


def _resolve_workspace(config_path: Path, workspace_value: str | None) -> Path:
    workspace_hint = Path(workspace_value or ".")
    workspace = workspace_hint if workspace_hint.is_absolute() else (config_path.parent / workspace_hint)
    workspace = workspace.resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise FileNotFoundError(f"Workspace directory does not exist: {workspace}")
    return workspace


def _resolve_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (workspace / path).resolve()


def resolve_config_path(config_path: Path | None, cwd: Path | None = None) -> Path:
    if config_path is not None:
        return config_path

    base = cwd or Path.cwd()
    root_config = base / ROOT_CONFIG_PATH
    legacy_config = base / LEGACY_CONFIG_PATH
    if root_config.exists():
        return root_config
    if legacy_config.exists():
        return legacy_config
    return root_config


def load_settings(config_path: Path) -> AppSettings:
    raw = tomllib.loads(config_path.read_text())
    workspace = _resolve_workspace(config_path, raw.get("workspace"))

    deepseek = DeepSeekSettings.model_validate(raw["deepseek"])
    if not os.getenv(deepseek.api_key_env):
        raise EnvironmentError(f"Missing required environment variable: {deepseek.api_key_env}")

    artifacts_root = _resolve_path(workspace, raw["artifacts"]["root"])
    permissions = PermissionSettings.model_validate(raw["permissions"])

    skill_roots: list[SkillRootSettings] = []
    for root_entry in raw.get("skill_roots", []):
        resolved = _resolve_path(workspace, root_entry["path"])
        if not resolved.exists() or not resolved.is_dir():
            raise FileNotFoundError(f"Skill root does not exist: {resolved}")
        skill_roots.append(
            SkillRootSettings(
                path=Path(root_entry["path"]),
                resolved_path=resolved,
            )
        )

    return AppSettings(
        workspace=workspace,
        deepseek=deepseek,
        artifacts=ArtifactSettings(root=artifacts_root),
        permissions=permissions,
        skill_roots=skill_roots,
    )
