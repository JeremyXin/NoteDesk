import subprocess

import pytest

from notedesk.agent.runtime import RuntimeFailure, _run_twitter_command


def test_run_twitter_command_sanitizes_sensitive_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["twitter", "timeline"],
            returncode=1,
            stdout="",
            stderr="token=secret123 cookie=sessionabc authorization: bearer xyz",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeFailure) as exc:
        _run_twitter_command(["twitter", "timeline"])

    message = str(exc.value).lower()
    assert "secret123" not in message
    assert "sessionabc" not in message
    assert "bearer xyz" not in message
    assert "[redacted]" in message
