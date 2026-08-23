import pytest

from notedesk.capabilities.registry import CapabilityAlreadyRegisteredError, CapabilityRegistry
from notedesk.models.capabilities import CapabilityDescriptor, RetryPolicy


def test_registry_registers_and_resolves_capabilities() -> None:
    registry = CapabilityRegistry()
    descriptor = CapabilityDescriptor(
        capability_id="sink.console_output",
        kind="sink",
        description="Render output",
        retry_policy=RetryPolicy(max_attempts=1),
    )

    registry.register(descriptor)

    resolved = registry.get("sink.console_output")
    assert resolved.capability_id == "sink.console_output"


def test_registry_rejects_duplicate_capability_ids() -> None:
    registry = CapabilityRegistry()
    descriptor = CapabilityDescriptor(
        capability_id="sink.console_output",
        kind="sink",
        description="Render output",
        retry_policy=RetryPolicy(max_attempts=1),
    )

    registry.register(descriptor)

    with pytest.raises(CapabilityAlreadyRegisteredError):
        registry.register(descriptor)


def test_registry_rejects_unknown_capability_lookup() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(KeyError):
        registry.get("missing.capability")
