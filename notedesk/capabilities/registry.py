from __future__ import annotations

from notedesk.models.capabilities import CapabilityDescriptor


class CapabilityAlreadyRegisteredError(ValueError):
    pass


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDescriptor] = {}

    def register(self, descriptor: CapabilityDescriptor) -> None:
        if descriptor.capability_id in self._capabilities:
            raise CapabilityAlreadyRegisteredError(
                f"Capability '{descriptor.capability_id}' is already registered"
            )
        self._capabilities[descriptor.capability_id] = descriptor

    def get(self, capability_id: str) -> CapabilityDescriptor:
        return self._capabilities[capability_id]

    def list_all(self) -> list[CapabilityDescriptor]:
        return list(self._capabilities.values())
