import os

import pytest
from agentscope.credential import DeepSeekCredential
from agentscope.model import ChatModelBase, DeepSeekChatModel

from notedesk.model.config import ModelRoleMap, NamedModelConfig, Provider
from notedesk.model.factory import ModelFactory


@pytest.fixture
def role_map() -> ModelRoleMap:
    return ModelRoleMap(
        models={
            "default": NamedModelConfig(
                provider=Provider.DEEPSEEK,
                model="deepseek-chat",
                api_key_env="DEEPSEEK_API_KEY",
                temperature=0.6,
                max_tokens=2048,
                retry=4,
                context_size=32768,
                thinking=True,
                base_url="https://api.deepseek.com",
            )
        },
        roles={"agent": "default", "generator": "default"},
    )


def test_model_factory_resolve_returns_agentscope_chat_model(monkeypatch: pytest.MonkeyPatch, role_map: ModelRoleMap) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    factory = ModelFactory(role_map)
    model = factory.resolve("agent")

    assert isinstance(model, ChatModelBase)
    assert isinstance(model, DeepSeekChatModel)


def test_model_factory_reuses_instance_for_shared_role_config(
    monkeypatch: pytest.MonkeyPatch, role_map: ModelRoleMap
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    factory = ModelFactory(role_map)

    assert factory.resolve("agent") is factory.resolve("generator")


def test_model_factory_uses_deepseek_native_parameters(
    monkeypatch: pytest.MonkeyPatch, role_map: ModelRoleMap
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    factory = ModelFactory(role_map)
    model = factory.resolve("agent")

    assert model.stream is True
    assert model.max_retries == 4
    assert model.context_size == 32768
    assert model.model == "deepseek-chat"
    assert isinstance(model.credential, DeepSeekCredential)
    assert model.credential.api_key.get_secret_value() == "secret"
    assert model.credential.base_url == "https://api.deepseek.com"
    assert model.parameters == DeepSeekChatModel.Parameters(
        temperature=0.6,
        max_tokens=2048,
        thinking_enable=True,
    )


def test_model_factory_requires_declared_api_key_env(
    monkeypatch: pytest.MonkeyPatch, role_map: ModelRoleMap
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    factory = ModelFactory(role_map)

    with pytest.raises(EnvironmentError):
        factory.resolve("agent")
