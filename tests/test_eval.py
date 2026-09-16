"""Tests for the eval harness."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from skill_factory import eval as _eval_pkg
from skill_factory.eval import (
    EvalPrompt,
    EvalReport,
    EvalSet,
    JudgeConfig,
    bootstrap_lift_ci,
    judge_response,
    list_eval_sets,
    load_eval_set,
    parse_score,
    run_eval,
    save_report_to_skill_meta,
)
from skill_factory.eval.cli import _default_eval_set_for_slug
from skill_factory.models import SkillMeta, SkillSpec
from skill_factory.skill_store import SkillStore


# ---------------------------------------------------------------------------
# Score parsing
# ---------------------------------------------------------------------------
class TestParseScore:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1", 1.0),
            ("0", 0.0),
            ("0.5", 0.5),
            ("  1  ", 1.0),
            ("Score: 1", 1.0),
            ("Verdict = 0.5", 0.5),
            ("`0`", 0.0),
            ("rating: 1.0\n", 1.0),
            ("\n\n0.5\n", 0.5),
            ("0.49", 0.5),  # closest-snap rounding
            ("0.74", 0.5),  # 0.74 is closer to 0.5 than to 1.0
            ("0.26", 0.5),
        ],
    )
    def test_legal_values(self, raw: str, expected: float) -> None:
        assert parse_score(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "nope",
            "Score: maybe",
            "1.5",  # out of range
            "-0.1",
        ],
    )
    def test_unparseable_returns_none(self, raw: str) -> None:
        assert parse_score(raw) is None


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------
class TestBootstrapCI:
    def test_zero_lift_is_zero_ci(self):
        # Both arms identical → lift distribution centered on zero.
        passed = [True, False, True, False, True, False, True, False]
        lo, hi = bootstrap_lift_ci(passed, passed, n_bootstrap=500, seed=0)
        assert abs(lo) < 1e-6 and abs(hi) < 1e-6

    def test_positive_lift_has_positive_ci(self):
        # Mixed inputs so the bootstrap actually has variance.
        base = [True, False, True, False, True, False, True, False, True, False]
        skill = [True, True, True, False, True, True, True, False, True, True]
        lo, hi = bootstrap_lift_ci(base, skill, n_bootstrap=500, seed=0)
        assert lo > 0.0
        assert hi > lo
        assert hi <= 100.0

    def test_negative_lift_has_negative_ci(self):
        base = [True, True, True, False, True, True, True, False, True, True]
        skill = [True, False, True, False, True, False, True, False, True, False]
        lo, hi = bootstrap_lift_ci(base, skill, n_bootstrap=500, seed=0)
        assert hi < 0.0
        assert lo < hi
        assert lo >= -100.0

    def test_empty_returns_zeros(self):
        assert bootstrap_lift_ci([], [], n_bootstrap=10) == (0.0, 0.0)

    def test_mismatched_lengths_returns_zeros(self):
        assert bootstrap_lift_ci([True], [True, False], n_bootstrap=10) == (0.0, 0.0)

    def test_zero_bootstrap_returns_zeros(self):
        assert bootstrap_lift_ci([True, False], [True, True], n_bootstrap=0) == (0.0, 0.0)

    def test_deterministic_with_seed(self):
        # Same seed → same CI.
        a = bootstrap_lift_ci(
            [True, False, True, True, False],
            [True, True, True, False, True],
            n_bootstrap=300,
            seed=42,
        )
        b = bootstrap_lift_ci(
            [True, False, True, True, False],
            [True, True, True, False, True],
            n_bootstrap=300,
            seed=42,
        )
        assert a == b


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------
class TestEvalSetLoader:
    def test_lists_reference_sets(self):
        names = list_eval_sets()
        # Three reference YAMLs ship in the repo.
        assert "backend-api-engineer" in names
        assert "quant-research-analyst" in names
        assert "financial-statement-analyst" in names

    def test_loads_backend_set(self):
        s = load_eval_set("backend-api-engineer")
        assert s.name == "backend-api-engineer"
        assert s.pass_threshold == 0.5
        assert len(s.prompts) >= 5
        for p in s.prompts:
            assert p.id
            assert p.prompt
            assert isinstance(p.expected_traits, list)

    def test_load_with_extension_strips_it(self):
        s = load_eval_set("backend-api-engineer.yaml")
        assert s.name == "backend-api-engineer"

    def test_missing_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_eval_set("does-not-exist", directory=tmp_path)

    def test_roundtrip(self):
        s = load_eval_set("quant-research-analyst")
        blob = s.to_dict()
        restored = EvalSet.from_dict(blob)
        assert restored.name == s.name
        assert len(restored.prompts) == len(s.prompts)


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------
class FakeClient:
    """Captures calls and returns canned responses."""

    def __init__(self, verdicts: list[float], default_model: str = "fake-model"):
        self._verdicts = list(verdicts)
        self._idx = 0
        self.default_model = default_model
        self.calls: list[dict] = []

    def complete(
        self, *, system: str, user: str, model: str | None = None, **_: object
    ) -> MagicMock:
        self.calls.append({"system": system, "user": user, "model": model})
        score = self._verdicts[self._idx % len(self._verdicts)]
        self._idx += 1
        m = MagicMock()
        m.content = str(score)
        return m


class TestJudgeScoring:
    def test_returns_parsed_score(self):
        client = FakeClient([1.0])
        prompt = EvalPrompt(id="p", prompt="q?", expected_traits=["a"])
        score = judge_response(client, prompt, "response", JudgeConfig(), judge_model="m")
        assert score == 1.0
        assert client.calls[0]["model"] == "m"

    def test_unparseable_defaults_to_zero(self):
        client = FakeClient(["nope"])
        prompt = EvalPrompt(id="p", prompt="q?", expected_traits=["a"])
        score = judge_response(client, prompt, "response", JudgeConfig(), judge_model="m")
        assert score == 0.0

    def test_prompt_contains_expected_traits(self):
        client = FakeClient([0.5])
        prompt = EvalPrompt(
            id="p", prompt="What is X?", expected_traits=["mentions X", "explains Y"]
        )
        judge_response(client, prompt, "answer", JudgeConfig(), judge_model="m")
        sent = client.calls[0]["user"]
        assert "mentions X" in sent
        assert "explains Y" in sent
        assert "answer" in sent


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
class TestRunner:
    def _eval_set(self) -> EvalSet:
        return EvalSet(
            name="unit",
            prompts=[
                EvalPrompt(id="a", prompt="q1?", expected_traits=["t1"]),
                EvalPrompt(id="b", prompt="q2?", expected_traits=["t2"]),
                EvalPrompt(id="c", prompt="q3?", expected_traits=["t3"]),
                EvalPrompt(id="d", prompt="q4?", expected_traits=["t4"]),
            ],
            pass_threshold=0.5,
        )

    def _scripted_client(self) -> FakeClient:
        # Pattern: base pass=False, skill pass=True → +50pp lift.
        # Judge verdicts in order: base, judge, skill, judge (xN prompts).
        verdicts = []
        for _ in range(4):
            verdicts += [0.0, 0.0, 1.0, 1.0]  # base=0, judge-base=0, skill=1, judge-skill=1
        return FakeClient(verdicts)

    def test_lift_when_skill_beats_base(self):
        client = self._scripted_client()
        report = run_eval(
            client,
            self._eval_set(),
            skill_md="# Body",
            skill_slug="x",
            model="m",
            n_bootstrap=200,
            bootstrap_seed=0,
        )
        assert report.n_prompts == 4
        assert report.base_pass_rate == 0.0
        assert report.skill_pass_rate == 1.0
        assert report.lift_pp == pytest.approx(100.0, abs=1e-6)
        assert report.lift_ci_low_pp > 0
        assert report.lift_ci_high_pp <= 100.0

    def test_no_skill_arm_only_base(self):
        # With skill_md=None, only the base arm is meaningful.
        client = FakeClient([1.0] * 8)  # judge always returns 1
        report = run_eval(
            client,
            self._eval_set(),
            skill_md=None,
            model="m",
            n_bootstrap=50,
        )
        assert report.base_pass_rate == 1.0
        assert report.skill_pass_rate == 0.0
        assert report.lift_pp == pytest.approx(-100.0, abs=1e-6)

    def test_save_persists_to_metadata(self, tmp_path: Path):
        store = SkillStore(tmp_path)
        spec = SkillSpec(name="demo", description="Use when demoing.")
        store.save_new_version("demo", "---\nname: demo\n---\nbody", SkillMeta.from_spec(spec))
        client = self._scripted_client()
        report = run_eval(client, self._eval_set(), skill_md="body", skill_slug="demo", model="m")
        save_report_to_skill_meta(store, "demo", 1, report)

        reloaded = store.load_meta("demo", 1)
        assert reloaded.lift_pp == pytest.approx(100.0, abs=1e-6)
        assert len(reloaded.eval_results or []) == 1
        assert reloaded.last_eval_set == "unit"

    def test_save_appends_history_with_cap(self, tmp_path: Path):
        store = SkillStore(tmp_path)
        spec = SkillSpec(name="demo", description="Use when demoing.")
        store.save_new_version("demo", "---\nname: demo\n---\nbody", SkillMeta.from_spec(spec))
        client = self._scripted_client()
        # 25 reports — cap should keep the latest 20.
        for _ in range(25):
            r = run_eval(client, self._eval_set(), skill_md="body", skill_slug="demo", model="m")
            save_report_to_skill_meta(store, "demo", 1, r)
        reloaded = store.load_meta("demo", 1)
        assert len(reloaded.eval_results or []) == 20

    def test_metadata_round_trip_with_eval_fields(self, tmp_path: Path):
        """Older metadata.json files without eval fields still load cleanly."""
        import json as _json

        # Write an "old" metadata.json without any eval fields.
        vdir = tmp_path / "demo" / "v1"
        vdir.mkdir(parents=True)
        (vdir / "SKILL.md").write_text("---\nname: demo\n---\nbody", encoding="utf-8")
        (vdir / "metadata.json").write_text(
            _json.dumps(
                {
                    "name": "demo",
                    "description": "x",
                    "version": 1,
                }
            ),
            encoding="utf-8",
        )

        store = SkillStore(tmp_path)
        meta = store.load_meta("demo", 1)
        # Eval fields should default, not crash.
        assert meta.lift_pp == 0.0
        assert meta.lift_ci_pp == (0.0, 0.0)
        assert meta.eval_results == []


# ---------------------------------------------------------------------------
# CLI default-set selection
# ---------------------------------------------------------------------------
class TestCliDefaults:
    def test_exact_slug_match(self):
        assert _default_eval_set_for_slug("backend-api-engineer") == "backend-api-engineer"

    def test_no_match_falls_back_to_first(self):
        # If no stem matches, returns None — caller picks the first available.
        assert _default_eval_set_for_slug("totally-unrelated-xyz") is None


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------
def test_package_exports():
    for name in (
        "EvalSet",
        "EvalPrompt",
        "EvalReport",
        "JudgeConfig",
        "load_eval_set",
        "list_eval_sets",
        "run_eval",
        "bootstrap_lift_ci",
        "judge_response",
        "parse_score",
        "save_report_to_skill_meta",
    ):
        assert hasattr(_eval_pkg, name), f"missing export: {name}"


def test_json_serializable_report():
    r = EvalReport(skill_slug="x", eval_set_name="y", n_prompts=1, lift_pp=10.0)
    blob = json.dumps(r.to_dict())
    assert "lift_pp" in blob


def test_report_summary_format():
    r = EvalReport(
        skill_slug="x",
        eval_set_name="y",
        n_prompts=10,
        base_pass_rate=0.4,
        skill_pass_rate=0.6,
        lift_pp=20.0,
        lift_ci_low_pp=5.0,
        lift_ci_high_pp=35.0,
        n_bootstrap=1000,
    )
    s = r.summary()
    assert "+20.0" in s
    assert "[+5.0" in s
    assert "n=10" in s
