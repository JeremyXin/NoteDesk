from typer.testing import CliRunner

from notedesk.cli.app import app


def test_doctor_reports_environment_status(tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "config.toml"
    skills_path = tmp_path / "skills"
    artifacts_path = tmp_path / "artifacts"
    skills_path.mkdir()
    artifacts_path.mkdir()
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
        ["doctor", "--config-path", str(config_path)],
        env={"DEEPSEEK_API_KEY": "secret"},
    )

    assert result.exit_code == 0
    assert "Environment: OK" in result.stdout
    assert "AgentScope: 2.0.7" in result.stdout
    assert str(artifacts_path) in result.stdout
    assert "DeepSeek API key: env:DEEPSEEK_API_KEY" in result.stdout


def test_doctor_reports_inline_api_key_source_without_echoing_secret(tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "config.toml"
    skills_path = tmp_path / "skills"
    artifacts_path = tmp_path / "artifacts"
    skills_path.mkdir()
    artifacts_path.mkdir()
    config_path.write_text(
        """
workspace = "."

[deepseek]
model = "deepseek-chat"
api_key = "inline-secret"

[artifacts]
root = "artifacts"

[permissions]
mode = "accept_edits"

[[skill_roots]]
path = "skills"
""".strip()
    )

    result = runner.invoke(app, ["doctor", "--config-path", str(config_path)])

    assert result.exit_code == 0
    assert "DeepSeek API key: inline-config" in result.stdout
    assert "inline-secret" not in result.stdout
