"""Core data structures shared across the Skill Factory.

These are plain dataclasses with ``to_dict``/``from_dict`` helpers so they can be
serialised to ``metadata.json`` and round-tripped in tests without any framework
coupling. Nothing here is domain-specific.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Skill types — generic, NOT tied to any domain.
# ---------------------------------------------------------------------------
SKILL_TYPES: list[str] = ["domain-expert", "specialist", "workflow", "hybrid"]

SKILL_TYPE_HELP: dict[str, str] = {
    "domain-expert": "Broad expertise in a field (e.g. 'backend-api-engineer', 'financial-statement-analyst').",
    "specialist": "Deep focus on a single subject/entity, usually extending a base skill (e.g. 'qnb-analyst').",
    "workflow": "A repeatable procedure or checklist the model should follow step by step.",
    "hybrid": "A mix of domain knowledge and a concrete workflow.",
}

# Tones offered in the UI; free text is also allowed.
TONES: list[str] = ["concise", "balanced", "comprehensive"]


@dataclass
class SkillSpec:
    """Everything the user supplies to generate a skill. Fully domain-agnostic."""

    name: str
    description: str = ""  # the YAML frontmatter trigger description
    skill_type: str = "domain-expert"
    domain_focus: str = ""
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)  # companies/subjects/services — generic
    requirements: list[str] = field(default_factory=list)
    base_skill: str | None = None  # slug of a base skill this one extends
    token_budget: int = 1500  # approximate target size of the body
    tone: str = "balanced"
    reference_text: str = ""  # injected context (pasted facts or extracted docs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillSpec:
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class TestResult:
    """A single playground run recorded against a skill version."""

    __test__ = False  # not a pytest test class

    test_name: str
    user_prompt: str
    output: str
    model: str
    rating: str = ""  # "up" | "down" | ""
    notes: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestResult:
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class SkillMeta:
    """Per-version metadata persisted alongside ``SKILL.md`` as ``metadata.json``."""

    name: str
    description: str = ""
    skill_type: str = "domain-expert"
    domain_focus: str = ""
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    base_skill: str | None = None
    version: int = 1
    version_notes: str = ""
    model: str = ""  # model used to generate this version
    created_at: float = field(default_factory=time.time)
    test_results: list[TestResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["test_results"] = [t.to_dict() for t in self.test_results]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillMeta:
        data = dict(data)
        raw_results = data.pop("test_results", []) or []
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        meta = cls(**{k: v for k, v in data.items() if k in known})
        meta.test_results = [TestResult.from_dict(r) for r in raw_results]
        return meta

    @classmethod
    def from_spec(
        cls, spec: SkillSpec, *, version: int = 1, model: str = "", version_notes: str = ""
    ) -> SkillMeta:
        return cls(
            name=spec.name,
            description=spec.description,
            skill_type=spec.skill_type,
            domain_focus=spec.domain_focus,
            tags=list(spec.tags),
            entities=list(spec.entities),
            base_skill=spec.base_skill,
            version=version,
            version_notes=version_notes,
            model=model,
        )


@dataclass
class GenerationResult:
    """Returned by pipeline stages that call the LLM."""

    content: str
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestCase:
    """A reusable playground test case."""

    __test__ = False  # not a pytest test class

    name: str
    user_prompt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    """Result of linting a ``SKILL.md`` against best-practice rules."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    frontmatter: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"{len(self.errors)} error(s), "
            f"{len(self.warnings)} warning(s), "
            f"{len(self.suggestions)} suggestion(s)"
        )
