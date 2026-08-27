# NoteDesk

`NoteDesk` is a local-first agent workspace for knowledge tasks.

## Current Configuration Layout

Project configuration lives at the repository root:

```text
config.toml
```

Runtime data stays under `.notedesk/`:

```text
.notedesk/
  artifacts/
  state/
```

Compatibility behavior:

- `notedesk` reads `./config.toml` first.
- If `./config.toml` does not exist, it falls back to `.notedesk/config.toml`.

## Initialize

Create the default project config and runtime directories:

```bash
./.venv/bin/notedesk config init
```

This writes:

- `config.toml`
- `skills/`
- `.notedesk/artifacts/`
- `.notedesk/state/`

## Default Config

The generated config currently looks like:

```toml
workspace = "."

[deepseek]
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"

[artifacts]
root = ".notedesk/artifacts"

[permissions]
mode = "accept_edits"

[[skill_roots]]
path = "skills"
```

## Run

Start the CLI:

```bash
./.venv/bin/notedesk
```

Useful commands:

```bash
./.venv/bin/notedesk doctor
./.venv/bin/notedesk skills
./.venv/bin/notedesk skills reload
```

## Live Smoke

The live smoke test now defaults to:

- config: `config.toml`
- artifact: `.notedesk/live-smoke.md`

Example:

```bash
NOTEDESK_RUN_LIVE_SMOKE=1 ./.venv/bin/pytest tests/smoke/test_real_twitter_deepseek.py -q
```
