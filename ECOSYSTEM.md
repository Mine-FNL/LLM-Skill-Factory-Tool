# The Mine-FNL SKILL.md ecosystem

This page maps every component in the open SKILL.md toolchain we maintain.
Pick the layer that matches your problem.

## At a glance

```
┌──────────────────────────────────────────────────────────────────────┐
│ Authoring                                                            │   │
│   LLM-Skill-Factory-Tool  ← Streamlit UI + CLI for skill authoring   │   │
│                              and offline eval                        │   │
├──────────────────────────────────────────────────────────────────────┤
│ Validation                                                          │   │
│   skillmd-lint           ← Python CLI: 22 rules + JSON Schema        │   │
│   skillmd-lint-action    ← Official GitHub Action                    │   │
│   skillmd-lint-vscode    ← VS Code extension (inline diagnostics)    │   │
├──────────────────────────────────────────────────────────────────────┤
│ Browser                                                             │   │
│   site/index.html        ← Browser-side mirror of the rule engine    │   │
│                              (LLM-Skill-Factory-Tool/site/)          │   │
├──────────────────────────────────────────────────────────────────────┤
│ Spec                                                                │   │
│   agentskills.io         ← Open SKILL.md format spec                 │   │
└──────────────────────────────────────────────────────────────────────┘
```

## One-line summaries

| Repo | One-liner |
|------|-----------|
| **[LLM-Skill-Factory-Tool](https://github.com/Mine-FNL/LLM-Skill-Factory-Tool)** | Author, evaluate, and run SKILL.md files end-to-end. Streamlit UI + CLI. Includes `make demo` for a 10-second offline proof. |
| **[skillmd-lint](https://github.com/Mine-FNL/skillmd-lint)** | Pure-Python linter for SKILL.md files. 22 rules (10 errors, 13 warnings) + a published JSON Schema. No API key, no network at runtime. |
| **[skillmd-lint-action](https://github.com/Mine-FNL/skillmd-lint-action)** | Official GitHub Action wrapping `skillmd-lint`. 7 inputs, 2 outputs, GitHub Actions annotations on each finding. |
| **[skillmd-lint-vscode](https://github.com/Mine-FNL/skillmd-lint-vscode)** | *(in progress)* VS Code extension with live diagnostics + safe auto-fixes. |
| **[agentskills.io](https://agentskills.io)** | The open SKILL.md format spec. Not ours; we conform to it. |

## Why these layers

The open SKILL.md spec is portable across Claude Code, Claude API, ChatGPT,
OpenAI Codex, and the broader agent ecosystem — that's its biggest asset.
Every tool in this list exists to make it **easier to author**, **easier to
validate**, and **easier to ship** SKILL.md files without violating the spec.

The linter is the centerpiece: it's the smallest piece that's still useful
on its own, and it's what every other layer either calls (the GitHub Action,
the VS Code extension) or mirrors (the browser playground).

## Cross-pollination

Every repo cross-links the others:

- `skillmd-lint` README links to `skillmd-lint-action` and
  `LLM-Skill-Factory-Tool`.
- `skillmd-lint-action` README links back to `skillmd-lint`.
- `LLM-Skill-Factory-Tool/SHOWCASE.md` mentions `skillmd-lint` and the
  browser playground.

## Status (Sep 2026)

| Layer | Version | Tests | Coverage | Notes |
|-------|---------|-------|----------|-------|
| skillmd-lint | 1.1.1 | 100 | 91% | Pure-Python, cross-platform, JSON Schema |
| skillmd-lint-action | 1.0.0 | 3 fixtures + CI build matrix | n/a | Docker-based, 7 inputs, 2 outputs |
| LLM-Skill-Factory-Tool | 0.4.0 | 166 | 79% | Streamlit + CLI, eval harness |
| Browser playground | (matches skillmd-lint) | 15 parity tests | n/a | Same 22 rules in JS, no build |
| skillmd-lint-vscode | 0.1.0 (in progress) | TBD | TBD | TypeScript, vsce-packaged |

## What we don't ship

- **A web app** beyond the playground. Authoring UI lives in the
  Streamlit app inside `LLM-Skill-Factory-Tool`.
- **A SaaS**. Everything runs locally. The eval harness can call hosted
  models via standard `anthropic/` / `openai/` prefixed names but there is
  no managed backend.

## License

All repos are MIT. The SKILL.md spec at agentskills.io is owned by its
authors — we conform to it but don't fork it.