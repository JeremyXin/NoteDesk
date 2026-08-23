from __future__ import annotations

from pydantic import BaseModel, Field


class RetryPolicy(BaseModel):
    max_attempts: int = Field(ge=1)
    backoff_seconds: float = Field(default=0.0, ge=0.0)


class CapabilityDescriptor(BaseModel):
    capability_id: str
    kind: str
    description: str
    retry_policy: RetryPolicy
    enabled: bool = True
    permission_mode: str = "auto"
    side_effect_level: str = "none"
