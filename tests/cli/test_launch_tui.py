from __future__ import annotations

import importlib
from pathlib import Path

from notedesk.config.models import (
    AppSettings,
    ArtifactSettings,
    DeepSeekSettings,
    PermissionMode,
    PermissionSettings,
)

cli_module = importlib.import_module("notedesk.cli.app")


class FakeApplication:
    def __init__(self) -> None:
        self.ran = False
        self.scheduled = []

    def create_background_task(self, coroutine):
        self.scheduled.append(coroutine)
        coroutine.close()
        return coroutine

    def run(self) -> None:
        self.ran = True


class FakeTUI:
    def __init__(self) -> None:
        self.on_submit = lambda text: None
        self.on_cancel = lambda: None
        self.on_approve_permission = lambda: None
        self.on_deny_permission = lambda: None
        self.application = FakeApplication()

    def build_application(self):
        return self.application


class FakeRuntime:
    def __init__(self, agent, ui_queue, artifact_path) -> None:
        self.agent = agent
        self.ui_queue = ui_queue
        self.artifact_path = artifact_path


class FakeController:
    def __init__(self, tui, runtime) -> None:
        self.tui = tui
        self.runtime = runtime

    async def submit_prompt(self, prompt: str) -> None:
        return None

    async def cancel(self) -> None:
        return None

    async def approve_permission(self) -> None:
        return None

    async def deny_permission(self) -> None:
        return None


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        workspace=tmp_path,
        deepseek=DeepSeekSettings(
            model="deepseek-chat",
            api_key_env="DEEPSEEK_API_KEY",
        ),
        artifacts=ArtifactSettings(root=tmp_path / "artifacts"),
        permissions=PermissionSettings(mode=PermissionMode.ACCEPT_EDITS),
    )


def test_launch_tui_wires_runtime_controller_and_callbacks(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli_module, "build_agent_session", lambda settings, role_map: object()
    )

    def _runtime_factory(agent, ui_queue, artifact_path):
        runtime = FakeRuntime(agent=agent, ui_queue=ui_queue, artifact_path=artifact_path)
        captured["runtime"] = runtime
        return runtime

    monkeypatch.setattr(cli_module, "AgentSessionRuntime", _runtime_factory)
    monkeypatch.setattr(cli_module, "TUISessionController", FakeController)

    tui = FakeTUI()
    settings = _settings(tmp_path)

    cli_module.launch_tui(settings=settings, tui=tui)
    tui.on_submit("hello")
    tui.on_cancel()
    tui.on_approve_permission()
    tui.on_deny_permission()

    runtime = captured["runtime"]
    assert isinstance(runtime, FakeRuntime)
    assert runtime.artifact_path == tmp_path / "artifacts" / "latest.md"
    assert (tmp_path / "artifacts").is_dir()
    assert tui.application.ran is True
    assert len(tui.application.scheduled) == 4
