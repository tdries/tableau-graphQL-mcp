<!-- Thanks for contributing! Keep PRs focused and small where possible. -->

## What and why

<!-- What does this change, and why? Link any related issue: Closes #123 -->

## Checklist

- [ ] `uv run pytest` passes (and I added/updated tests for the change)
- [ ] `uv run ruff check .` and `uv run ruff format --check .` are clean
- [ ] `uv run mypy` is clean (strict)
- [ ] No new **runtime** dependency (this project is stdlib + `mcp` only)
- [ ] The server stays **read-only** (no mutations, no shell, no writes)
- [ ] README / CHANGELOG updated if behavior or the tool schema changed
- [ ] If a tool name or argument changed, I updated `tests/tool_contract.json` **on purpose** and noted it in the CHANGELOG (the tool schema is the public API)
