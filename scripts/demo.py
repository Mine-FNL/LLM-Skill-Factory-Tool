"""End-to-end offline demo of the eval harness.

This runs the full ``run_eval`` pipeline against one of the shipped example
skills with a deterministic scripted "fake model". The fake model produces
realistic, hand-crafted outputs that vary by prompt — so the eval numbers
look like a real run, but every line is clearly labelled as synthetic.

Why this exists:
- Visitors can ``make demo`` and see the tool actually work end-to-end in
  ~10 seconds, no API key required.
- Reviewers / CI can verify the harness wiring without network access.
- First-time users get a concrete picture of the output format.

Run::

    make demo
    # or:
    python scripts/demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

from skill_factory.eval import EvalSet, run_eval
from skill_factory.eval.loader import DEFAULT_EVALS_DIR, load_eval_set
from skill_factory.llm_client import LLMClient
from skill_factory.skill_store import SkillStore

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILL = REPO_ROOT / "examples" / "showcase-qnb-specialist"
DEFAULT_EVAL_SET = "demo"

# Synthetic but realistic responses keyed by prompt id. These are the
# "base model" outputs (a competent general-purpose model without the
# specialist context). Keyed by the prompt ids in evals/demo.yaml.
BASE_RESPONSES: dict[str, str] = {
    "api-design-idempotency": (
        "For a POST /transfers endpoint, you'd return 201 Created on success with the "
        "transfer ID in the response body. If a client retries after a network blip, "
        "the server should just create the duplicate transfer — that's the client's "
        "responsibility to handle."
    ),
    "pagination-tradeoffs": (
        "Use offset pagination with a reasonable default page size (e.g. ?page=1&per_page=50). "
        "It's simpler for clients to implement."
    ),
}

# Synthetic "skill-on" responses — what the specialist produces when given
# the right context. Longer, more specific, citing actual best practice.
SKILL_RESPONSES: dict[str, str] = {
    "api-design-idempotency": (
        "Design a POST /transfers endpoint with an Idempotency-Key header (RFC draft). "
        "On first request: validate, debit, credit, persist with status 201 Created. "
        "On retry with the same key: return the *original* response body and status, "
        "do not re-execute. This is at-least-once delivery semantics — required for "
        "any financial system. 200/201 are both acceptable; 201 if a new resource was "
        "created, 200 if you're returning the cached result. Include an "
        "'Idempotency-Replayed: true' header so the client knows it was a replay."
    ),
    "pagination-tradeoffs": (
        "For 10M-row invoices, use cursor pagination (`?cursor=<opaque>&limit=50`). "
        "Offset pagination has three real problems at this scale: (1) deep offsets "
        "are O(n) on most databases — page 100,000 of 50/page scans 5M rows; "
        "(2) offset is unstable under concurrent inserts — the same offset can "
        "return duplicates or skip rows; (3) counting total rows for a `total_count` "
        "field forces a second O(n) query. Cursors (typically the row's indexed "
        "created_at + id) are stable, O(log n), and don't need a count."
    ),
}

# Synthetic judge scores: aligned with each prompt id in evals/demo.yaml.
# Format: (base_score, skill_score).
JUDGE_SCORES: dict[str, tuple[float, float]] = {
    "api-design-idempotency": (0.0, 1.0),
    "pagination-tradeoffs": (0.0, 1.0),
}


class ScriptedClient:
    """A deterministic 'fake model' that returns canned outputs.

    Behaves like ``LLMClient`` for the eval harness's purposes: it exposes
    ``default_model``, ``complete(system=, user=, model=)``, and is callable
    by :func:`run_eval`. Returns scripted responses keyed by user-prompt
    content; falls back to a generic placeholder for anything unrecognised.
    """

    default_model = "demo/scripted-model"

    def __init__(self, eval_set_name: str):
        self._eval_set_name = eval_set_name
        self._judge_queue: list[float] = []
        self._arm_counter: dict[str, int] = {}  # prompt_id -> call count (0 = base, 1 = skill)

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.0,
        **_: Any,
    ) -> Any:
        from unittest.mock import MagicMock

        m = MagicMock()
        # Judge calls have a specific structure: user contains "## Expected traits"
        # AND "## Response to score". Detect and use the scripted judge queue.
        is_judge = "## Expected traits" in user and "## Response to score" in user
        if is_judge:
            score = self._judge_queue.pop(0)
            m.content = str(score)
            return m

        # Generation call. The runner iterates prompts and calls generation
        # + judge twice per prompt: base then skill. We track per-prompt call
        # count and toggle arms on the second generation call.
        prompt_id = self._extract_prompt_id(user)
        call_n = self._arm_counter.get(prompt_id, 0)
        self._arm_counter[prompt_id] = call_n + 1
        is_skill_arm = (
            call_n >= 1
        )  # 0=base generation, 1=skill generation, 2+=extra (shouldn't happen)
        responses = SKILL_RESPONSES if is_skill_arm else BASE_RESPONSES
        m.content = responses.get(
            prompt_id,
            f"(synthetic demo response for prompt {prompt_id or '?'} on "
            f"{'skill arm' if is_skill_arm else 'base arm'})",
        )
        return m

    @staticmethod
    def _extract_prompt_id(user: str) -> str:
        # Eval harness sends the user prompt verbatim. We look for known
        # prompt-id keywords by lowercased whitespace-converted ids.
        user_low = user.lower()
        for pid in BASE_RESPONSES:
            needle = pid.replace("-", " ")
            if needle in user_low:
                return pid
        return ""

    def prime_judge_queue(self, eval_set: EvalSet) -> None:
        """Populate the judge queue in the exact order ``run_eval`` consumes it.

        ``run_eval`` calls the judge in two phases:

        1. ``run_controls`` — one judge call per control prompt.
        2. Per prompt in the eval set: base-generation, judge-base,
           skill-generation (if a skill is provided), judge-skill.

        We pre-queue scores in that exact order.
        """

        self._judge_queue = []
        # 1. Controls — for the shipped demo set the only control is
        #    ``obviously-bad-response`` with expected_score=0.0, so the judge
        #    must score 0.0 for the demo's calibration check to pass.
        for control in eval_set.controls:
            if control.expected_score <= 0.0:
                self._judge_queue.append(0.0)
            else:
                self._judge_queue.append(control.expected_score)
        # 2. Per-prompt scores (base then skill).
        for prompt in eval_set.prompts:
            base_score, skill_score = JUDGE_SCORES.get(prompt.id, (0.0, 0.0))
            self._judge_queue.append(base_score)
            self._judge_queue.append(skill_score)


def _print_human_summary(report: Any, skill_slug: str) -> None:
    print("\u2705 Skill Factory v0.3.0 \u2014 OFFLINE DEMO (synthetic numbers)")
    print()
    print(f"  skill      : {skill_slug}")
    print(f"  eval set   : {report.eval_set_name} (n={report.n_prompts})")
    print(f"  model      : {report.eval_model}")
    print(f"  judge      : {report.judge_model}")
    print()
    if report.control_results:
        print(f"  judge calibration ({len(report.control_results)} control):")
        for c in report.control_results:
            ok = "\u2713" if c["within_tolerance"] else "\u2717"
            print(
                f"    [{ok}] {c['id']:<28} expected={c['expected_score']:.1f} "
                f"judge={c['judge_score']:.1f} delta={c['delta']:+.1f}"
            )
        if not report.judge_calibration_ok():
            print()
            print("  WARNING: judge is miscalibrated (expected in this demo, calibration is off).")
        print()

    print(f"  base pass  : {report.base_pass_rate:>6.1%}")
    print(f"  skill pass : {report.skill_pass_rate:>6.1%}")
    print(f"  lift       : {report.lift_pp:+6.1f}pp")
    print(
        f"  95% CI     : [{report.lift_ci_low_pp:+5.1f}, {report.lift_ci_high_pp:+5.1f}]pp "
        f"(bootstrap n={report.n_bootstrap})"
    )
    print()
    print(f"  {'prompt_id':<32} {'base':>5} {'skill':>5}  {'lift':>6}")
    print("  " + "-" * 56)
    for pr in report.prompt_results:
        base_mark = "\u2713" if pr.base_passed else "\u2717"
        skill_mark = "\u2713" if pr.skill_passed else "\u2717"
        per_lift = (pr.skill_score - pr.base_score) * 100.0
        print(f"  {pr.prompt_id:<32} {base_mark:>5} {skill_mark:>5}  {per_lift:+6.1f}")
    print()
    verdict = (
        "\u2713 lift > 0"
        if report.lift_pp > 0 and report.lift_ci_low_pp > 0
        else "\u2248 no clear lift (CI overlaps 0)"
        if report.lift_ci_low_pp <= 0 <= report.lift_ci_high_pp
        else "\u2717 lift < 0"
    )
    print(f"  {verdict}")
    print()


def main(argv: list[str] | None = None) -> int:
    eval_set_name = argv[0] if argv and argv[0] else DEFAULT_EVAL_SET

    # Build a temp skills dir with the showcase skill loaded.
    tmp = Path(tempfile.mkdtemp(prefix="skill_factory_demo_"))
    store = SkillStore(tmp)
    skill_slug = "showcase-qnb-specialist"
    skill_src = (DEFAULT_SKILL / "SKILL.md").read_text(encoding="utf-8")
    # ``run_eval`` only needs the body, but we still write the full file so
    # the demo also exercises ``SkillStore.save_new_version``.
    from skill_factory.models import SkillMeta, SkillSpec  # local import for clarity

    spec = SkillSpec(name=skill_slug, description="Demo skill (QNB specialist).")
    meta = SkillMeta.from_spec(spec, version=1, model="demo/scripted-model")
    store.save_new_version(skill_slug, skill_src, meta)

    eval_set_path = DEFAULT_EVALS_DIR / f"{eval_set_name}.yaml"
    if not eval_set_path.exists():
        print(f"error: eval set '{eval_set_name}' not found at {eval_set_path}", file=sys.stderr)
        return 2
    eval_set = load_eval_set(eval_set_name)

    # Use a real LLMClient (so run_eval flows through the retry / backoff path),
    # but inject our scripted client as the underlying network call by monkey-patching
    # its complete() method.
    client = LLMClient(
        api_key="demo-no-key-needed",
        base_url="https://demo.invalid/v1",
        default_model="demo/scripted-model",
        timeout=10.0,
        max_retries=0,
    )
    scripted = ScriptedClient(eval_set_name)
    scripted.prime_judge_queue(eval_set)
    client.complete = scripted.complete  # type: ignore[method-assign]

    report = run_eval(
        client,
        eval_set,
        skill_md=skill_src,
        skill_slug=skill_slug,
        skill_version=1,
        model="demo/scripted-model",
        judge_model="demo/scripted-model",
        n_bootstrap=1000,
        bootstrap_seed=42,
    )

    _print_human_summary(report, skill_slug)
    print("  \u26a0\ufe0f  These numbers are SYNTHETIC (scripted offline demo).")
    print("  Run `python -m skill_factory eval <your-skill> --save` for a real measurement.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
