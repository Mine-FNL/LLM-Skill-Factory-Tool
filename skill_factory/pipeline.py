"""Generation pipeline — pure orchestration over an OpenRouter-like client.

Each function takes a ``client`` exposing ``complete(system=, user=, model=,
temperature=)`` and returning a :class:`GenerationResult`. That tiny contract is
all the tests need to mock.
"""

from __future__ import annotations

from . import meta_prompts as mp
from .models import GenerationResult, SkillSpec


def clean_skill_output(text: str) -> str:
    """Defensively strip code fences / preamble the model may add despite the contract."""

    s = text.strip()

    # Remove surrounding triple-backtick fences (``` or ```markdown).
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()

    # If there is preamble before the frontmatter, drop it.
    if not s.startswith("---"):
        lines = s.splitlines()
        for i, ln in enumerate(lines):
            if ln.strip() == "---":
                s = "\n".join(lines[i:]).strip()
                break

    return s + "\n"


def plan_outline(
    client, spec: SkillSpec, *, model: str | None = None, temperature: float = 0.5
) -> GenerationResult:
    return client.complete(
        system=mp.outline_system(),
        user=mp.outline_user(spec),
        model=model,
        temperature=temperature,
    )


def generate_draft(
    client,
    spec: SkillSpec,
    outline: str = "",
    *,
    model: str | None = None,
    temperature: float = 0.6,
) -> GenerationResult:
    result = client.complete(
        system=mp.draft_system(),
        user=mp.draft_user(spec, outline),
        model=model,
        temperature=temperature,
    )
    result.content = clean_skill_output(result.content)
    return result


def refine_section(
    client,
    skill_md: str,
    instruction: str,
    *,
    section: str = "",
    model: str | None = None,
    temperature: float = 0.5,
) -> GenerationResult:
    result = client.complete(
        system=mp.refine_system(),
        user=mp.refine_user(skill_md, instruction, section),
        model=model,
        temperature=temperature,
    )
    result.content = clean_skill_output(result.content)
    return result


def generate_overlay(
    client,
    base_md: str,
    entity: str,
    spec: SkillSpec,
    *,
    model: str | None = None,
    temperature: float = 0.6,
) -> GenerationResult:
    result = client.complete(
        system=mp.overlay_system(),
        user=mp.overlay_user(base_md, entity, spec),
        model=model,
        temperature=temperature,
    )
    result.content = clean_skill_output(result.content)
    return result
