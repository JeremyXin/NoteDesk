from __future__ import annotations

from notedesk.skills.models import SkillCatalog


def resolve_skill_loaders(catalog: SkillCatalog) -> list[str]:
    return [str(path) for path in catalog.active_directories()]
