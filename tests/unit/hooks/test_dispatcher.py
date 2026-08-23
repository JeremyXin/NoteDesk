from notedesk.hooks.dispatcher import HookBlockedError, HookDispatcher


def test_dispatcher_runs_hooks_in_registration_order() -> None:
    dispatcher = HookDispatcher()
    events: list[str] = []

    dispatcher.register("before_step", lambda payload: events.append(f"first:{payload['step']}"))
    dispatcher.register("before_step", lambda payload: events.append(f"second:{payload['step']}"))

    dispatcher.dispatch("before_step", {"step": "collect"})

    assert events == ["first:collect", "second:collect"]


def test_dispatcher_stops_when_hook_blocks_execution() -> None:
    dispatcher = HookDispatcher()
    events: list[str] = []

    def blocking_hook(payload: dict[str, str]) -> None:
        events.append(f"blocked:{payload['step']}")
        raise HookBlockedError("budget exceeded")

    dispatcher.register("before_step", blocking_hook)
    dispatcher.register("before_step", lambda payload: events.append(f"after:{payload['step']}"))

    try:
        dispatcher.dispatch("before_step", {"step": "collect"})
    except HookBlockedError as exc:
        assert "budget exceeded" in str(exc)
    else:
        raise AssertionError("expected hook dispatch to raise HookBlockedError")

    assert events == ["blocked:collect"]
