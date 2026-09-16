# Changelog

All notable changes to **LLM Skill Factory** are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/) and the project adheres
to [Semantic Versioning](https://semver.org/).

## [0.3.0] — Unreleased

**Headline: prove your skill makes the model better, with numbers.**

The eval harness turns "I think my skill helps" into "your skill improves
Claude Sonnet 4.6 by **+42.9pp** on the held-out set, 95% CI [+15, +70]."

### Added
- **`skill_factory.eval`** — new package with:
  - `EvalSet` / `EvalPrompt` / `JudgeConfig` dataclasses, YAML loader, runner,
    judge wrapper, and CLI dispatch.
  - `run_eval()` runs the base model and base+skill arms on every prompt in an
    eval set, calls an LLM-as-judge to score each output against the prompt's
    expected traits, computes pass-rates, the **lift in percentage points**, and
    a bootstrap 95% CI (1000 resamples by default, deterministic seed).
  - `parse_score()` is strict: unparseable judge verdicts default to 0 (never
    silently coerced to a pass), so a flaky judge can never inflate the lift.
  - `save_report_to_skill_meta()` persists the report into `metadata.json` and
    surfaces the latest snapshot (`lift_pp`, `lift_ci_pp`, `base_pass_rate`,
    `skill_pass_rate`, `last_eval_set`, `last_eval_at`) at the top level for
    fast library-card reads. History is capped at 20 reports.
  - New CLI: `python -m skill_factory eval <slug> [--eval-set NAME]
    [--model X] [--judge-model Y] [--save] [--json] [--dry-run]`.
- **Three reference eval sets** under `evals/`:
  - `backend-api-engineer.yaml` (7 prompts about API design, idempotency,
    pagination, error contracts, version deprecation, authn/authz, rate
    limiting, schema evolution).
  - `quant-research-analyst.yaml` (6 prompts about Sharpe pitfalls, factor vs
    alpha claims, multiple comparisons, survivorship, look-ahead, capacity).
  - `financial-statement-analyst.yaml` (6 prompts about revenue vs cash,
    EBITDA vs cash flow, goodwill, lease capitalisation, quality of earnings,
    off-balance-sheet SPEs).
- **`SkillMeta` fields** (with defaults for backward compatibility):
  `eval_results`, `lift_pp`, `lift_ci_pp`, `base_pass_rate`, `skill_pass_rate`,
  `last_eval_set`, `last_eval_at`. Older `metadata.json` files without these
  fields round-trip cleanly.
- **Tests**: 42 new test cases covering bootstrap-CI math (zero lift, positive
  lift, negative lift, deterministic seeds, edge cases), judge score parsing
  (legal / unparseable / out-of-range), YAML loader, end-to-end runner flow
  with a scripted fake client, metadata persistence + history cap + older
  metadata round-trip, and the CLI default-set selection logic.
- **README**: a new "Measuring a skill (eval harness)" section with example
  output; the headline now calls out the eval feature.

### Why this matters
The whole pitch of the tool is "structured generation beats one-shot prompting."
Until now there was no way to measure that claim. The eval harness turns the
thesis into a number per skill, with a confidence interval — and the eval
prompts themselves accumulate as a defensible asset over time.

## [0.2.0] — 2026-09-16

Production-readiness release. The core package and the Streamlit UI are now
ready for multi-user / containerised deployments.

### Added
- `pyproject.toml` — installable as a package (`pip install -e .`); bundles
  `[pdf]` and `[dev]` extras.
- **Ruff** linting + formatting (`ruff check .`, `ruff format .`); pre-existing
  issues cleaned up.
- **CI workflow** (`.github/workflows/ci.yml`): ruff + pytest matrix on
  Python 3.10 / 3.11 / 3.12 + Docker build smoke test.
- **Dependabot** configuration for pip + GitHub Actions.
- **Structured logging** (`skill_factory.logging_setup`): stdlib `logging` with
  optional JSON output (`SKILL_FACTORY_LOG_FORMAT=json`). Honours
  `SKILL_FACTORY_LOG_LEVEL`.
- **Input safety** (`skill_factory.safety`): hard size caps on reference text
  and uploads, reserved-slug protection (Windows device names, `.`, `..`),
  path-traversal guard for preset paths. Overridable via env vars
  `SF_MAX_REF_TEXT_BYTES`, `SF_MAX_UPLOAD_BYTES`, `SF_MAX_NAME_LEN`.
- **Healthcheck** (`python -m skill_factory.healthcheck`): standalone
  exit-coded probe with JSON output for orchestrators (Docker `HEALTHCHECK`,
  k8s readiness probes, etc.).
- **CLI entrypoint** (`skill-factory` console script + `python -m
  skill_factory`): prints version, can dispatch to `healthcheck`.
- **Dockerfile** hardening: multi-stage build, non-root user, `HEALTHCHECK`
  directive wired to the in-tree healthcheck.
- **Makefile**: `make lint`, `make test`, `make test-cov`, `make docker-build`,
  `make run`, etc.
- **`.editorconfig`** + **`.dockerignore`**.
- **`requests>=2.32`** pinned as a runtime dependency (was lazily imported).
- New tests covering retries, exponential backoff, typed errors, the
  healthcheck, input limits, reserved slugs, path traversal, the smoke test
  (AppTest path resolution), and config edge cases.

### Changed
- **LLM client** (`skill_factory.llm_client`):
  - Configurable `timeout` (default 60s) and `max_retries` (default 3) on every
    API call.
  - Automatic retry with exponential backoff + full jitter for transient
    failures (HTTP 408/409/425/429/500/502/503/504, connection errors,
    read timeouts).
  - New `RetryableLLMError` subclass so the UI / batch runner can distinguish
    transient from permanent failures.
  - `list_models` now uses a shared `requests.Session` with `urllib3.Retry`,
    removing the previous one-shot connection.
  - `OpenAI` client is constructed with `timeout=` and `max_retries=0` (we own
    the retry policy now).
- **References module** rejects oversize uploads and combined reference text
  via `InputLimitError` *before* extraction.
- **Batch page** falls back to a safe slug if the configured name pattern
  produces a reserved name.
- **`test_app_smoke.py`**: pass an absolute `app.py` path so `AppTest.from_file`
  resolves correctly regardless of the working directory pytest is invoked from.

## [0.1.0] — 2026-06-09

Initial public release.

- Multi-provider support: OpenRouter, MiniMax, Kimi/Moonshot, custom
  OpenAI-compatible endpoints.
- Multi-stage generation pipeline: spec → outline → draft → refine → validate.
- Hierarchical skills with specialist overlays.
- Batch generator driven by JSON presets.
- Filesystem-first versioned skill library (`skills/<slug>/v<n>/`).
- Validator + meta-prompt enforcing SKILL.md best practices.
- Testing playground with thumbs/notes recorded against each skill version.
- Reference-material ingestion (`.txt`/`.md`, `.pdf` when `pypdf` is available).
- Streamlit UI with Config / New Skill / Library / Editor / Playground / Batch
  pages.
- MIT licensed.
