from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


HookCallback = Callable[[dict[str, Any]], None]


class HookBlockedError(RuntimeError):
    pass


class HookDispatcher:
    def __init__(self) -> None:
        self._hooks: dict[str, list[HookCallback]] = defaultdict(list)

    def register(self, event_name:mustr, callback: HookCallback) -> None:
        self._hooks[event_name].append(callback)

    def dispatch(self, event_name: str, payload: dict[str, Any]) -> None:
        for callback in self._hooks[event_name]:
            callback(payload)
