import asyncio
from pathlib import Path

import pytest

from notedesk.agent.runtime import CoreMVPRuntime, RuntimeFailure


def test_offline_vertical_slice_creates_artifact_and_updates_tasks(tmp_path: Path) -> None:
    runtime = CoreMVPRuntime(
        artifact_path=tmp_path / "summary.md",
        ui_queue=asyncio.Queue(),
    )

    receipt = asyncio.run(
        runtime.run_twitter_to_markdown(
            request="Summarize this timeline",
            fetch_tweets=lambda: [f"tweet {i}" for i in range(10)],
            generate_markdown=lambda tweets: "# Summary\n\n" + "\n".join(f"- {tweet}" for tweet in tweets),
        )
    )

    assert receipt.path.exists()
    assert "tweet 0" in receipt.path.read_text()
    assert [task.state for task in runtime.state.tasks_context.tasks] == ["completed", "completed"]


def test_offline_vertical_slice_does_not_write_artifact_on_fetch_failure(tmp_path: Path) -> None:
    runtime = CoreMVPRuntime(
        artifact_path=tmp_path / "summary.md",
        ui_queue=asyncio.Queue(),
    )

    with pytest.raises(RuntimeFailure):
        asyncio.run(
            runtime.run_twitter_to_markdown(
                request="Summarize this timeline",
                fetch_tweets=_raise_fetch_failure,
                generate_markdown=lambda tweets: "# Summary\n",
            )
        )

    assert not (tmp_path / "summary.md").exists()


def test_offline_vertical_slice_does_not_write_artifact_on_markdown_failure(tmp_path: Path) -> None:
    runtime = CoreMVPRuntime(
        artifact_path=tmp_path / "summary.md",
        ui_queue=asyncio.Queue(),
    )

    with pytest.raises(RuntimeFailure):
        asyncio.run(
            runtime.run_twitter_to_markdown(
                request="Summarize this timeline",
                fetch_tweets=lambda: [f"tweet {i}" for i in range(10)],
                generate_markdown=lambda tweets: "not markdown",
            )
        )

    assert not (tmp_path / "summary.md").exists()


def _raise_fetch_failure() -> list[str]:
    raise RuntimeError("twitter failed")
