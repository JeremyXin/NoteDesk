from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class ArtifactReceipt(BaseModel):
    path: Path
    bytes_written: int
    sources: list[str]
