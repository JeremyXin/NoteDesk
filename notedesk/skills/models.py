from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


SkillStatus = Literal["active", "shadowed", "invalid"]


class SkillCatalogEntry(BaseModel):
    name: str | None = None
    description: str | None = None
    status: SkillStatus
    path: Path
    content_hash: str
    diagnostic: str = ""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SkillCatalog(BaseModel):
    entries: list[SkillCatalogEntry]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def active_directories(self) -> list[Path]:
        return [entry.path for entry in self.entries if entry.status == "active"]
