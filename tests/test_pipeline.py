from skill_factory import pipeline
from skill_factory.models import GenerationResult, SkillSpec


class FakeClient:
    """Captures call args and returns a canned GenerationResult."""

    def __init__(self, content: str):
        self.content = content
        self.calls: list[dict] = []

    def complete(self, *, system, user, model=None, temperature=0.7, max_tokens=None):
        self.calls.append(
            {"system": system, "user": user, "model": model, "temperature": temperature}
        )
        return GenerationResult(content=self.content, model=model or "fake-model")


def _spec():
    return SkillSpec(name="demo", description="Use when X.")


def test_clean_skill_output_strips_fences():
    raw = "```markdown\n---\nname: x\n---\nbody\n```"
    out = pipeline.clean_skill_output(raw)
    assert out.startswith("---")
    assert "```" not in out
    assert out.endswith("\n")


def test_clean_skill_output_strips_preamble():
    raw = "Sure! Here is your skill:\n---\nname: x\n---\nbody"
    out = pipeline.clean_skill_output(raw)
    assert out.startswith("---")
    assert "Sure!" not in out


def test_plan_outline_passes_through():
    client = FakeClient("- Overview\n- Framework")
    res = pipeline.plan_outline(client, _spec(), model="m1")
    assert res.content.startswith("- Overview")
    assert client.calls[0]["model"] == "m1"
    assert "PLANNING" in client.calls[0]["system"]


def test_generate_draft_cleans_output():
    client = FakeClient("```\n---\nname: demo\n---\nAlways do it.\n```")
    res = pipeline.generate_draft(client, _spec(), "outline here")
    assert res.content.startswith("---")
    assert "```" not in res.content
    assert "outline here" in client.calls[0]["user"]


def test_refine_section_cleans_output():
    client = FakeClient("---\nname: demo\n---\nrefined")
    res = pipeline.refine_section(client, "old content", "tighten it", section="Overview")
    assert "refined" in res.content
    assert "tighten it" in client.calls[0]["user"]
    assert "Overview" in client.calls[0]["user"]


def test_generate_overlay_includes_base_and_entity():
    client = FakeClient("---\nname: acme-specialist\n---\noverlay body")
    res = pipeline.generate_overlay(client, "BASE_MD", "Acme Corp", _spec(), model="m2")
    assert "overlay body" in res.content
    assert "BASE_MD" in client.calls[0]["user"]
    assert "Acme Corp" in client.calls[0]["user"]
    assert client.calls[0]["model"] == "m2"
