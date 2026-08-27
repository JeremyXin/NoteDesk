from pathlib import Path

from notedesk.skills.discovery import discover_skill_catalog
from notedesk.skills.resolver import resolve_skill_loaders


def test_resolve_skill_loaders_returns_active_skill_directories_in_priority_order(tmp_path: Path) -> None:
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    _write_skill(root_a, "twitter-cli", "twitter-cli", "Twitter")
    _write_skill(root_b, "writer", "writer", "Writer")
    _write_skill(root_b, "twitter-cli", "twitter-cli", "Shadowed")

    catalog = discover_skill_catalog([root_a, root_b])

    loaders = resolve_skill_loaders(catalog)

    assert loaders == [str(root_a / "twitter-cli"), str(root_b / "writer")]


def _write_skill(root: Path, directory: str, name: str, description: str) -> None:
    skill_dir = root / directory
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n"
    )
