import os

import pytest


pytestmark = pytest.mark.live_smoke


def test_live_smoke_requires_explicit_env() -> None:
    if not os.getenv("NOTEDESK_RUN_LIVE_SMOKE"):
        pytest.skip("Set NOTEDESK_RUN_LIVE_SMOKE=1 to enable live smoke tests.")

    required = ["DEEPSEEK_API_KEY"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip(f"Missing required env vars: {', '.join(missing)}")

    assert os.getenv("DEEPSEEK_API_KEY")
