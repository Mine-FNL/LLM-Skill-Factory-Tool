"""Data types for the eval harness.

The eval loop is:

1. Load an :class:`EvalSet` (YAML).
2. For each prompt in the set, run the **base model** with no skill → ``base_outputs``.
3. For each prompt, run the **base model + skill** with the skill body as the system prompt → ``skill_outputs``.
4. For each (output, prompt) pair, ask the judge model to score it against the prompt's
   ``expected_traits`` → per-prompt scores in [0, 0.5, 1].
5. Compute pass-rate per arm (threshold = ``pass_threshold``), then the **lift**
   ``pass_skill - pass_base`` and a bootstrap 95% CI.

Everything is plain dataclasses so the results serialise cleanly to ``metadata.json``.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvalPrompt:
    """A single held-out prompt with the traits the response should exhibit."""

    id: str
    prompt: str
    expected_traits: list[str] = field(default_factory=list)
    rubric: str = ""  # optional per-prompt override of the eval-set rubric

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalPrompt:
        return cls(
            id=str(data["id"]),
            prompt=str(data["prompt"]),
            expected_traits=list(data.get("expected_traits", []) or []),
            rubric=str(data.get("rubric", "") or ""),
        )


@dataclass
class JudgeConfig:
    """How to call the LLM-as-judge."""

    prompt: str = (
        "You are an expert evaluator. You will be given a prompt, a list of expected traits "
        "that a high-quality response should exhibit, and an actual response. "
        "Score the response on a 3-point scale:\n"
        "  1.0 — ALL expected traits are substantively addressed.\n"
        "  0.5 — at least half (rounded up) of the traits are addressed.\n"
        "  0.0 — fewer than half are addressed.\n"
        "Output ONLY the score: a single number (0, 0.5, or 1). No commentary."
    )
    # Optional override of the model used for judging. Defaults to the eval model.
    model: str = ""


@dataclass
class ControlPrompt:
    """A judge self-calibration control: a prompt with a known expected score.

    The runner scores the control and warns if the judge's score diverges from
    ``expected_score``. Use these to catch judge miscalibration before trusting
    a real lift number.
    """

    id: str
    prompt: str
    expected_score: float
    expected_response_snippet: str = ""
    # Tolerance for warnings: |judge - expected| > tolerance ⇒ warning.
    tolerance: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlPrompt:
        return cls(
            id=str(data["id"]),
            prompt=str(data["prompt"]),
            expected_score=float(data["expected_score"]),
            expected_response_snippet=str(data.get("expected_response_snippet", "") or ""),
            tolerance=float(data.get("tolerance", 0.5)),
        )

    def to_eval_prompt(self) -> EvalPrompt:
        """Render the control as a synthetic :class:`EvalPrompt` for the judge.

        The expected_traits are derived from the expected_score so the judge
        sees a consistent rubric. We use a trait that the judge can either
        detect (for high-score controls) or fail to detect (for low-score
        controls); the resulting score lets us measure divergence.
        """

        from .types import EvalPrompt  # local import to avoid cycle at module load

        if self.expected_score >= 1.0:
            traits = ["addresses the prompt thoroughly and correctly"]
        elif self.expected_score >= 0.5:
            traits = ["partially addresses the prompt"]
        else:
            traits = ["fails to address the prompt adequately"]
        return EvalPrompt(
            id=f"control-{self.id}",
            prompt=self.prompt,
            expected_traits=traits,
        )


@dataclass
class EvalSet:
    """A named collection of prompts + judging instructions."""

    name: str
    description: str = ""
    version: int = 1
    prompts: list[EvalPrompt] = field(default_factory=list)
    judge: JudgeConfig = field(default_factory=JudgeConfig)
    # Optional self-calibration controls (see :class:`ControlPrompt`).
    controls: list[ControlPrompt] = field(default_factory=list)
    # Per-prompt score >= pass_threshold counts as a "pass".
    pass_threshold: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "pass_threshold": self.pass_threshold,
            "judge": asdict(self.judge),
            "controls": [c.to_dict() for c in self.controls],
            "prompts": [p.to_dict() for p in self.prompts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalSet:
        judge_data = data.get("judge") or {}
        return cls(
            name=str(data["name"]),
            description=str(data.get("description", "")),
            version=int(data.get("version", 1)),
            prompts=[EvalPrompt.from_dict(p) for p in data.get("prompts", [])],
            judge=JudgeConfig(**judge_data) if judge_data else JudgeConfig(),
            controls=[ControlPrompt.from_dict(c) for c in data.get("controls", []) or []],
            pass_threshold=float(data.get("pass_threshold", 0.5)),
        )


@dataclass
class PromptResult:
    """Result of running + judging a single prompt in both arms."""

    prompt_id: str
    prompt: str
    expected_traits: list[str]
    base_output: str
    skill_output: str
    base_score: float
    skill_score: float
    base_passed: bool
    skill_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvalReport:
    """Aggregate result for one skill (cross-product) one eval set."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    skill_slug: str = ""
    skill_version: int | None = None
    eval_set_name: str = ""
    eval_set_version: int = 1
    eval_model: str = ""
    judge_model: str = ""
    base_pass_rate: float = 0.0
    skill_pass_rate: float = 0.0
    lift_pp: float = 0.0  # percentage points
    lift_ci_low_pp: float = 0.0  # bootstrap 2.5th percentile, percentage points
    lift_ci_high_pp: float = 0.0  # bootstrap 97.5th percentile, percentage points
    n_prompts: int = 0
    n_bootstrap: int = 0
    pass_threshold: float = 0.5
    created_at: float = field(default_factory=time.time)
    prompt_results: list[PromptResult] = field(default_factory=list)
    # Judge self-calibration results (one entry per control prompt).
    control_results: list[dict[str, Any]] = field(default_factory=list)
    # Free-form notes (cost, runtime, warnings).
    notes: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"lift = {self.lift_pp:+.1f}pp "
            f"(95% CI [{self.lift_ci_low_pp:+.1f}, {self.lift_ci_high_pp:+.1f}], "
            f"n={self.n_prompts}, base={self.base_pass_rate:.0%}, "
            f"skill={self.skill_pass_rate:.0%})"
        )

    def judge_calibration_ok(self) -> bool:
        """True when every control prompt was scored within its tolerance."""
        return all(c.get("within_tolerance", True) for c in self.control_results)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["prompt_results"] = [p.to_dict() for p in self.prompt_results]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalReport:
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in data.items() if k in known and k != "prompt_results"}
        results = [PromptResult(**r) for r in data.get("prompt_results", [])]
        kwargs["prompt_results"] = results
        return cls(**kwargs)
