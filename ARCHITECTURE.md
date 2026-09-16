# Architecture

A short tour of how **LLM Skill Factory** is put together. Read this before
making structural changes — it should pay for itself the first time you need
to figure out where a new feature belongs.

## Goals

1. **Domain-agnostic core.** Everything in `skill_factory/` knows nothing
   about any particular business domain. The same code can author a
   `backend-api-engineer` skill or a `qnb-specialist` overlay depending only
   on the supplied `SkillSpec`.
2. **Provider-agnostic LLM.** Every supported provider speaks OpenAI's Chat
   Completions API; `skill_factory/llm_client.py` is a thin wrapper with a
   uniform `complete(system=, user=)` interface.
3. **Filesystem-first, git-friendly storage.** A skill is plain `SKILL.md` +
   `metadata.json` inside a `v<n>/` folder. No database.
4. **Testable core.** `skill_factory/` has **no** Streamlit imports. The UI
   lives in `ui/` and can be swapped out without touching the core.

## Layers

```
              ┌──────────────────────────────┐
              │         app.py               │  ← Streamlit entrypoint
              └─────────────┬────────────────┘
                            │
              ┌─────────────▼────────────────┐
              │             ui/              │  ← pages, state, helpers
              │  config | new | library |    │
              │  editor | playground | batch │
              └─────────────┬────────────────┘
                            │ (no Streamlit imports below)
              ┌─────────────▼────────────────┐
              │       skill_factory/         │  ← core package
              │                              │
              │  config     providers        │
              │  llm_client models           │
              │  meta_prompts pipeline       │
              │  frontmatter  validator      │
              │  skill_store  exporter       │
              │  references  presets         │
              │  research   safety           │
              │  logging_setup healthcheck   │
              └─────────────┬────────────────┘
                            │
              ┌─────────────▼────────────────┐
              │    External LLM providers    │
              │  OpenRouter | MiniMax |      │
              │  Kimi/Moonshot | custom      │
              └──────────────────────────────┘
```

## Module map

| Module | Purpose |
|---|---|
| `config.py` | Resolves Settings (overrides → env → provider defaults → built-ins). Idempotent `.env` loading. |
| `providers.py` | Registry of `Provider` dataclasses. UI is the only place that should mutate this. |
| `llm_client.py` | `LLMClient` over the OpenAI SDK; retry + backoff; typed errors (`LLMError`, `RetryableLLMError`). |
| `models.py` | Pure dataclasses (`SkillSpec`, `SkillMeta`, `TestResult`, `GenerationResult`, `ValidationReport`). |
| `frontmatter.py` | Tiny YAML helpers shared by validator/store/exporter. |
| `validator.py` | Best-practice lint rules for a `SKILL.md` (errors / warnings / suggestions). |
| `meta_prompts.py` | The "meta-skill" — system prompts teaching the model to author good skills. |
| `pipeline.py` | Pure orchestration: `plan_outline`, `generate_draft`, `refine_section`, `generate_overlay`. |
| `skill_store.py` | Filesystem storage (`skills/<slug>/v<n>/`). Atomic per-version writes. |
| `exporter.py` | Zip a skill, copy it to another directory, generate a `USAGE.md`. |
| `references.py` | Read text/markdown/PDF uploads; combine into a context blob (size-capped). |
| `presets.py` | JSON-driven entity lists for batch generation. |
| `research.py` | Protocol seam for future web-research providers. |
| `safety.py` | Input limits, reserved-slug protection, path-traversal guard. |
| `logging_setup.py` | stdlib `logging` with optional JSON output. |
| `healthcheck.py` | Standalone smoke probe for orchestrators. |
| `__main__.py` | CLI entrypoint: `python -m skill_factory [healthcheck]`. |

## Data flow (New Skill)

```
SkillSpec ──▶ outline stage ──▶ Outline ──▶ draft stage ──▶ SKILL.md ──┐
                                       │                              │
                                       └──── reference material ◀────┘
                                                                       │
                                                                       ▼
                                                                validator (preview)
                                                                       │
                                                                       ▼
                                                          SkillStore.save_new_version
                                                                       │
                                                                       ▼
                                                         skills/<slug>/v1/{SKILL.md, metadata.json}
```

## Data flow (Editor refine)

```
loaded SKILL.md  ──▶ editor_content (text_area)
                       │
                       ├──▶ validate_skill_md ──▶ UI render (errors / warnings / suggestions)
                       │
                       └──▶ pipeline.refine_section ──▶ LLMClient.chat ──▶ cleaned markdown
                                                                                  │
                                                                                  ▼
                                                              _pending_editor_content (deferred apply)
```

## Retry / error model

```
LLMClient.chat()
    │
    ├──▶ OpenAI SDK raises APIStatusError / APIConnectionError / APITimeoutError / RateLimitError
    │
    ├──▶ _is_retryable(exc) decides:
    │       yes  → exponential backoff w/ jitter, try again (≤ max_retries)
    │       no   → wrap in LLMError, raise immediately
    │
    └──▶ exhausted retries on a retryable cause → RetryableLLMError(...)
```

Status codes considered retryable: 408, 409, 425, 429, 500, 502, 503, 504.
Everything else (400, 401, 403, 404, ...) is a permanent failure.

## Configuration precedence

```
UI input (session state)
    └─▶ per-provider dict (provider_keys, provider_models, provider_base_urls)
            └─▶ environment variable (OPENROUTER_API_KEY, MINIMAX_API_KEY, ...)
                    └─▶ provider default (built into providers.py)
                            └─▶ built-in default
```

API keys are never written to disk by the app. Set them in `.env` for
persistence, or paste them in the **Config** page for the session only.

## Storage layout

```
skills/                       # gitignored by default
└── <skill-name>/
    ├── v1/
    │   ├── SKILL.md
    │   └── metadata.json
    └── v2/
        ├── SKILL.md
        └── metadata.json
```

`metadata.json` is the persisted `SkillMeta` (name, description, type, tags,
domain, base_skill, version_notes, model, created_at, test_results). It is
written atomically and never rewritten except by `update_meta` (playground
results).

## Threading model

- The Streamlit app is single-process, single-user. There is no shared state
  across sessions beyond the filesystem.
- The `Batch` page generates overlays serially (one LLM call at a time) to
  respect provider rate limits. Parallelism can be added later behind the
  `pipeline.generate_overlay` seam — keep it a pure function and wrap the
  iteration with a thread/process pool when needed.
- The `LLMClient` is **not** thread-safe at the per-request level (the OpenAI
  SDK holds its own state). Build one client per worker.

## Adding a new provider

1. Add an entry to `PROVIDERS` in `skill_factory/providers.py`.
2. If the base URL is unusual, make it editable in the UI (already the case
   via `provider_base_urls`).
3. If the provider exposes a `/models` endpoint, set
   `supports_model_listing=True` (default).
4. Add tests under `tests/test_providers.py`.

## Adding a new UI page

1. Create `ui/<page>_page.py` exposing `def render() -> None: ...`.
2. Add a `PAGE_*` constant in `ui/__init__.py`, append it to `PAGES`.
3. Wire the route in `app.py`.
4. Extend `tests/test_app_smoke.py:PAGES` so the new page gets a smoke check.
