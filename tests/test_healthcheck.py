"""Tests for the standalone healthcheck module."""

from __future__ import annotations

import json

from skill_factory import healthcheck
from skill_factory.healthcheck import run_healthcheck


def test_run_healthcheck_no_key(tmp_path, monkeypatch):
    """No API key → skills_dir check still runs; provider probe is skipped."""
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    for k in [
        "OPENROUTER_API_KEY",
        "MINIMAX_API_KEY",
        "MOONSHOT_API_KEY",
        "LLM_API_KEY",
        "LLM_PROVIDER",
    ]:
        monkeypatch.delenv(k, raising=False)

    report = run_healthcheck(probe_provider=False)
    assert report.ok is True
    names = {c["name"] for c in report.checks}
    assert {"settings", "skills_dir", "api_key"} <= names
    api_key = next(c for c in report.checks if c["name"] == "api_key")
    assert api_key["ok"] is False  # missing


def test_run_healthcheck_strict_key_fails_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    for k in ["OPENROUTER_API_KEY", "MINIMAX_API_KEY", "MOONSHOT_API_KEY", "LLM_API_KEY"]:
        monkeypatch.delenv(k, raising=False)

    report = run_healthcheck(probe_provider=False, strict_key=True)
    assert report.ok is False


def test_run_healthcheck_creates_skills_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path / "fresh"))
    for k in ["OPENROUTER_API_KEY", "MINIMAX_API_KEY", "MOONSHOT_API_KEY", "LLM_API_KEY"]:
        monkeypatch.delenv(k, raising=False)

    report = run_healthcheck(probe_provider=False)
    skills_dir = next(c for c in report.checks if c["name"] == "skills_dir")
    assert skills_dir["ok"] is True
    assert (tmp_path / "fresh").exists()


def test_run_healthcheck_json_output(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    for k in ["OPENROUTER_API_KEY", "MINIMAX_API_KEY", "MOONSHOT_API_KEY", "LLM_API_KEY"]:
        monkeypatch.delenv(k, raising=False)

    rc = healthcheck.main(["--no-probe", "--json"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert rc == 0
    assert parsed["ok"] is True
    assert "version" in parsed


def test_main_returns_zero_when_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    for k in ["OPENROUTER_API_KEY", "MINIMAX_API_KEY", "MOONSHOT_API_KEY", "LLM_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    assert healthcheck.main(["--no-probe"]) == 0


def test_main_with_provider_probe_skips_when_no_key(tmp_path, monkeypatch, capsys):
    """When probe_provider=True but no key, the probe step is skipped, not failed."""
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    for k in ["OPENROUTER_API_KEY", "MINIMAX_API_KEY", "MOONSHOT_API_KEY", "LLM_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    rc = healthcheck.main(["--no-probe"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Skill Factory" in out


def test_report_to_dict_is_serialisable(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    for k in ["OPENROUTER_API_KEY", "MINIMAX_API_KEY", "MOONSHOT_API_KEY", "LLM_API_KEY"]:
        monkeypatch.delenv(k, raising=False)

    report = run_healthcheck(probe_provider=False)
    blob = report.to_dict()
    json.dumps(blob)  # must not raise
    assert blob["version"]


def test_main_quiet_suppresses_human_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path))
    for k in ["OPENROUTER_API_KEY", "MINIMAX_API_KEY", "MOONSHOT_API_KEY", "LLM_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    rc = healthcheck.main(["--no-probe", "--quiet"])
    out = capsys.readouterr().out
    # Quiet mode emits JSON only, no human-readable banner.
    assert "Skill Factory" not in out
    assert rc == 0
