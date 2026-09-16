"""The eval runner.

For each prompt in an :class:`EvalSet`, runs two arms:

- **base**: the model with no skill (just a minimal generic system prompt).
- **skill**: the model with the skill body injected as the system prompt.

Each output is scored by the judge. We compute pass-rates per arm (a pass
means score >= ``EvalSet.pass_threshold``), the **lift** in percentage points,
and a bootstrap 95% CI on the lift.

The bootstrap resamples prompt indices with replacement ``n_bootstrap`` times,
computes (pass_rate_skill - pass_rate_base) on each resample, and reports the
2.5/97.5 percentiles. With 5-10 prompts the CIs will be wide — we report
them honestly rather than hiding them.
"""

from __future__ import annotations

import logging
import random
from typing import Any

from ..frontmatter import split_frontmatter
from ..llm_client import LLMClient, LLMError
from ..skill_store import SkillStore
from .judge import judge_response
from .types import ControlPrompt, EvalReport, EvalSet, PromptResult

logger = logging.getLogger(__name__)

# Minimal generic system prompt for the base arm. Kept short so it doesn't
# accidentally teach the model anything that would inflate the baseline.
_BASE_SYSTEM = "You are a helpful assistant. Answer the user's question directly."

DEFAULT_N_BOOTSTRAP = 1000
DEFAULT_BOOTSTRAP_SEED = 0  # deterministic by default; tests can override


def _skill_body(skill_md: str) -> str:
    """Return just the body of a SKILL.md (drop the YAML frontmatter).

    Skills are injected as system prompts; the YAML metadata is not part of
    the runtime instructions the model should follow.
    """

    _fm, body = split_frontmatter(skill_md)
    return body.strip() if body.strip() else skill_md


def _pass(score: float, threshold: float) -> bool:
    return score >= threshold


def _run_one(client: LLMClient, system: str, user: str, *, model: str | None) -> str:
    try:
        result = client.complete(
            system=system,
            user=user,
            model=model,
            temperature=0.0,
            max_tokens=2048,
        )
        return result.content
    except LLMError as exc:
        # Surface as empty string so the judge scores it 0 — we don't want a
        # transient API failure to silently exclude a prompt.
        logger.warning("Eval generation failed: %s", exc)
        return ""


