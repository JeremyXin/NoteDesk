from pathlib import Path

from notedesk.skills.discovery import discover_skill_catalog


def test_discover_skill_catalog_marks_shadowed_roots_by_config_order(tmp_path: Path) -> None:
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    _write_skill(root_a, "twitter-cli", "twitter-cli", "Use twitter")
    _write_skill(root_b, "twitter-cli", "twitter-cli", "Use override")

    catalog = discover_skill_catalog([root_a, root_b])

    assert [entry.status for entry in catalog.entries] == ["active", "shadowed"]
    assert catalog.active_directories() == [root_a / "twitter-cli"]


def test_discover_skill_catalog_only_scans_root_skill_directory_shape(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _write_skill(root, "writer", "Writer", "Write content")
    nested = root / "nested" / "deeper"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\nname: ignored\ndescription: ignored\n---\nIgnored")

    catalog = discover_skill_catalog([root])

    assert [entry.name for entry in catalog.entries] == ["Writer"]


def test_discover_skill_catalog_marks_missing_frontmatter_as_invalid(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill_dir = root / "broken"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Missing frontmatter")

    catalog = discover_skill_catalog([root])

    assert catalog.entries[0].status == "invalid"
    assert "frontmatter" in catalog.entries[0].diagnostic.lower()


def test_discover_skill_catalog_records_metadata_hash_for_active_skill(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _write_skill(root, "outline", "Outline", "Build outlines")

    catalog = discover_skill_catalog([root])
    entry = catalog.entries[0]

    assert entry.status == "active"
    assert entry.content_hash
    assert entry.path == root / "outline"


def _write_skill(root: Path, directory: str, name: str, description: str) -> None:
    skill_dir = root / directory
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n"
    )
