"""Tests for the ``run`` command — the close-the-loop CLI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from skill_factory.models import SkillMeta, SkillSpec
from skill_factory.run import cli_main, run_skill
from skill_factory.skill_store import SkillStore


def _save_demo_skill(tmp_path: Path, slug: str = "demo-skill") -> int:
    """Save a real-looking skill to ``tmp_path`` and return the version."""

    store = SkillStore(tmp_path)
    spec = SkillSpec(
        name=slug,
        description="Use when testing the run command end-to-end.",
        skill_type="domain-expert",
    )
    content = (
        "---\n"
        f"name: {slug}\n"
        "description: |\n"
        "  Use when testing the run command end-to-end.\n"
        "---\n"
        "# System Prompt Body\n"
        "You are a precise, careful assistant. Always cite your sources.\n"
    )
    return store.save_new_version(slug, content, SkillMeta.from_spec(spec))


class FakeClient:
    """Minimal LLMClient stand-in that returns a canned response."""

    default_model = "fake-model"

    def __init__(self, content: str = "Hello back.") -> None:
        self._content = content
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str, model: str | None = None, **_kw):
        self.calls.append({"system": system, "user": user, "model": model})
        m = MagicMock()
        m.content = self._content
        m.usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        return m


def test_run_skill_injects_body_as_system_prompt(tmp_path: Path):
    _save_demo_skill(tmp_path)
    store = SkillStore(tmp_path)
    client = FakeClient(content="Output text")
    result = run_skill(
        store,
        client,
        slug="demo-skill",
        prompt="User question?",
    )
    assert result.ok is True
    assert result.output == "Output text"
    assert "System Prompt Body" in client.calls[0]["system"]
    assert client.calls[0]["user"] == "User question?"


def test_run_skill_uses_provided_model(tmp_path: Path):
    _save_demo_skill(tmp_path)
    store = SkillStore(tmp_path)
    client = FakeClient()
    result = run_skill(
        store,
        client,
        slug="demo-skill",
        prompt="q",
        model="custom-model",
    )
    assert result.model == "custom-model"
    assert client.calls[0]["model"] == "custom-model"


def test_run_skill_missing_skill_returns_error(tmp_path: Path):
    store = SkillStore(tmp_path)
    client = FakeClient()
    result = run_skill(store, client, slug="does-not-exist", prompt="q")
    assert result.ok is False
    assert "not found" in (result.error or "")


def test_run_skill_specific_version(tmp_path: Path):
    store = SkillStore(tmp_path)
    spec = SkillSpec(name="v", description="multi-version test")
    store.save_new_version(
        "v",
        "---\nname: v\n---\n# V1 body",
        SkillMeta.from_spec(spec, version=1, version_notes="v1"),
    )
    store.save_new_version(
        "v",
        "---\nname: v\n---\n# V2 body",
        SkillMeta.from_spec(spec, version=2, version_notes="v2"),
    )

    client = FakeClient()
    result = run_skill(store, client, slug="v", prompt="q", version=2)
    assert result.ok is True
    assert "V2 body" in client.calls[0]["system"]


def test_run_skill_populates_metadata(tmp_path: Path):
    v = _save_demo_skill(tmp_path)
    store = SkillStore(tmp_path)
    client = FakeClient(content="Done.")
    result = run_skill(store, client, slug="demo-skill", prompt="x")
    assert result.skill_version == v
    assert result.skill_description == "Use when testing the run command end-to-end."
    assert result.usage["total_tokens"] == 15


def test_cli_quiet_prints_just_output(tmp_path: Path, monkeypatch, capsys):
    """``--quiet`` should print just the model output, one logical line."""
    _save_demo_skill(tmp_path, slug="cli-skill")

    # Monkey-patch the LLM client so the CLI doesn't need a real key.
    from skill_factory.run import cli as cli_mod

    fake = FakeClient(content="Just the output.")
    monkeypatch.setattr(cli_mod, "client_from_settings", lambda: fake)

    rc = cli_main(
        [
            "cli-skill",
            "--prompt",
            "Tell me something",
            "--quiet",
            "--skills-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip() == "Just the output."


def test_cli_json_emits_record(tmp_path: Path, monkeypatch, capsys):
    _save_demo_skill(tmp_path, slug="cli-skill")

    from skill_factory.run import cli as cli_mod

    fake = FakeClient(content="JSON output.")
    monkeypatch.setattr(cli_mod, "client_from_settings", lambda: fake)

    rc = cli_main(
        [
            "cli-skill",
            "--prompt",
            "x",
            "--json",
            "--skills-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    blob = json.loads(capsys.readouterr().out)
    assert blob["skill_slug"] == "cli-skill"
    assert blob["output"] == "JSON output."
    assert blob["ok"] is True


def test_cli_missing_skill_returns_error_code(tmp_path: Path, monkeypatch, capsys):
    from skill_factory.run import cli as cli_mod

    fake = FakeClient()
    monkeypatch.setattr(cli_mod, "client_from_settings", lambda: fake)

    rc = cli_main(
        [
            "does-not-exist",
            "--prompt",
            "x",
            "--skills-dir",
            str(tmp_path),
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "not found" in err


def test_cli_resolves_latest_when_no_version_given(tmp_path: Path, monkeypatch):
    """With no --version, the CLI picks the latest version of the skill."""

    store = SkillStore(tmp_path)
    spec = SkillSpec(name="v", description="latest version test")
    store.save_new_version(
        "v",
        "---\nname: v\n---\n# V1 body",
        SkillMeta.from_spec(spec, version=1),
    )
    store.save_new_version(
        "v",
        "---\nname: v\n---\n# V3 body",
        SkillMeta.from_spec(spec, version=3),
    )

    from skill_factory.run import cli as cli_mod

    fake = FakeClient()
    monkeypatch.setattr(cli_mod, "client_from_settings", lambda: fake)

    rc = cli_main(
        [
            "v",
            "--prompt",
            "x",
            "--skills-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    assert "V3 body" in fake.calls[0]["system"]
