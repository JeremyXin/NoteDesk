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
    assert str(config_path) in result.stdout


def test_config_init_creates_default_runtime_directories(tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / ".notedesk" / "config.toml"

    result = runner.invoke(app, ["config", "init", "--config-path", str(config_path)])

    assert result.exit_code == 0
    assert (tmp_path / ".notedesk" / "skills").is_dir()
    assert (tmp_path / ".notedesk" / "artifacts").is_dir()
