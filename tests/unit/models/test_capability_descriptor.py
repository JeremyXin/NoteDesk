import pytest
from pydantic import ValidationError

from notedesk.models.capabilities import CapabilityDescriptor, RetryPolicy


def test_capability_descriptor_defaults_to_enabled() -> None:
    descriptor = CapabilityDescriptor(
        capability_id="sink.console_output",
        kind="sink",
        description="Render content to stdout",
        retry_policy=RetryPolicy(max_attempts=1),
    )

    assert descriptor.enabled is True
    assert descriptor.retry_policy.max_attempts == 1


def test_capability_descriptor_rejects_invalid_retry_policy() -> None:
    with pytest.raises(ValidationError):
        CapabilityDescriptor(
            capability_id="sink.console_output",
            kind="sink",
            description="Render content to stdout",
            retry_policy=RetryPolicy(max_attempts=0),
        )
