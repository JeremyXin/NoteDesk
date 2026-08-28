from __future__ import annotations

import os

from agentscope.credential import DeepSeekCredential
from agentscope.model import ChatModelBase, DeepSeekChatModel

from notedesk.model.config import ModelRoleMap, NamedModelConfig, Provider


class ModelFactory:
    def __init__(self, role_map: ModelRoleMap) -> None:
        self._role_map = role_map
        self._instances: dict[str, ChatModelBase] = {}

    def resolve(self, role_name: str) -> ChatModelBase:
        model_name = self._role_map.roles[role_name]
        if model_name not in self._instances:
            config = self._role_map.resolve_role(role_name)
            self._instances[model_name] = self._build_model(config)
        return self._instances[model_name]

    def _build_model(self, config: NamedModelConfig) -> ChatModelBase:
        if config.provider is not Provider.DEEPSEEK:
            raise ValueError(f"Unsupported provider: {config.provider}")

        api_key = config.api_key or os.getenv(config.api_key_env or "")
        if not api_key:
            raise EnvironmentError(
                f"Missing required environment variable: {config.api_key_env}"
            )

        credential = DeepSeekCredential(
            api_key=api_key,
            base_url=config.base_url or "https://api.deepseek.com",
        )
        parameters = DeepSeekChatModel.Parameters(
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            thinking_enable=config.thinking,
        )
        return DeepSeekChatModel(
            credential=credential,
            model=config.model,
            parameters=parameters,
            stream=True,
            max_retries=config.retry,
            context_size=config.context_size or 65536,
        )
