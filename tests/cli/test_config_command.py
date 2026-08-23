from pathlib import Path

from typer.testing import CliRunner

from notedesk.cli.app import app


def test_config_init_writes_default_config_file(tmp_path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["config", "init", "--config-path", str(config_path)])

    assert result.exit_code == 0
    assert config_path.exists()
    assert "db_path" in config_path.read_text()
    assert str(config_path) in result.stdout
