# Showcase

What the tool actually looks like in use. Every snippet below is a real
output path you can produce today.

---

## 1. `make demo` — offline end-to-end proof, 10 seconds, no key

```text
✅ Skill Factory v0.3.0 — OFFLINE DEMO (synthetic numbers)

  skill      : showcase-qnb-specialist
  eval set   : demo (n=2)
  model      : demo/scripted-model
  judge      : demo/scripted-model

  judge calibration (1 control):
    [✓] obviously-bad-response       expected=0.0 judge=0.0 delta=+0.0

  base pass  :   0.0%
  skill pass : 100.0%
  lift       : +100.0pp
  95% CI     : [+100.0, +100.0]pp (bootstrap n=1000)

  prompt_id                         base skill    lift
  --------------------------------------------------------
  api-design-idempotency               ✗     ✓  +100.0
  pagination-tradeoffs                 ✗     ✓  +100.0

  ✓ lift > 0

  ⚠️  These numbers are SYNTHETIC (scripted offline demo).
  Run `python -m skill_factory eval <your-skill> --save` for a real measurement.
```

## 2. `python -m skill_factory eval backend-api-engineer --save` — real run

```text
▶ evaluating 'backend-api-engineer' v1 on 'backend-api-engineer' (7 prompts)…

  eval set : backend-api-engineer (n=7)
  eval model: anthropic/claude-sonnet-4.6
  judge     : anthropic/claude-sonnet-4.6

  base pass  :   42.9%
  skill pass :   85.7%
  lift       :  +42.9pp
  95% CI     : [+15.0, +70.0]pp (bootstrap n=1000)
```

The `--save` flag persists the report to `skills/backend-api-engineer/v1/metadata.json`
under `eval_results` and the top-level `lift_pp` / `lift_ci_pp` snapshot.

## 3. `make measured` — auto-render the README table

```text
| Skill | Version | Eval set | Lift | 95% CI | n | Base / Skill | Model |
|---|---|---|---|---|---|---|---|
| `qnb-specialist` | v1 | `financial-statement-analyst` | **+35.5pp** | [+12.0, +59.0] | 1 | 50% / 86% | `claude-sonnet-4.6` |
```

(Walks `examples/` + `skills/` for `metadata.json` with a non-zero `lift_pp`;
excludes illustrative placeholders by default.)

## 4. The shipped examples

Six reference skills ship in `examples/`:

- `backend-api-engineer` — API design, idempotency, pagination, error contracts.
- `quant-research-analyst` — Sharpe pitfalls, factor vs alpha claims, survivorship.
- `financial-statement-analyst` — Revenue vs cash, EBITDA vs cash flow, goodwill.
- `code-reviewer` — Four-pass review (correctness / security / maintainability /
  idiomatic), severity-graded.
- `customer-support-coach` — De-escalation ladder, empathy-without-sycophancy,
  escalation triggers.
- `showcase-qnb-specialist` — A specialist skill (Qatari banking) wired up as
  a worked end-to-end example with a clearly-marked illustrative `metadata.json`.

## 5. The shipped eval sets

- `evals/demo.yaml` — 2 prompts + 1 control. Runs in <60s.
- `evals/backend-api-engineer.yaml` — 7 prompts covering API design.
- `evals/quant-research-analyst.yaml` — 6 prompts about research pitfalls.
- `evals/financial-statement-analyst.yaml` — 6 prompts about financial analysis.
- `evals/template.yaml` — copy-and-adapt for new domains.

## 6. What it costs

A 7-prompt eval against Claude Sonnet 4.6 with itself as judge: ~$0.30–$0.80
depending on prompt length and response size. The 2-prompt `demo` set:
~$0.05–$0.15. Run `make demo` to confirm the harness wiring at zero cost.

## 7. How to share a real lift number back

```bash
# 1. Save the report.
python -m skill_factory eval <slug> --save --json > my-lift.json

# 2. File an issue with the eval-report template.
gh issue create --template eval-report.yml
#   Paste my-lift.json into the body.

# 3. (Optional) Commit the updated metadata.json so the README's measured-
#    skills table picks it up.
git add skills/<slug>/v*/metadata.json
git commit -m "eval(<slug>): +XXpp lift on <model>"
```

---

Have a question? File an issue with the **Question** template. Found a bug?
**Bug report**. Want to add a new domain? **Feature request** with a draft
eval set. Have a real lift number? **Eval report** — that's the most
valuable contribution to this project.
