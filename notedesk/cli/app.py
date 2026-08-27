from __future__ import annotations

import asyncio
import platform
import shutil
from importlib.metadata import version
from pathlib import Path
import sys

import typer

from notedesk.agent.runtime import AgentSessionRuntime, build_default_role_map
from notedesk.agent.factory import build_agent_session
from notedesk.config.loader import load_settings
from notedesk.config.models import AppSettings
from notedesk.interactive.tui.app import NoteDeskTUI
from notedesk.interactive.tui.runner import TUISessionController
from notedesk.skills.discovery import discover_skill_catalog


DEFAULT_CONFIG_PATH = Path(".notedesk/config.toml")

app = typer.Typer(
    help="NoteDesk local-first agentic knowledge workspace.",
    invoke_without_command=True,
)
config_app = typer.Typer(help="Manage NoteDesk configuration.")
skills_app = typer.Typer(help="Inspect discovered skills.")
app.add_typer(config_app, name="config")
app.add_typer(skills_app, name="skills")


def render_default_config() -> str:
    return """
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
""".strip() + "\n"


@config_app.command("init")
def config_init(config_path: Path = typer.Option(DEFAULT_CONFIG_PATH, exists=False)) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(render_default_config())
    workspace = config_path.parent
    (workspace / "skills").mkdir(parents=True, exist_ok=True)
    (workspace / "artifacts").mkdir(parents=True, exist_ok=True)
    typer.echo(f"Config initialized: {config_path}")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    config_path: Path = typer.Option(DEFAULT_CONFIG_PATH, exists=False),
) -> None:
    if ctx.invoked_subcommand:
        return
    settings = load_settings(config_path)
    tui = NoteDeskTUI(
        workspace=settings.workspace,
        artifact_root=settings.artifacts.root,
    )
    if sys.stdin.isatty() and sys.stdout.isatty():
        launch_tui(settings, tui)
    else:
        typer.echo(tui.render_launch_summary())


@app.command()
def doctor(config_path: Path = typer.Option(DEFAULT_CONFIG_PATH, exists=False)) -> None:
    settings = load_settings(config_path)
    typer.echo("Environment: OK")
    typer.echo(f"Python: {platform.python_version()}")
    typer.echo(f"AgentScope: {version('agentscope')}")
    typer.echo(f"Workspace: {settings.workspace}")
    typer.echo(f"Artifacts: {settings.artifacts.root}")
    typer.echo(f"Twitter CLI: {shutil.which('twitter') or 'not found'}")


def _render_skills(config_path: Path) -> None:
    settings = load_settings(config_path)
    catalog = discover_skill_catalog([root.resolved_path for root in settings.skill_roots])
    for entry in catalog.entries:
        typer.echo(
            f"{entry.status}\t{entry.name or '-'}\t{entry.path}"
        )


@skills_app.callback(invoke_without_command=True)
def skills_command(
    ctx: typer.Context,
    config_path: Path = typer.Option(DEFAULT_CONFIG_PATH, exists=False),
) -> None:
    if ctx.invoked_subcommand:
        return
    _render_skills(config_path)


@skills_app.command("reload")
def skills_reload(config_path: Path = typer.Option(DEFAULT_CONFIG_PATH, exists=False)) -> None:
    typer.echo("Skills reloaded")
    _render_skills(config_path)


def main() -> None:
    app()


def launch_tui(settings: AppSettings, tui: NoteDeskTUI | None = None) -> None:
    ui_queue: asyncio.Queue = asyncio.Queue()
    artifact_root = settings.artifacts.root
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_root / "latest.md"
    runtime = AgentSessionRuntime(
        agent=build_agent_session(settings, build_default_role_map(settings)),
        ui_queue=ui_queue,
        artifact_path=artifact_path,
    )
    tui = tui or NoteDeskTUI(
        workspace=settings.workspace,
        artifact_root=artifact_root,
    )
    controller = TUISessionController(tui=tui, runtime=runtime)
    application = tui.build_application()
    tui.on_submit = lambda text: application.create_background_task(
        controller.submit_prompt(text)
    )
    tui.on_cancel = lambda: application.create_background_task(controller.cancel())
    tui.on_approve_permission = lambda: application.create_background_task(
        controller.approve_permission()
    )
    tui.on_deny_permission = lambda: application.create_background_task(
        controller.deny_permission()
    )
    application.run()
