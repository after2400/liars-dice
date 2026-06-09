# liars-dice — Project Rules

## Python execution

**Always use `uv run python` — never bare `python3` or `python`.**

```bash
# correct
uv run python -m game ...
uv run python .github/scripts/register_player.py
uv run pytest tests/ -v

# wrong — do not use
python3 script.py
python -m game
pytest tests/
```

This applies everywhere: shell commands, CI scripts, subagent prompts, code review suggestions. No exceptions.

## Testing

Run the full test suite with:
```bash
uv run pytest tests/ -v
```
