from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Provider(str, Enum):
    DEEPSEEK = "deepseek"


class NamedModelConfig(BaseModel):
    provider: Provider
    model: str
    api_key_env: str
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    retry: int = 0
    context_size: int | None = None
    thinking: bool = False
    fallback_model: str | None = None

    @model_validator(mode="after")
    def validate_values(self) -> "NamedModelConfig":
        if not self.api_key_env.strip():
            raise ValueError("api_key_env must not be empty")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.retry < 0:
            raise ValueError("retry must be >= 0")
        if self.context_size is not None and self.context_size <= 0:
            raise ValueError("context_size must be positive")
        return self


class ModelRoleMap(BaseModel):
    models: dict[str, NamedModelConfig] = Field(default_factory=dict)
    roles: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_role_references(self) -> "ModelRoleMap":
        for role_name in ("agent", "generator"):
            if role_name not in self.roles:
                raise ValueError(f"Missing required role mapping: {role_name}")

        unknown = [model_name for model_name in self.roles.values() if model_name not in self.models]
        if unknown:
            joined = ", ".join(sorted(set(unknown)))
            raise ValueError(f"Unknown model references: {joined}")
        return self

    def resolve_role(self, role_name: str) -> NamedModelConfig:
        try:
            model_name = self.roles[role_name]
        except KeyError as exc:
            raise KeyError(f"Unknown role: {role_name}") from exc
        return self.models[model_name]
