# 🏭 LLM Skill Factory

A domain-agnostic **Skill Studio** for rapidly authoring high-quality, production-ready
`SKILL.md` files — modular expert system prompts that make an LLM dramatically better at a
specific kind of work.

Build a skill for a **backend engineer**, a **quant researcher**, a **robotics designer**, a
**financial analyst**, or anything else. The tool is generic by design and works with your choice
of LLM provider — **OpenRouter**, **MiniMax**, **Kimi (Moonshot)**, or any OpenAI-compatible
endpoint (bring your own API key).

> The leverage comes from a strong built-in **meta-skill** plus a **multi-stage,
> human-in-the-loop** pipeline — structured generation beats one-shot prompting.

> 🆕 **New to Python or the command line?** Follow the step-by-step
> **[Installation Guide → INSTALL.md](INSTALL.md)**, which walks you through everything from zero.

> 🚀 **Deploying?** See **[Production deployment](#production-deployment)** for the hardened
> image, health probe, operational env vars, and auth notes. The architecture map is in
> **[ARCHITECTURE.md](ARCHITECTURE.md)** and the change log in **[CHANGELOG.md](CHANGELOG.md)**.

---

## Features

- **Multi-stage generation pipeline** with approval gates: *outline → (optional) context →
  draft → refine → validate → save*.
- **Skill types**: domain-expert, specialist, workflow, hybrid.
- **Hierarchical skills**: a base skill plus specialist **overlays** that extend it.
- **Batch generator**: produce one overlay per entity from a base skill (entities from a JSON
  preset or pasted list).
- **Versioned, filesystem-first library**: every skill is plain `SKILL.md` + `metadata.json`,
  git-friendly and inspectable.
- **Editor** with live markdown preview, a best-practice **validator**, and targeted LLM
  "refine this section".
- **Multi-provider**: OpenRouter, MiniMax, Kimi/Moonshot, or any custom OpenAI-compatible endpoint
  — switch in the UI; keys are remembered per provider.
- **Testing playground**: run a skill as a system prompt against any model and record thumbs/notes.
- **Reference material ingestion**: paste text or upload files (`.txt`/`.md`; `.pdf` when `pypdf`
  is available).
- **Export**: download a skill as a zip (with a usage guide) or copy it into another app.

---

## Quickstart

*First time with Python/terminals? Use the gentler **[step-by-step guide](INSTALL.md)** instead.*

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure a key for the provider you want (either of these)
cp .env.example .env        # then set OPENROUTER_API_KEY / MINIMAX_API_KEY / MOONSHOT_API_KEY
# ...or just paste the key into the Config page at runtime (kept in-session only)

# 3. Run
streamlit run app.py
```

Then open the app, go to **Config**, pick your **Provider**, paste its key (if not using `.env`),
optionally click **Fetch models**, and head to **New Skill**.

### Docker

```bash
docker build -t skill-factory .
docker run -p 8501:8501 -e OPENROUTER_API_KEY=sk-or-... skill-factory
# or: -e LLM_PROVIDER=kimi -e MOONSHOT_API_KEY=...   /   -e LLM_PROVIDER=minimax -e MINIMAX_API_KEY=...
```

---

## How it works

The **New Skill** wizard walks three gates, with you in control at each step:

1. **Specify** — name, type, trigger description, domain, tags, requirements, tone, token budget,
   optional reference material, and an optional base skill to extend.
2. **Outline** — the model proposes a section outline; you edit it freely before drafting.
3. **Draft** — the model writes the full `SKILL.md`. Preview it, run the validator, then save it
   as a version (or open it in the **Editor** to refine sections via the LLM).

Open any saved skill in the **Editor** to hand-edit, re-validate, refine with the LLM, and save
new versions. Try it in the **Playground**, or generate a family of specialists in **Batch**.

### What makes a good `SKILL.md`?

The built-in meta-skill enforces these conventions (and the validator checks them):

- **Frontmatter**: a kebab-case `name` and a `description` that states *what the skill does* **and**
  *when to use it* (trigger conditions). The description drives activation — make it specific.
- **Imperative voice** aimed at the model that will run the skill ("Always…", "Check the
  following…").
- **Only non-obvious, high-value knowledge** — don't restate what a capable model already knows.
- **Actionable** frameworks, checklists, and output templates; at least one concrete example.
- **Progressive disclosure** — keep the main file focused; push deep detail into references.

See ready-made examples in [`examples/`](examples/): `backend-api-engineer`,
`quant-research-analyst`, `financial-statement-analyst`.

---

## Storage layout

```
skills/
└── <skill-name>/
    ├── v1/
    │   ├── SKILL.md
    │   └── metadata.json
    └── v2/
        └── ...
```

`skills/` is gitignored by default (your generated skills are yours). `metadata.json` records
type, tags, domain, entities, base skill, version notes, the model used, and playground results.

## Presets (for batch generation)

Presets are **generic data** under [`presets/`](presets/). A preset is a JSON file listing named
entities; the batch generator turns each into a specialist overlay of a base skill. Ships with
`qse-banks.json` purely as an example — add your own (`s-and-p-500.json`, `microservices.json`,
`robot-platforms.json`, …).

---

## Providers

All providers use the OpenAI-compatible Chat Completions API (`POST {base_url}/chat/completions`),
so one client drives them all — only the base URL, key, and model ids differ. Pick a provider on
the **Config** page; the base URL and model are editable (handy for regional endpoints), and keys
are remembered per provider.

| Provider | Key env var | Default base URL | Example model ids |
|---|---|---|---|
| **OpenRouter** | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `anthropic/claude-sonnet-4.6`, `openai/gpt-4o` |
| **MiniMax** | `MINIMAX_API_KEY` | `https://api.minimax.io/v1` | `MiniMax-M3`, `MiniMax-M2.1`, `MiniMax-Text-01` |
| **Kimi (Moonshot)** | `MOONSHOT_API_KEY` | `https://api.moonshot.ai/v1` | `kimi-k2.6`, `kimi-k2.5`, `moonshot-v1-8k` |
| **Custom** | `LLM_API_KEY` | *(you set it)* | any |

Regional endpoints: MiniMax China → `https://api.minimax.chat/v1`; Moonshot China →
`https://api.moonshot.cn/v1` (set in **Advanced**). Base URLs and OpenAI-compatibility were
verified against each provider's docs (June 2026). **Model ids evolve** — older Kimi ids
(`kimi-k2-*`, `kimi-latest`) were retired in 2026, so type the model you want or click **Fetch
models**. OpenRouter also proxies many MiniMax/Moonshot models (e.g. `minimax/...`,
`moonshotai/...`) if you prefer a single key.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `LLM_PROVIDER` | Which provider to use (`openrouter`/`minimax`/`kimi`/`custom`) | `openrouter` |
| `OPENROUTER_API_KEY` / `MINIMAX_API_KEY` / `MOONSHOT_API_KEY` / `LLM_API_KEY` | Per-provider key | — |
| `<PROVIDER>_DEFAULT_MODEL` | Default model, e.g. `OPENROUTER_DEFAULT_MODEL`, `KIMI_DEFAULT_MODEL` | provider default |
| `APP_TITLE` / `APP_URL` | Attribution sent to OpenRouter | — |
| `SKILLS_DIR` | Where skills are written | `./skills` |

Each value resolves as: **in-app input → environment → provider default**, and keys are never
written to disk by the app.

---

## Development

```bash
make dev               # pip install -e ".[dev,pdf]"
make lint              # ruff check
make format            # ruff format
make test              # pytest
make test-cov          # pytest + coverage
make typecheck         # mypy on skill_factory/
```

The core package [`skill_factory/`](skill_factory/) contains all logic and has **no Streamlit
imports**, so it is fully unit-testable and reusable outside the UI. The Streamlit layer lives in
[`ui/`](ui/) and [`app.py`](app.py).

## Production deployment

This project ships a hardened 0.2+ image. Run it however you prefer:

```bash
# 1. Container (recommended): non-root user, multi-stage build, in-tree HEALTHCHECK.
docker build -t skill-factory:0.2 .
docker run --rm -p 8501:8501 \
    -e LLM_PROVIDER=openrouter \
    -e OPENROUTER_API_KEY=sk-or-... \
    skill-factory:0.2

# 2. Bare metal / venv
pip install -e .
streamlit run app.py

# 3. CLI version + health probe
python -m skill_factory               # prints the version
python -m skill_factory healthcheck   # full check (exit 0 = ready)
```

What "production-ready" means in this repo (full detail in
[`SECURITY.md`](SECURITY.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md)):

| Concern              | Implementation                                                                                                    |
|----------------------|-------------------------------------------------------------------------------------------------------------------|
| API call resilience  | Configurable timeout + retry with exponential backoff + jitter on transient HTTP / network failures (`LLMClient`).|
| Typed errors         | `RetryableLLMError` distinguishes transient from permanent failures for the UI / batch runner.                    |
| Input limits         | Hard size caps on reference text (`SF_MAX_REF_TEXT_BYTES`, default 200 KB) and uploads (default 5 MB).             |
| Path safety          | Reserved-slug protection (Windows device names, `.`, `..`), path-traversal guard, kebab-case enforcement.         |
| Logging              | stdlib `logging` via `skill_factory.logging_setup`; JSON format for container aggregators.                        |
| Health probe         | `python -m skill_factory.healthcheck` — Docker `HEALTHCHECK`-compatible, JSON output, `--strict` for prod.        |
| Container hardening  | Multi-stage `Dockerfile`, non-root user (`uid 10001`), `HEALTHCHECK` directive wired to the in-tree module.        |
| CI                   | GitHub Actions: ruff + pytest matrix on Python 3.10 / 3.11 / 3.12 + Docker build smoke.                          |
| Dependency updates   | Dependabot configured for pip + GitHub Actions, weekly, grouped.                                                  |

### Operational knobs

All of these are environment variables with sensible defaults; you do not need to set them unless
your deployment differs.

| Env var                     | Purpose                                            | Default |
|-----------------------------|----------------------------------------------------|---------|
| `LLM_PROVIDER`              | `openrouter` / `minimax` / `kimi` / `custom`       | `openrouter` |
| `LLM_TIMEOUT`               | Per-request HTTP timeout in seconds                | `60`    |
| `LLM_MAX_RETRIES`           | Retry attempts (exponential backoff + jitter)      | `3`     |
| `SF_MAX_REF_TEXT_BYTES`     | Reject oversized pasted / uploaded reference text  | `204800` (200 KB) |
| `SF_MAX_UPLOAD_BYTES`       | Reject oversized file uploads                      | `5242880` (5 MB) |
| `SF_MAX_NAME_LEN`           | Reject oversized skill slugs                       | `64`    |
| `SKILL_FACTORY_LOG_LEVEL`   | `DEBUG` / `INFO` / `WARNING` / `ERROR`             | `WARNING` |
| `SKILL_FACTORY_LOG_FORMAT`  | `plain` or `json`                                  | `plain` |
| `SKILLS_DIR`                | Where skills are written                           | `./skills` |

### Auth

The Streamlit app is **single-tenant**. If you expose it beyond localhost, put it behind your
existing reverse-proxy / auth layer (nginx, oauth2-proxy, Cloudflare Access, etc.). Out of the box
the app binds to `0.0.0.0:8501` and trusts any client that can reach the port.

## Roadmap (deferred)

The interfaces/seams for these are in place; they were intentionally left out of v1:

- **Web research provider** (Tavily/Brave) for automatic context injection — see
  `skill_factory/research.py`.
- **SQLite search index** for very large libraries (filesystem + filters cover smaller ones).
- Richer test-result analytics dashboards.

## License

MIT — see [LICENSE](LICENSE).
