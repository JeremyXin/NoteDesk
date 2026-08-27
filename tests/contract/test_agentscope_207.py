from importlib.metadata import PackageNotFoundError, version

import pytest


def test_agentscope_207_contract_is_installed() -> None:
    try:
        installed = version("agentscope")
    except PackageNotFoundError as exc:
        pytest.fail(f"agentscope is not installed: {exc}")

    assert installed == "2.0.7"


def test_agentscope_207_exposes_expected_symbols() -> None:
    from agentscope.agent import Agent
    from agentscope.model import ChatModelBase
    from agentscope.model import ChatResponse, DeepSeekChatModel
    from agentscope.credential import DeepSeekCredential
    from agentscope.permission import PermissionEngine, PermissionMode
    from agentscope.tool import Bash, TaskCreate, TaskGet, TaskList, TaskUpdate, Toolkit

    assert Agent is not None
    assert Toolkit is not None
    assert Bash is not None
    assert ChatModelBase is not None
    assert DeepSeekChatModel is not None
    assert DeepSeekCredential is not None
    assert ChatResponse is not None
    assert TaskCreate is not None
    assert TaskGet is not None
    assert TaskList is not None
    assert TaskUpdate is not None
    assert PermissionEngine is not None
    assert PermissionMode is not None
    assert hasattr(Agent, "reply_stream")


def test_agentscope_207_agent_state_contract() -> None:
    from agentscope.state import AgentState

    state = AgentState()

    assert hasattr(state, "tasks_context")
