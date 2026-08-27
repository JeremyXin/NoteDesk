from pathlib import Path

from typer.testing import CliRunner

from notedesk.cli.app import app


def test_config_init_writes_default_config_file(tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["config", "init", "--config-path", str(config_path)])

    assert result.exit_code == 0
    assert config_path.exists()
    text = config_path.read_text()
    assert "[deepseek]" in text
    assert "[permissions]" in text
    assert "[[skill_roots]]" in text
    assert 'root = ".notedesk/artifacts"' in text
    assert str(config_path) in result.stdout


def test_config_init_creates_project_and_runtime_directories(tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["config", "init", "--config-path", str(config_path)])

    assert result.exit_code == 0
    assert (tmp_path / "skills").is_dir()
    assert (tmp_path / ".notedesk" / "artifacts").is_dir()
    assert (tmp_path / ".notedesk" / "state").is_dir()


def test_config_init_migrates_legacy_config_to_root_by_default(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    legacy_dir = tmp_path / ".notedesk"
    legacy_dir.mkdir()
    legacy_config = legacy_dir / "config.toml"
    legacy_config.write_text(
        """
workspace = "."

[deepseek]
model = "deepseek-reasoner"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = ".notedesk/artifacts"

[permissions]
mode = "dont_ask"

[[skill_roots]]
path = "skills"
""".strip()
    )

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["config", "init"], catch_exceptions=False)

    assert result.exit_code == 0
    root_config = tmp_path / "config.toml"
    assert root_config.exists()
    assert 'model = "deepseek-reasoner"' in root_config.read_text()
    assert 'root = ".notedesk/artifacts"' in root_config.read_text()
