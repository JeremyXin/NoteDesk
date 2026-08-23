from typer.testing import CliRunner

from notedesk.cli.app import app


def test_run_command_creates_a_persisted_run(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "state.db"

    result = runner.invoke(app, ["run", "Create a research brief", "--db-path", str(db_path)])

    assert result.exit_code == 0
    assert "Run created:" in result.stdout
    assert "status=pending" in result.stdout


def test_inspect_command_shows_run_details(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "state.db"

    run_result = runner.invoke(app, ["run", "Create a research brief", "--db-path", str(db_path)])
    run_id = run_result.stdout.split("Run created: ", 1)[1].split()[0]

    inspect_result = runner.invoke(app, ["inspect", run_id, "--db-path", str(db_path)])

    assert inspect_result.exit_code == 0
    assert run_id in inspect_result.stdout
    assert "Create a research brief" in inspect_result.stdout
    assert "pending" in inspect_result.stdout


def test_abort_command_marks_run_as_aborted(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "state.db"

    run_result = runner.invoke(app, ["run", "Create a research brief", "--db-path", str(db_path)])
    run_id = run_result.stdout.split("Run created: ", 1)[1].split()[0]

    abort_result = runner.invoke(app, ["abort", run_id, "--db-path", str(db_path)])
    inspect_result = runner.invoke(app, ["inspect", run_id, "--db-path", str(db_path)])

    assert abort_result.exit_code == 0
    assert "aborted" in abort_result.stdout
    assert "aborted" in inspect_result.stdout


def test_resume_command_restarts_suspended_run(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "state.db"

    run_result = runner.invoke(app, ["run", "Create a research brief", "--db-path", str(db_path)])
    run_id = run_result.stdout.split("Run created: ", 1)[1].split()[0]
    runner.invoke(app, ["suspend-test-run", run_id, "--db-path", str(db_path)])

    resume_result = runner.invoke(app, ["resume", run_id, "--db-path", str(db_path)])
    inspect_result = runner.invoke(app, ["inspect", run_id, "--db-path", str(db_path)])

    assert resume_result.exit_code == 0
    assert "running" in resume_result.stdout
    assert "running" in inspect_result.stdout
