from skill_factory import meta_prompts as mp
from skill_factory.models import SkillSpec


def _spec():
    return SkillSpec(
        name="my-skill",
        description="Use when analysing widgets.",
        skill_type="specialist",
        domain_focus="widget analysis",
        tags=["widgets", "analysis"],
        entities=["Acme Corp"],
        requirements=["Cover defects", "Add a checklist"],
        base_skill="widget-base",
        token_budget=900,
        tone="concise",
        reference_text="Widgets were invented in 1999.",
    )


def test_guide_encodes_core_rules():
    g = mp.SKILL_MD_GUIDE.lower()
    for rule in [
        "frontmatter",
        "kebab-case",
        "description",
        "imperative",
        "progressive disclosure",
        "non-obvious",
        "code fences",
    ]:
        assert rule in g, rule


def test_outline_prompt_includes_spec_and_planning_instruction():
    spec = _spec()
    sys = mp.outline_system()
    user = mp.outline_user(spec)
    assert "PLANNING" in sys
    assert "my-skill" in user
    assert "Acme Corp" in user
    assert "Cover defects" in user
    assert "Widgets were invented in 1999." in user  # reference block injected


def test_draft_prompt_includes_outline():
    spec = _spec()
    user = mp.draft_user(spec, "1. Overview\n2. Framework")
    assert "1. Overview" in user
    assert "my-skill" in user
    assert "~900 tokens" in user


def test_refine_prompt_targets_section():
    user = mp.refine_user("---\nname: x\n---\nbody", "make it punchier", section="Red Flags")
    assert "make it punchier" in user
    assert "Red Flags" in user
    assert "<skill>" in user


def test_overlay_prompt_includes_base_and_entity():
    spec = _spec()
    sys = mp.overlay_system()
    user = mp.overlay_user("BASE CONTENT HERE", "Acme Corp", spec)
    assert "overlay" in sys.lower()
    assert "BASE CONTENT HERE" in user
    assert "Acme Corp" in user


def test_no_reference_block_when_empty():
    spec = _spec()
    spec.reference_text = ""
    user = mp.outline_user(spec)
    assert "reference_material" not in user
