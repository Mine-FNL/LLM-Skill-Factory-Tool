"""Eval harness: prove your SKILL.md actually improves the model.

Public API:

- :class:`EvalSet`, :class:`EvalPrompt`, :class:`JudgeConfig` — declarative
  YAML schemas (see ``skill_factory.eval.types``).
- :func:`load_eval_set`, :func:`list_eval_sets` — YAML loaders
  (see ``skill_factory.eval.loader``).
- :func:`run_eval` — runs an eval set against a skill and returns an
  :class:`EvalReport` with the lift and bootstrap CI.
- :func:`save_report_to_skill_meta` — persists the report to ``metadata.json``.
- :func:`parse_score` — score-string parser used by the judge.

Example::

    from skill_factory.eval import load_eval_set, run_eval, save_report_to_skill_meta
    from skill_factory.llm_client import client_from_settings
    from skill_factory.skill_store import SkillStore

    client = client_from_settings()
    eval_set = load_eval_set("backend-api-engineer")
    skill = SkillStore("./skills").load_content("backend-api-engineer", 1)
    report = run_eval(client, eval_set, skill_md=skill, skill_slug="backend-api-engineer")
    print(report.summary())
"""

from __future__ import annotations

from .judge import judge_response, parse_score
from .loader import DEFAULT_EVALS_DIR, evals_dir, list_eval_sets, load_eval_set
from .runner import (
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_N_BOOTSTRAP,
    bootstrap_lift_ci,
    run_eval,
    save_report_to_skill_meta,
)
from .types import EvalPrompt, EvalReport, EvalSet, JudgeConfig, PromptResult

__all__ = [
    "DEFAULT_BOOTSTRAP_SEED",
    "DEFAULT_EVALS_DIR",
    "DEFAULT_N_BOOTSTRAP",
    "EvalPrompt",
    "EvalReport",
    "EvalSet",
    "JudgeConfig",
    "PromptResult",
    "bootstrap_lift_ci",
    "evals_dir",
    "judge_response",
    "list_eval_sets",
    "load_eval_set",
    "parse_score",
    "run_eval",
    "save_report_to_skill_meta",
]
