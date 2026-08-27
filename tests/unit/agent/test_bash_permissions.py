import asyncio
from pathlib import Path

from agentscope.permission import PermissionBehavior, PermissionMode
from agentscope.tool import Bash

from notedesk.agent.permissions import build_permission_engine


def test_interactive_permissions_use_accept_edits_mode(tmp_path: Path) -> None:
    engine = build_permission_engine(
        workspace=tmp_path,
        interactive=True,
    )

    assert engine.context.mode is PermissionMode.ACCEPT_EDITS


def test_non_interactive_permissions_use_dont_ask_mode(tmp_path: Path) -> None:
    engine = build_permission_engine(
        workspace=tmp_path,
        interactive=False,
    )

    assert engine.context.mode is PermissionMode.DONT_ASK


def test_twitter_read_command_is_explicitly_allowed(tmp_path: Path) -> None:
    engine = build_permission_engine(workspace=tmp_path, interactive=True)
    bash = Bash(cwd=tmp_path)

    decision = asyncio.run(
        engine.check_permission(
            bash,
            {"command": "twitter timeline --limit 10"},
        )
    )

    assert decision.behavior is PermissionBehavior.ALLOW


def test_twitter_write_command_requires_confirmation(tmp_path: Path) -> None:
    engine = build_permission_engine(workspace=tmp_path, interactive=True)
    bash = Bash(cwd=tmp_path)

    decision = asyncio.run(
        engine.check_permission(
            bash,
            {"command": "twitter post \"hello\""},
        )
    )

    assert decision.behavior is PermissionBehavior.ASK


def test_unclassified_dynamic_command_fails_closed(tmp_path: Path) -> None:
    engine = build_permission_engine(workspace=tmp_path, interactive=True)
    bash = Bash(cwd=tmp_path)

    decision = asyncio.run(
        engine.check_permission(
            bash,
            {"command": "twitter timeline $(cat secret.txt)"},
        )
    )

    assert decision.behavior is PermissionBehavior.ASK
