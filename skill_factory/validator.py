"""Best-practice linting for generated ``SKILL.md`` files.

The rules encode the same conventions the meta-prompt is told to follow, so the
validator acts as an automated reviewer of the model's output. Rules are
domain-agnostic.
"""

from __future__ import annotations

import re

from .frontmatter import split_frontmatter
from .models import ValidationReport

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Words that signal explicit trigger conditions in a description.
_TRIGGER_HINTS = ("use when", "use this", "when ", "whenever", "trigger", "for ")

# Imperative sentence starters we expect to see in a good skill body.
_IMPERATIVE_HINTS = (
    "always",
    "never",
    "use ",
    "check",
    "structure",
    "ensure",
    "avoid",
    "follow",
    "include",
    "do not",
    "prefer",
    "verify",
    "start",
    "list",
)

MAX_NAME_LEN = 64  # mirrors skill_factory.safety.MAX_NAME_LEN (kept in sync)
MAX_DESC_LEN = 1024
MIN_DESC_LEN = 40
LONG_BODY_LINES = 400  # suggest progressive disclosure beyond this


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) — good enough for budget warnings."""

    return max(0, len(text) // 4)


def validate_skill_md(
    text: str,
    *,
    expected_name: str | None = None,
    token_budget: int | None = None,
) -> ValidationReport:
    report = ValidationReport()
    fm, body = split_frontmatter(text)
    report.frontmatter = fm

    # --- frontmatter presence -------------------------------------------
    if not fm:
        report.errors.append(
            "Missing or malformed YAML frontmatter. The file must start with a "
            "'---' block containing 'name' and 'description'."
        )
        return report  # nothing else is meaningful without frontmatter

    # --- name -----------------------------------------------------------
    name = str(fm.get("name", "")).strip()
    if not name:
        report.errors.append("Frontmatter is missing a 'name' field.")
    else:
        if not NAME_RE.match(name):
            report.errors.append(
                f"'name' must be kebab-case (lowercase letters, digits, hyphens): got '{name}'."
            )
        if len(name) > MAX_NAME_LEN:
            report.errors.append(f"'name' exceeds {MAX_NAME_LEN} characters.")
        if expected_name and name != expected_name:
            report.warnings.append(
                f"'name' ('{name}') does not match the skill folder ('{expected_name}')."
            )

    # --- description ----------------------------------------------------
    desc = str(fm.get("description", "")).strip()
    if not desc:
        report.errors.append("Frontmatter is missing a 'description' field.")
    else:
        if len(desc) > MAX_DESC_LEN:
            report.warnings.append(
                f"'description' is {len(desc)} chars; keep it under {MAX_DESC_LEN}."
            )
        if len(desc) < MIN_DESC_LEN:
            report.warnings.append(
                "'description' is very short. It should explain what the skill does "
                "AND when to use it (trigger conditions)."
            )
        if not any(h in desc.lower() for h in _TRIGGER_HINTS):
            report.suggestions.append(
                "Add explicit trigger conditions to the description (e.g. 'Use when…') "
                "so the model reliably knows when to activate the skill."
            )

    # --- body -----------------------------------------------------------
    if not body.strip():
        report.errors.append("The skill body is empty.")
        return report

    headings = [ln for ln in body.splitlines() if ln.lstrip().startswith("#")]
    if len(headings) < 2:
        report.suggestions.append(
            "Add clear section headings (e.g. Overview, Framework, Examples) to "
            "structure the skill."
        )

    if not any(h in body.lower() for h in _IMPERATIVE_HINTS):
        report.suggestions.append(
            "Use imperative voice ('Always…', 'Structure your response as…', "
            "'Check the following…') rather than descriptive prose."
        )

    if "example" not in body.lower():
        report.suggestions.append(
            "Include at least one concrete example (ideally good-vs-poor) to anchor quality."
        )

    line_count = len(body.splitlines())
    if line_count > LONG_BODY_LINES:
        report.suggestions.append(
            f"The body is {line_count} lines. Consider progressive disclosure: keep the "
            "main file focused and move deep detail into a 'references/' file."
        )

    if token_budget:
        est = estimate_tokens(body)
        if est > token_budget * 1.5:
            report.warnings.append(
                f"Body is ~{est} tokens, well above the {token_budget}-token target. "
                "Trim to only non-obvious, high-value knowledge."
            )

    return report
