# Contributing

Thanks for your interest in improving **LLM Skill Factory**! 🎉

This project is intentionally small and friendly. The core package
(`skill_factory/`) contains all the logic and has **no Streamlit imports**;
the UI (`ui/`) and the entrypoint (`app.py`) sit on top.

## Development setup

```bash
git clone https://github.com/Mine-FNL/LLM-Skill-Factory-Tool.git
cd LLM-Skill-Factory-Tool
python -m venv .venv && source .venv/bin/activate
make dev           # pip install -e ".[dev,pdf]"
make test          # pytest
```

The `Makefile` is the source of truth for project commands. Run `make help`
for the full list.

## Coding standards

- **Python 3.10+** is the supported floor. The CI matrix tests 3.10, 3.11, 3.12.
- **Ruff** handles both lint and format. `make lint` and `make format` exist
  for convenience; CI runs `ruff check .` and `ruff format --check .`.
- **Type hints** are encouraged but not enforced. `make typecheck` runs `mypy`.
- **Tests** ship alongside the change. The `skill_factory/` package is
  fully unit-testable (no Streamlit imports). UI changes should add or update
  an `AppTest` smoke test in `tests/test_app_smoke.py`.
- **No API keys in tests.** Network tests should mock the LLM client or use
  the curated fallback list in `LLMClient.list_models`.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(batch): allow concurrency knob per preset
fix(client): retry on 503 with exponential backoff
docs(readme): add production deployment section
chore(deps): bump streamlit to 1.40
test(safety): cover reserved-slug detection
```

Commit messages describe **what is IN the commit**, not what is planned next.
A merge commit's body must match the diff. (See `AGENTS.md` for the same rule
applied at the agent level.)

## Pull requests

1. Fork + branch from `main`.
2. Keep changes focused. Larger refactors should be split into stacked PRs.
3. Run `make lint test typecheck` locally before pushing.
4. Open a PR against `main`. CI must be green before review.
5. One approval from a maintainer is enough for non-breaking changes.

## Reporting security issues

Please see [`SECURITY.md`](SECURITY.md). Do **not** file public issues for
vulnerabilities.
