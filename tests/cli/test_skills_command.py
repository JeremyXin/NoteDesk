from typer.testing import CliRunner

from notedesk.cli.app import app


def test_skills_command_reports_active_shadowed_and_invalid_entries(tmp_path) -> None:
    runner = CliRunner()
    root_a = tmp_path / "skills-a"
    root_b = tmp_path / "skills-b"
    artifacts = tmp_path / "artifacts"
    root_a.mkdir()
    root_b.mkdir()
    artifacts.mkdir()

    twitter_a = root_a / "twitter-cli"
    twitter_a.mkdir()
    (twitter_a / "SKILL.md").write_text(
        "---\nname: twitter-cli\ndescription: Twitter read\n---\nUse twitter\n"
    )

    twitter_b = root_b / "twitter-cli"
    twitter_b.mkdir()
    (twitter_b / "SKILL.md").write_text(
        "---\nname: twitter-cli\ndescription: Shadowed twitter\n---\nUse override\n"
    )

    broken = root_b / "broken"
    broken.mkdir()
    (broken / "SKILL.md").write_text("# broken")

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
workspace = "."

[deepseek]
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = "artifacts"

[permissions]
mode = "accept_edits"

[[skill_roots]]
path = "{root_a.name}"

[[skill_roots]]
path = "{root_b.name}"
""".strip()
    )

    result = runner.invoke(
        app,
        ["skills", "--config-path", str(config_path)],
        env={"DEEPSEEK_API_KEY": "secret"},
    )

    assert result.exit_code == 0
    assert "active" in result.stdout
    assert "shadowed" in result.stdout
    assert "invalid" in result.stdout
    assert "twitter-cli" in result.stdout


def test_default_invocation_launches_tui_summary(tmp_path) -> None:
    runner = CliRunner()
    skills = tmp_path / "skills"
    artifacts = tmp_path / "artifacts"
    skills.mkdir()
    artifacts.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
workspace = "."

[deepseek]
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = "artifacts"

[permissions]
mode = "accept_edits"

[[skill_roots]]
path = "skills"
""".strip()
    )

    result = runner.invoke(
        app,
        ["--config-path", str(config_path)],
        env={"DEEPSEEK_API_KEY": "secret"},
    )

    assert result.exit_code == 0
    assert "Launching NoteDesk TUI" in result.stdout
