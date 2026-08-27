import os
from pathlib import Path
import asyncio
import shlex
import shutil

import pytest

from notedesk.agent.runtime import run_live_smoke
from notedesk.config.loader import load_settings


pytestmark = pytest.mark.live_smoke


def test_live_smoke_requires_explicit_env() -> None:
    if not os.getenv("NOTEDESK_RUN_LIVE_SMOKE"):
        pytest.skip("Set NOTEDESK_RUN_LIVE_SMOKE=1 to enable live smoke tests.")

    required = ["DEEPSEEK_API_KEY"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip(f"Missing required env vars: {', '.join(missing)}")

    if shutil.which("twitter") is None:
        pytest.skip("Twitter CLI not found in PATH.")

    config_path = Path(os.getenv("NOTEDESK_SMOKE_CONFIG", "config.toml"))
    if not config_path.exists():
        pytest.skip(f"Config not found: {config_path}")

    settings = load_settings(config_path)
    artifact_path = Path(os.getenv("NOTEDESK_SMOKE_ARTIFACT", ".notedesk/live-smoke.md"))
    receipt = asyncio.run(
        run_live_smoke(
            settings=settings,
            artifact_path=artifact_path,
            ui_queue=asyncio.Queue(),
            twitter_command=shlex.split(
                os.getenv("NOTEDESK_SMOKE_TWITTER_CMD", "twitter timeline --limit 3")
            ),
            summary_prompt=os.getenv(
                "NOTEDESK_SMOKE_PROMPT",
                "Produce a markdown brief with a title and bullet insights.",
            ),
        )
    )

    assert receipt.path.exists()
    assert receipt.bytes_written > 0