def bootstrap_lift_ci(
    base_passed: list[bool],
    skill_passed: list[bool],
    *,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Return the (low, high) bootstrap CI for lift, in percentage points.

    ``lift_pp = (mean(skill) - mean(base)) * 100``. We resample prompt indices
    with replacement, compute the lift on each resample, and return the
    ``alpha/2`` and ``1 - alpha/2`` percentiles.
    """

    n = len(base_passed)
    if n == 0 or n != len(skill_passed):
        return (0.0, 0.0)
    if n_bootstrap <= 0:
        return (0.0, 0.0)
    rng = random.Random(seed)
    base_f = [1.0 if b else 0.0 for b in base_passed]
    skill_f = [1.0 if s else 0.0 for s in skill_passed]
    lifts: list[float] = []
    for _ in range(n_bootstrap):
        idxs = [rng.randrange(n) for _ in range(n)]
        b_mean = sum(base_f[i] for i in idxs) / n
        s_mean = sum(skill_f[i] for i in idxs) / n
        lifts.append((s_mean - b_mean) * 100.0)
    lifts.sort()
    lo_idx = round((alpha / 2) * (n_bootstrap - 1))
    hi_idx = round((1 - alpha / 2) * (n_bootstrap - 1))
    return (lifts[lo_idx], lifts[hi_idx])


def run_controls(
    client: LLMClient,
    eval_set: EvalSet,
    *,
    judge_model: str | None = None,
) -> list[dict[str, Any]]:
    """Score each control prompt and return a list of result dicts.

    Each result has ``id``, ``expected_score``, ``judge_score``, ``delta``,
    ``tolerance``, ``within_tolerance``, and ``warning``. A miscalibrated judge
    shows up as ``within_tolerance=False`` and a non-null ``warning``.
    """

    results: list[dict[str, Any]] = []
    for control in eval_set.controls:
        # The control's "response" is the *expected* behaviour (a hint of what
        # the model *should* say), which we judge. The judge shouldn't know
        # the expected score — we just measure divergence afterwards.
        synthetic_response = control.expected_response_snippet or control.prompt
        score = judge_response(
            client,
            ControlPrompt.to_eval_prompt(control),
            synthetic_response,
            eval_set.judge,
            judge_model=judge_model,
        )
        delta = score - control.expected_score
        within = abs(delta) <= control.tolerance
        warning: str | None = None
        if not within:
            warning = (
                f"judge scored {score:.1f} for control '{control.id}' "
                f"(expected {control.expected_score:.1f}, tolerance ±{control.tolerance:.1f}). "
                "A miscalibrated judge can inflate the lift — fix the judge prompt "
                "or the control before trusting the lift number."
            )
        results.append(
            {
                "id": control.id,
                "expected_score": control.expected_score,
                "judge_score": score,
                "delta": delta,
                "tolerance": control.tolerance,
                "within_tolerance": within,
                "warning": warning,
            }
        )
    return results


def run_eval(
    client: LLMClient,
    eval_set: EvalSet,
    *,
    skill_md: str | None = None,
    skill_slug: str = "",
    skill_version: int | None = None,
    model: str | None = None,
    judge_model: str | None = None,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> EvalReport:
    """Run the full eval and return an :class:`EvalReport`.

    ``skill_md=None`` runs only the base arm and reports base_pass_rate —
    useful for sanity-checking the eval set itself.
    """

    skill_system = _skill_body(skill_md) if skill_md else None
    base_passed: list[bool] = []
    skill_passed: list[bool] = []
    prompt_results: list[PromptResult] = []
    threshold = eval_set.pass_threshold

    # Judge self-calibration controls (run first so warnings are visible).
    control_results = run_controls(client, eval_set, judge_model=judge_model)

    for prompt in eval_set.prompts:
        base_out = _run_one(client, _BASE_SYSTEM, prompt.prompt, model=model)
        base_score = judge_response(
            client,
            prompt,
            base_out,
            eval_set.judge,
            judge_model=judge_model,
        )
        base_is_pass = _pass(base_score, threshold)

        if skill_system is not None:
            skill_out = _run_one(client, skill_system, prompt.prompt, model=model)
            skill_score = judge_response(
                client,
                prompt,
                skill_out,
                eval_set.judge,
                judge_model=judge_model,
            )
            skill_is_pass = _pass(skill_score, threshold)
        else:
            skill_out = ""
            skill_score = 0.0
            skill_is_pass = False

        prompt_results.append(
            PromptResult(
                prompt_id=prompt.id,
                prompt=prompt.prompt,
                expected_traits=list(prompt.expected_traits),
                base_output=base_out,
                skill_output=skill_out,
                base_score=base_score,
                skill_score=skill_score,
                base_passed=base_is_pass,
                skill_passed=skill_is_pass,
            )
        )
        base_passed.append(base_is_pass)
        skill_passed.append(skill_is_pass)

    n = len(prompt_results)
    base_rate = sum(1 for b in base_passed if b) / n if n else 0.0
    skill_rate = sum(1 for s in skill_passed if s) / n if n else 0.0
    lift_pp = (skill_rate - base_rate) * 100.0
    ci_lo, ci_hi = bootstrap_lift_ci(
        base_passed,
        skill_passed,
        n_bootstrap=n_bootstrap,
        seed=bootstrap_seed,
    )

    return EvalReport(
        skill_slug=skill_slug,
        skill_version=skill_version,
        eval_set_name=eval_set.name,
        eval_set_version=eval_set.version,
        eval_model=model or client.default_model,
        judge_model=judge_model or eval_set.judge.model or (model or client.default_model),
        base_pass_rate=base_rate,
        skill_pass_rate=skill_rate,
        lift_pp=lift_pp,
        lift_ci_low_pp=ci_lo,
        lift_ci_high_pp=ci_hi,
        n_prompts=n,
        n_bootstrap=n_bootstrap,
        pass_threshold=threshold,
        prompt_results=prompt_results,
        control_results=control_results,
    )


def save_report_to_skill_meta(
    store: SkillStore,
    slug: str,
    version: int,
    report: EvalReport,
) -> None:
    """Persist the report into ``metadata.json``.

    The :class:`SkillMeta` dataclass already carries the eval fields
    (declared with defaults so older metadata.json files round-trip cleanly).
    Existing test_results and other metadata are preserved.
    """

    meta = store.load_meta(slug, version)
    history = list(meta.eval_results or [])
    history.append(report.to_dict())
    meta.eval_results = history[-20:]  # cap the in-file history
    # Latest snapshot for fast reads (used by the library card UI).
    meta.lift_pp = report.lift_pp
    meta.lift_ci_pp = (report.lift_ci_low_pp, report.lift_ci_high_pp)
    meta.base_pass_rate = report.base_pass_rate
    meta.skill_pass_rate = report.skill_pass_rate
    meta.last_eval_set = report.eval_set_name
    meta.last_eval_at = report.created_at
    store.update_meta(slug, version, meta)
