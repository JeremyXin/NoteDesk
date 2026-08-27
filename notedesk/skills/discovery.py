from __future__ import annotations

import hashlib
from pathlib import Path

from notedesk.skills.models import SkillCatalog, SkillCatalogEntry


def discover_skill_catalog(roots: list[Path]) -> SkillCatalog:
    entries: list[SkillCatalogEntry] = []
    active_names: set[str] = set()

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue

        for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            try:
                metadata = _read_frontmatter(skill_md)
            except ValueError as exc:
                entries.append(
                    SkillCatalogEntry(
                        status="invalid",
                        path=skill_dir,
                        content_hash=_hash_text(skill_md.read_text()),
                        diagnostic=str(exc),
                    )
                )
                continue

            name = metadata.get("name")
            description = metadata.get("description")
            if not name or not description:
                entries.append(
                    SkillCatalogEntry(
                        name=name,
                        description=description,
                        status="invalid",
                        path=skill_dir,
                        content_hash=_hash_text(skill_md.read_text()),
                        diagnostic="Missing required frontmatter field: name or description",
                    )
                )
                continue

            status = "shadowed" if name in active_names else "active"
            if status == "active":
                active_names.add(name)

            entries.append(
                SkillCatalogEntry(
                    name=name,
                    description=description,
                    status=status,
                    path=skill_dir,
                    content_hash=_hash_text(skill_md.read_text()),
                    diagnostic="" if status == "active" else "Shadowed by higher-priority root",
                )
            )

    return SkillCatalog(entries=entries)


def _read_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text()
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ValueError("Invalid frontmatter: missing opening marker")

    metadata: dict[str, str] = {}
    end_index = None
    for index in range(1, len(lines)):
        line = lines[index].strip()
        if line == "---":
            end_index = index
            break
        if ":" not in line:
            raise ValueError("Invalid frontmatter: expected key: value pairs")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    if end_index is None:
        raise ValueError("Invalid frontmatter: missing closing marker")
    return metadata


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
