from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PermissionMode(str, Enum):
    ACCEPT_EDITS = "accept_edits"
    DONT_ASK = "dont_ask"
    BYPASS = "bypass"


class DeepSeekSettings(BaseModel):
    model: str
    api_key_env: str
    base_url: str | None = None

    @field_validator("model", "api_key_env")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value


class SkillRootSettings(BaseModel):
    path: Path
    resolved_path: Path

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ArtifactSettings(BaseModel):
    root: Path

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PermissionSettings(BaseModel):
    mode: PermissionMode


class AppSettings(BaseModel):
    workspace: Path
    deepseek: DeepSeekSettings
    artifacts: ArtifactSettings
    permissions: PermissionSettings
    skill_roots: list[SkillRootSettings] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
