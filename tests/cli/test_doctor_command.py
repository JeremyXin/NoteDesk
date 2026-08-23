from typer.testing import CliRunner

from notedesk.cli.app import app


def test_doctor_reports_environment_status(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "state.db"

    result = runner.invoke(app, ["doctor", "--db-path", str(db_path)])

    assert result.exit_code == 0
    assert "Environment: OK" in result.stdout
    assert str(db_path) in result.stdout
