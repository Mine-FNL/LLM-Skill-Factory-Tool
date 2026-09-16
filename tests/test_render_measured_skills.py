"""Tests for ``scripts/render_measured_skills.py``.

We don't need a real network — we just exercise the walker + table renderer
against a fixture layout, and verify it skips placeholder rows by default.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "render_measured_skills.py"


@pytest.fixture
def fixture_tree(tmp_path: Path):
    """Lay down a fake examples/ tree with three skills."""

    # One measured skill (real lift).
    (tmp_path / "examples" / "a-skill" / "v1").mkdir(parents=True)
    (tmp_path / "examples" / "a-skill" / "v1" / "metadata.json").write_text(
        json.dumps(
            {
                "name": "a-skill",
                "version": 1,
                "lift_pp": 30.0,
                "lift_ci_pp": [10.0, 50.0],
                "base_pass_rate": 0.4,
                "skill_pass_rate": 0.7,
                "n_prompts": 5,
                "last_eval_set": "demo",
                "eval_model": "m1",
                "notes": {},
            }
        ),
        encoding="utf-8",
    )

    # One illustrative placeholder.
    (tmp_path / "examples" / "b-skill" / "v1").mkdir(parents=True)
    (tmp_path / "examples" / "b-skill" / "v1" / "metadata.json").write_text(
        json.dumps(
            {
                "name": "b-skill",
                "version": 1,
                "lift_pp": 35.0,
                "lift_ci_pp": [12.0, 59.0],
                "base_pass_rate": 0.5,
                "skill_pass_rate": 0.85,
                "n_prompts": 1,
                "last_eval_set": "demo",
                "eval_model": "illustrative",
                "notes": {"illustrative": True},
            }
        ),
        encoding="utf-8",
    )

    # One unmeasured skill (no lift_pp).
    (tmp_path / "examples" / "c-skill" / "v1").mkdir(parents=True)
    (tmp_path / "examples" / "c-skill" / "v1" / "metadata.json").write_text(
        json.dumps(
            {
                "name": "c-skill",
                "version": 1,
                "lift_pp": 0.0,
                "notes": {},
            }
        ),
        encoding="utf-8",
    )

    return tmp_path


def _run(args: list[str]) -> str:
    """Run the script with extra --search-dir args and capture stdout."""
    return subprocess.check_output(
        [sys.executable, str(SCRIPT), *args],
        text=True,
    )


def test_iter_metadata_via_cli(fixture_tree: Path) -> None:
    """The CLI should walk our fixture tree and emit JSON we can inspect."""
    out = _run(["--json", "--search-dir", str(fixture_tree / "examples")])
    blob = json.loads(out)
    names = {r["name"] for r in blob}
    assert "a-skill" in names
    assert "b-skill" not in names  # illustrative, excluded by default
    assert "c-skill" not in names  # zero lift, excluded


def test_default_excludes_illustrative(fixture_tree: Path) -> None:
    out = _run(["--search-dir", str(fixture_tree / "examples")])
    assert "a-skill" in out
    assert "b-skill" not in out
    assert "c-skill" not in out


def test_illustrative_flag_includes_placeholders(fixture_tree: Path) -> None:
    out = _run(["--illustrative", "--search-dir", str(fixture_tree / "examples")])
    assert "a-skill" in out
    assert "b-skill" in out  # now included


def test_empty_when_no_measurements(fixture_tree: Path) -> None:
    """A clean tree produces the 'no skills measured yet' placeholder."""
    # Wipe the measured row.
    (fixture_tree / "examples" / "a-skill" / "v1" / "metadata.json").unlink()
    out = _run(["--search-dir", str(fixture_tree / "examples")])
    assert "No skills have been measured yet" in out


def test_helper_api_directly(fixture_tree: Path) -> None:
    """The internal helpers can be invoked as a regular Python module."""
    sys.path.insert(0, str(SCRIPT.parent))
    import render_measured_skills as rms

    rows = rms._iter_metadata([fixture_tree / "examples"])
    assert {r["name"] for r in rows} == {"a-skill", "b-skill", "c-skill"}

    assert rms._is_illustrative({"notes": {"illustrative": True}}) is True
    assert rms._is_illustrative({"notes": {}}) is False

    table = rms._render_table(
        [
            {
                "name": "x",
                "version": 1,
                "last_eval_set": "demo",
                "lift_pp": 10.0,
                "lift_ci_pp": [0.0, 20.0],
                "n_prompts": 3,
                "base_pass_rate": 0.3,
                "skill_pass_rate": 0.4,
                "eval_model": "m",
            }
        ]
    )
    assert "+10.0" in table
    assert "x" in table


def test_env_var_overrides_search_dirs(fixture_tree: Path) -> None:
    """``SF_MEASURED_SEARCH_DIRS`` works for tests + automation."""
    env = {"SF_MEASURED_SEARCH_DIRS": str(fixture_tree / "examples")}
    out = subprocess.check_output(
        [sys.executable, str(SCRIPT), "--json"],
        text=True,
        env={**__import__("os").environ, **env},
    )
    blob = json.loads(out)
    names = {r["name"] for r in blob}
    assert "a-skill" in names
