from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PermissionMode(str, Enum):
    ACCEPT_EDITS = "accept_edits"
    DONT_ASK = "dont_ask"
    BYPASS = "bypass"


class DeepSeekSettings(BaseModel):
    model: str
    api_key: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None

    @model_validator(mode="after")
    def validate_auth(self) -> "DeepSeekSettings":
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if self.api_key is not None and not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if self.api_key_env is not None and not self.api_key_env.strip():
            raise ValueError("api_key_env must not be empty")
        if not self.api_key and not self.api_key_env:
            raise ValueError("either api_key or api_key_env must be configured")
        return self


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
