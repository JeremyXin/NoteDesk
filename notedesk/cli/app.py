from __future__ import annotations

import platform
import uuid
from pathlib import Path

import typer

from notedesk.models.state import RunState, RunStatus
from notedesk.storage.repositories import RunRepository
from notedesk.storage.schema import initialize_database


app = typer.Typer(help="NoteDesk local-first agentic knowledge workspace.")
config_app = typer.Typer(help="Manage NoteDesk configuration.")
app.add_typer(config_app, name="config")


DEFAULT_CONFIG_PATH = Path(".notedesk/config.toml")
DEFAULT_DB_PATH = Path(".notedesk/notedesk.db")
DEFAULT_ARTIFACTS_DIR = Path(".notedesk/artifacts")


def repository_for(db_path: Path) -> RunRepository:
    initialize_database(db_path)
    return RunRepository(db_path)


def render_default_config(db_path: Path, artifacts_dir: Path) -> str:
    return (
        f'db_path = "{db_path}"\n'
        f'artifacts_dir = "{artifacts_dir}"\n'
    )


@config_app.command("init")
def config_init(config_path: Path = typer.Option(DEFAULT_CONFIG_PATH, exists=False)) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    db_path = config_path.parent / DEFAULT_DB_PATH.name
    artifacts_dir = config_path.parent / DEFAULT_ARTIFACTS_DIR.name
    config_path.write_text(render_default_config(db_path, artifacts_dir))
    typer.echo(f"Config initialized: {config_path}")


@app.command()
def doctor(db_path: Path = typer.Option(DEFAULT_DB_PATH, exists=False)) -> None:
    initialize_database(db_path)
    typer.echo("Environment: OK")
    typer.echo(f"Python: {platform.python_version()}")
    typer.echo(f"Database: {db_path}")


@app.command()
def run(goal: str, db_path: Path = typer.Option(DEFAULT_DB_PATH, exists=False)) -> None:
    repository = repository_for(db_path)
    run_state = RunState(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        session_id=f"session-{uuid.uuid4().hex[:8]}",
        goal=goal,
        status=RunStatus.PENDING,
    )
    repository.upsert(run_state)
    typer.echo(f"Run created: {run_state.run_id} status={run_state.status.value}")


@app.command()
def inspect(run_id: str, db_path: Path = typer.Option(DEFAULT_DB_PATH, exists=False)) -> None:
    repository = repository_for(db_path)
    run_state = repository.get(run_id)
    typer.echo(f"run_id={run_state.run_id}")
    typer.echo(f"goal={run_state.goal}")
    typer.echo(f"status={run_state.status.value}")


@app.command()
def abort(run_id: str, db_path: Path = typer.Option(DEFAULT_DB_PATH, exists=False)) -> None:
    repository = repository_for(db_path)
    run_state = repository.get(run_id)
    updated = run_state.model_copy(update={"status": RunStatus.ABORTED})
    repository.upsert(updated)
    typer.echo(f"Run {run_id} aborted")


@app.command()
def resume(run_id: str, db_path: Path = typer.Option(DEFAULT_DB_PATH, exists=False)) -> None:
    repository = repository_for(db_path)
    run_state = repository.get(run_id)
    updated = run_state.model_copy(update={"status": RunStatus.RUNNING})
    repository.upsert(updated)
    typer.echo(f"Run {run_id} resumed with status={updated.status.value}")


@app.command("suspend-test-run", hidden=True)
def suspend_test_run(run_id: str, db_path: Path = typer.Option(DEFAULT_DB_PATH, exists=False)) -> None:
    repository = repository_for(db_path)
    run_state = repository.get(run_id)
    updated = run_state.model_copy(update={"status": RunStatus.SUSPENDED})
    repository.upsert(updated)


def main() -> None:
    app()
