"""LLM-as-judge wrapper for the eval harness.

The judge scores each response on the 3-point scale defined in
:class:`EvalSet.judge.prompt`. We tolerate the model wrapping the answer in
whitespace, code fences, or trailing punctuation — the parser pulls the first
token that parses as a number in ``{0, 0.5, 1}``.

If parsing still fails after normalisation, the score defaults to 0.0 and a
warning is logged. This matches the "strict verifier" stance: an unparseable
verdict is treated as a fail, never silently coerced to a pass.
"""

from __future__ import annotations

import logging
import re

from ..llm_client import LLMClient, LLMError
from .types import EvalPrompt, JudgeConfig

logger = logging.getLogger(__name__)

# Match a number at the start of the response: "1.0", "0.5", "  1 ", "Score: 0.5\n..."
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_score(raw: str) -> float | None:
    """Return a score in {0.0, 0.5, 1.0} or ``None`` if the text is unparseable.

    Strategy: pull the first number-like token, snap it to the closest legal
    value. Anything outside [0, 1] is rejected.
    """

    if not raw:
        return None
    cleaned = raw.strip().strip("`'\"")
    # Strip a leading "Score:" / "Verdict:" label if present.
    cleaned = re.sub(r"^(score|verdict|rating)\s*[:=]\s*", "", cleaned, flags=re.I)
    m = _NUMBER_RE.search(cleaned)
    if not m:
        return None
    try:
        value = float(m.group(0))
    except ValueError:
        return None
    if value < 0 or value > 1:
        return None
    # Snap to the legal set. Use the closest of {0.0, 0.5, 1.0}.
    candidates = (0.0, 0.5, 1.0)
    return min(candidates, key=lambda c: abs(c - value))


def _format_judge_prompt(prompt: str, traits: list[str], response: str) -> str:
    traits_block = (
        "\n".join(f"- {t}" for t in traits)
        if traits
        else "- (no specific traits — score on overall quality / correctness)"
    )
    return (
        f"## Prompt\n{prompt}\n\n"
        f"## Expected traits\n{traits_block}\n\n"
        f"## Response to score\n{response}\n\n"
        "## Your score"
    )


def judge_response(
    client: LLMClient,
    prompt: EvalPrompt,
    response: str,
    judge_cfg: JudgeConfig,
    *,
    judge_model: str | None = None,
) -> float:
    """Score one (prompt, response) pair. Returns 0.0 if the judge is unparseable."""

    user_msg = _format_judge_prompt(prompt.prompt, prompt.expected_traits, response)
    model = judge_model or judge_cfg.model or client.default_model
    try:
        result = client.complete(
            system=judge_cfg.prompt,
            user=user_msg,
            model=model,
            temperature=0.0,  # judgment should be deterministic
            max_tokens=8,  # we only need a number
        )
    except LLMError as exc:
        logger.warning("Judge call failed: %s; defaulting to 0.0", exc)
        return 0.0
    score = parse_score(result.content)
    if score is None:
        logger.warning(
            "Unparseable judge verdict for prompt %s: %r; defaulting to 0.0",
            prompt.id,
            result.content,
        )
        return 0.0
    return score
