"""The meta-skill: prompts that teach the model to author excellent ``SKILL.md``.

This is the core leverage of the whole tool. Everything here is domain-agnostic
— the same prompts produce a great backend-engineer skill, quant-analyst skill,
or financial-analyst skill depending only on the :class:`SkillSpec`.
"""

from __future__ import annotations

from .models import SkillSpec

# ---------------------------------------------------------------------------
# The shared best-practice guide injected into every generation/refinement call.
# ---------------------------------------------------------------------------
SKILL_MD_GUIDE = """\
You are an expert author of SKILL.md files. A SKILL.md is a modular instruction \
package (an expert system prompt) that makes an LLM dramatically better at a \
specific kind of work. Follow these rules without exception.

## File format
- The file MUST begin with a YAML frontmatter block delimited by `---` lines.
- Frontmatter has exactly two required keys:
  - `name`: kebab-case, lowercase letters/digits/hyphens only, <= 64 chars. It \
must match the intended skill identifier.
  - `description`: written in the third person. It must state BOTH what the skill \
does AND the concrete conditions that should trigger its use (e.g. "Use when the \
user asks to ..."). Pack it with the keywords/scenarios that should activate it. \
Keep it under ~1024 characters. This field is the single most important driver of \
whether the skill gets used correctly — make it specific and trigger-rich.

## Writing style
- Use imperative voice aimed at the model that will run the skill: "Always ...", \
"Structure your response as ...", "Before concluding, check ...".
- Include ONLY non-obvious, high-value knowledge. Do NOT restate things a capable \
model already knows. Every line must earn its place.
- Be concrete and actionable: provide frameworks, checklists, decision rules, and \
output templates rather than vague advice.
- Prefer tight prose and lists over long paragraphs. Optimise for token efficiency.

## Structure (adapt to the skill type; omit sections that don't apply)
- A short Overview / role statement.
- Core knowledge or principles (the non-obvious essentials).
- A step-by-step framework or workflow with a checklist.
- Red flags / watchpoints / common mistakes to avoid.
- Output template(s) the model should produce.
- At least one concrete example, ideally contrasting good vs poor work.

## Progressive disclosure
- Keep the main body focused and reasonably short. If a topic needs extensive \
detail, summarise it and note that it could live in a separate `references/` file \
rather than bloating the main file.

## Output contract
- Output ONLY the complete SKILL.md file content: the frontmatter block followed \
by the markdown body.
- Do NOT wrap the output in code fences. Do NOT add any commentary before or after.
"""


def _render_spec(spec: SkillSpec) -> str:
    """Human-readable rendering of the spec for inclusion in a user prompt."""

    lines = [
        f"- Skill name (use as frontmatter `name`): {spec.name}",
        f"- Skill type: {spec.skill_type}",
    ]
    if spec.domain_focus:
        lines.append(f"- Domain / focus: {spec.domain_focus}")
    if spec.description:
        lines.append(f"- Desired trigger / when to use: {spec.description}")
    if spec.tags:
        lines.append(f"- Tags: {', '.join(spec.tags)}")
    if spec.entities:
        lines.append(f"- Specific subjects/entities to cover: {', '.join(spec.entities)}")
    if spec.requirements:
        reqs = "\n".join(f"    - {r}" for r in spec.requirements)
        lines.append(f"- Key requirements:\n{reqs}")
    if spec.base_skill:
        lines.append(f"- Extends base skill: {spec.base_skill}")
    lines.append(f"- Tone: {spec.tone}")
    lines.append(f"- Target body size: ~{spec.token_budget} tokens")
    return "\n".join(lines)


def _context_block(reference_text: str) -> str:
    if not reference_text.strip():
        return ""
    return (
        "\n\nUse the following reference material as ground truth where relevant. "
        "Incorporate only the non-obvious, durable facts into the skill; do not copy "
        "it verbatim or include ephemeral details:\n"
        "<reference_material>\n"
        f"{reference_text.strip()}\n"
        "</reference_material>"
    )


# ---------------------------------------------------------------------------
# Stage 1 — Outline
# ---------------------------------------------------------------------------
def outline_system() -> str:
    return (
        SKILL_MD_GUIDE + "\n\n## Current task\nYou are in the PLANNING stage. Do not write the "
        "skill yet. Produce a concise outline (markdown bullets) of the sections the "
        "SKILL.md should contain, with a one-line note under each on what it will "
        "cover and why it is non-obvious/high-value. The user will review and edit "
        "this outline before drafting. Output only the outline."
    )


def outline_user(spec: SkillSpec) -> str:
    return (
        "Plan the outline for this skill:\n\n"
        + _render_spec(spec)
        + _context_block(spec.reference_text)
    )


# ---------------------------------------------------------------------------
# Stage 3 — Draft
# ---------------------------------------------------------------------------
def draft_system() -> str:
    return (
        SKILL_MD_GUIDE + "\n\n## Current task\nYou are in the DRAFTING stage. Write the complete, "
        "production-ready SKILL.md now, following the approved outline and all rules "
        "above. Remember the output contract: output only the file content, no fences, "
        "no commentary."
    )


def draft_user(spec: SkillSpec, outline: str) -> str:
    parts = ["Write the SKILL.md for this skill:\n", _render_spec(spec)]
    if outline.strip():
        parts.append(
            "\n\nFollow this approved outline (refine wording as needed but keep the "
            "structure):\n<outline>\n" + outline.strip() + "\n</outline>"
        )
    parts.append(_context_block(spec.reference_text))
    return "".join(parts)


# ---------------------------------------------------------------------------
# Stage 4 — Refine a section / the whole file
# ---------------------------------------------------------------------------
def refine_system() -> str:
    return (
        SKILL_MD_GUIDE
        + "\n\n## Current task\nYou are in the REFINEMENT stage. Revise the provided "
        "SKILL.md according to the user's instruction while preserving everything that "
        "is already good and keeping all formatting rules. Output the COMPLETE revised "
        "SKILL.md (not a diff), with no fences and no commentary."
    )


def refine_user(skill_md: str, instruction: str, section: str = "") -> str:
    target = f"\n\nFocus your changes on the '{section}' section." if section.strip() else ""
    return (
        f"Refinement instruction: {instruction}{target}\n\n"
        "Current SKILL.md:\n<skill>\n" + skill_md.strip() + "\n</skill>"
    )


# ---------------------------------------------------------------------------
# Base -> Overlay (hierarchical skills)
# ---------------------------------------------------------------------------
def overlay_system() -> str:
    return (
        SKILL_MD_GUIDE + "\n\n## Current task\nYou are creating a SPECIALIST overlay skill that "
        "extends an existing BASE skill. Do NOT duplicate what the base already covers. "
        "Assume the base skill is also active. Add only the subject-specific, "
        "non-obvious knowledge, watchpoints, and templates unique to this specialisation. "
        "In the description, make clear it specialises the base skill and state its own "
        "trigger conditions. Output only the complete overlay SKILL.md, no fences, no "
        "commentary."
    )


def overlay_user(base_md: str, entity: str, spec: SkillSpec) -> str:
    return (
        f"Create a specialist overlay for: {entity}\n\n"
        f"Overlay spec:\n{_render_spec(spec)}\n\n"
        "The base skill it extends is:\n<base_skill>\n"
        + base_md.strip()
        + "\n</base_skill>"
        + _context_block(spec.reference_text)
    )
