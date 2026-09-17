"""Core ``run_skill`` function — load a saved skill and call the model."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..frontmatter import split_frontmatter
from ..llm_client import LLMClient, LLMError
from ..models import SkillMeta
from ..skill_store import SkillStore

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """The output of a single ``run_skill`` invocation."""

    skill_slug: str
    skill_version: int
    skill_description: str
    model: str
    prompt: str
    output: str
    usage: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: int = 0
    # Whether the skill was found and loaded successfully.
    ok: bool = True
    error: str | None = None


def _resolve_skill_md(skill_md: str) -> tuple[str, str]:
    """Return (frontmatter_dict_as_str, body) for the loaded SKILL.md."""

    _fm, body = split_frontmatter(skill_md)
    return ("", body.strip() if body.strip() else skill_md)


def _resolve_meta(store: SkillStore, slug: str, version: int | None) -> SkillMeta:
    """Load the SkillMeta, falling back to a minimal one if metadata.json is missing."""

    try:
        return store.load_meta(slug, version)
    except FileNotFoundError:
        # Skill exists but metadata.json is absent — fine, just return a stub.
        return SkillMeta(name=slug, description="")


def run_skill(
    store: SkillStore,
    client: LLMClient,
    *,
    slug: str,
    prompt: str,
    version: int | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> RunResult:
    """Load ``slug`` from ``store`` and call ``client`` with the skill as system prompt.

    The skill body is injected as the system message; the user prompt is the
    raw ``prompt`` argument. Returns a :class:`RunResult` containing the
    model output plus usage metadata.
    """

    import time

    if not store.exists(slug, version):
        return RunResult(
            skill_slug=slug,
            skill_version=version or 0,
            skill_description="",
            model=model or client.default_model,
            prompt=prompt,
            output="",
            ok=False,
            error=f"skill '{slug}' (version={version or 'latest'}) not found",
        )

    resolved_version = version or store.latest_version(slug)
    if resolved_version is None:
        return RunResult(
            skill_slug=slug,
            skill_version=0,
            skill_description="",
            model=model or client.default_model,
            prompt=prompt,
            output="",
            ok=False,
            error=f"skill '{slug}' has no versions",
        )

    skill_md = store.load_content(slug, resolved_version)
    meta = _resolve_meta(store, slug, resolved_version)
    _, system_body = _resolve_skill_md(skill_md)
    if not system_body:
        return RunResult(
            skill_slug=slug,
            skill_version=resolved_version,
            skill_description=meta.description,
            model=model or client.default_model,
            prompt=prompt,
            output="",
            ok=False,
            error=f"skill '{slug}' v{resolved_version} has empty body",
        )

    chosen_model = model or client.default_model
    start = time.time()
    try:
        result = client.complete(
            system=system_body,
            user=prompt,
            model=chosen_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except LLMError as exc:
        return RunResult(
            skill_slug=slug,
            skill_version=resolved_version,
            skill_description=meta.description,
            model=chosen_model,
            prompt=prompt,
            output="",
            ok=False,
            error=f"model call failed: {exc}",
        )
    elapsed_ms = int((time.time() - start) * 1000)

    return RunResult(
        skill_slug=slug,
        skill_version=resolved_version,
        skill_description=meta.description,
        model=chosen_model,
        prompt=prompt,
        output=result.content,
        usage=result.usage,
        elapsed_ms=elapsed_ms,
    )
