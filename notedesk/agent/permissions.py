from __future__ import annotations

from pathlib import Path

from agentscope.permission import (
    AdditionalWorkingDirectory,
    PermissionBehavior,
    PermissionContext,
    PermissionEngine,
    PermissionMode,
    PermissionRule,
)


def build_permission_engine(workspace: Path, interactive: bool) -> PermissionEngine:
    context = PermissionContext(
        mode=PermissionMode.ACCEPT_EDITS if interactive else PermissionMode.DONT_ASK,
        working_directories={
            str(workspace.resolve()): AdditionalWorkingDirectory(
                path=str(workspace.resolve()),
                source="notedesk-workspace",
            )
        },
    )
    engine = PermissionEngine(context)

    for rule in _default_rules():
        engine.add_rule(rule)

    return engine


def _default_rules() -> list[PermissionRule]:
    return [
        PermissionRule(
            tool_name="Bash",
            rule_content="twitter timeline:*",
            behavior=PermissionBehavior.ALLOW,
            source="notedesk-default",
        ),
        PermissionRule(
            tool_name="Bash",
            rule_content="twitter show:*",
            behavior=PermissionBehavior.ALLOW,
            source="notedesk-default",
        ),
        PermissionRule(
            tool_name="Bash",
            rule_content="twitter search:*",
            behavior=PermissionBehavior.ALLOW,
            source="notedesk-default",
        ),
        PermissionRule(
            tool_name="Bash",
            rule_content="twitter post:*",
            behavior=PermissionBehavior.ASK,
            source="notedesk-default",
        ),
        PermissionRule(
            tool_name="Bash",
            rule_content="twitter like:*",
            behavior=PermissionBehavior.ASK,
            source="notedesk-default",
        ),
        PermissionRule(
            tool_name="Bash",
            rule_content="twitter follow:*",
            behavior=PermissionBehavior.ASK,
            source="notedesk-default",
        ),
    ]
