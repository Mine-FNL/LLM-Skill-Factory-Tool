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

## The highest-leverage contributions

The codebase is solid; what's missing is *content* and *real measurements*. These are the changes that move the project most:

### 1. Add a reference eval set

The shipped reference eval sets cover a backend engineer, a quant researcher, and a financial analyst. **More domains welcome**: code review, customer support, RAG, summarization, data-pipeline engineering, scientific writing, copy editing, etc.

```bash
# Copy the template.
cp evals/template.yaml evals/my-new-domain.yaml
$EDITOR evals/my-new-domain.yaml

# Verify it loads.
python -c "from skill_factory.eval import load_eval_set; print(load_eval_set('my-new-domain'))"

# Run it against a related skill, or open an issue asking for one.
python -m skill_factory eval <some-skill> --eval-set my-new-domain --save
```

A good eval set has:
- **5-10 prompts**, each grounded in a real-world scenario the base model would handle poorly.
- **`expected_traits`** that are checkable (not vague). A judge can read them and score consistently.
- **At least one control** so the judge self-calibration fires. An "obviously-bad" prompt + expected score 0.0 is the minimum.

### 2. Share a real measured lift number

This is the single most valuable contribution to the project. Run the eval against a saved skill, paste the JSON into a new issue using the **Eval report** template, and (optionally) commit the updated `metadata.json`.

```bash
python -m skill_factory eval <slug> --save --json > my-lift.json
gh issue create --template eval-report.yml   # paste my-lift.json into the body
```

The `scripts/render_measured_skills.py` helper picks up `metadata.json` files with a non-zero `lift_pp` and rebuilds the "Skills that have been measured" table in the README.

### 3. Improve the meta-skill

`skill_factory/meta_prompts.py` is the rubric the generator uses. Better rules there → better skills. Concrete ways to help:
- Add a "do not use when…" prompt directive (the open spec calls for negative triggers).
- Add rules enforcing the official Claude Code spec: no XML in names, no reserved words (`anthropic`, `claude`), 64-char name limit, 1024-char description.
- Add rules for progressive disclosure (L1 metadata → L2 instructions → L3 resources).

### 4. New UI polish

The Streamlit UI is functional but bare. High-value additions:
- A "Run eval" button on each library card.
- A side-by-side v1 / v2 / v3 comparison view.
- A live diff between skill versions.

UI changes must extend `tests/test_app_smoke.py:PAGES` and use `AppTest` so the new pages get a smoke check.

## Reporting security issues

Please see [`SECURITY.md`](SECURITY.md). Do **not** file public issues for
vulnerabilities.
