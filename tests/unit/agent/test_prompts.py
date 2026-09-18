from notedesk.agent.prompts import default_system_prompt


def test_default_system_prompt_bounds_task_tracking_before_synthesis() -> None:
    prompt = default_system_prompt()

    assert "at most one task" in prompt
    assert "within 12 reasoning actions" in prompt
    assert "produce the final answer" in prompt
