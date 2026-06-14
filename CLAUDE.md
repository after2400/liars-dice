# liars-dice — Project Rules

## Python execution

**Always use `uv run python` — never bare `python3` or `python`.**

```bash
# correct
uv run python -m game ...
uv run python .github/scripts/register_player.py
uv run pytest -v

# wrong — do not use
python3 script.py
python -m game
pytest tests/
```

This applies everywhere: shell commands, CI scripts, subagent prompts, code review suggestions. No exceptions.

## Testing

Run the full test suite with:

```bash
uv run pytest -v
```

This collects both `tests/` and `examples/tests/` via the `testpaths` setting in
`pyproject.toml` — pass no path so the example player's tests run too. Don't pass
`tests/` explicitly or the `examples/` template tests are skipped.

## PR and commit attribution

All PRs must use `🤖 Co-Authored with [Claude Code](https://claude.com/claude-code)` in the body footer — not "Generated with". This project is a genuine collaboration.
