import pytest
from pydantic import ValidationError

from notedesk.model.config import ModelRoleMap, NamedModelConfig, Provider


def test_model_role_map_allows_agent_and_generator_to_share_named_config() -> None:
    role_map = ModelRoleMap(
        models={
            "default": NamedModelConfig(
                provider=Provider.DEEPSEEK,
                model="deepseek-chat",
                api_key_env="DEEPSEEK_API_KEY",
                temperature=0.2,
            )
        },
        roles={"agent": "default", "generator": "default"},
    )

    assert role_map.resolve_role("agent").model == "deepseek-chat"
    assert role_map.resolve_role("generator").model == "deepseek-chat"


def test_model_role_map_rejects_unknown_role_reference() -> None:
    with pytest.raises(ValidationError):
        ModelRoleMap(
            models={
                "default": NamedModelConfig(
                    provider=Provider.DEEPSEEK,
                    model="deepseek-chat",
                    api_key_env="DEEPSEEK_API_KEY",
                )
            },
            roles={"agent": "default", "generator": "missing"},
        )


def test_model_role_map_rejects_missing_api_key_env_name() -> None:
    with pytest.raises(ValidationError):
        NamedModelConfig(
            provider=Provider.DEEPSEEK,
            model="deepseek-chat",
            api_key_env="",
        )


def test_model_role_map_rejects_illegal_model_parameters() -> None:
    with pytest.raises(ValidationError):
        NamedModelConfig(
            provider=Provider.DEEPSEEK,
            model="deepseek-chat",
            api_key_env="DEEPSEEK_API_KEY",
            temperature=3.0,
        )

