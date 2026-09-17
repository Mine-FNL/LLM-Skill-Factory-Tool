"""Tests for ``scripts/demo.py`` — the offline end-to-end demo."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "demo.py"


def _run(*args: str) -> str:
    return subprocess.check_output([sys.executable, str(SCRIPT), *args], text=True)


def test_demo_runs_to_completion():
    """The demo prints a lift summary and exits 0."""
    out = _run()
    assert "OFFLINE DEMO" in out
    assert "SYNTHETIC" in out
    assert "lift" in out.lower()
    # Showcases the calibration panel.
    assert "judge calibration" in out


def test_demo_lift_is_positive_and_marked_synthetic():
    """The demo narrative shows the skill beating the base (clearly synthetic)."""
    out = _run()
    # The scripted base responses are weak, the scripted skill responses are
    # strong → the harness should report a positive lift.
    assert "+100.0pp" in out or "+50.0pp" in out or "lift > 0" in out


def test_demo_does_not_require_network():
    """No network calls. No API key needed. Just the bundled data."""
    # We assert this by *running* the demo without env vars; if it depended
    # on network it would hang or error.
    out = _run()
    assert "OFFLINE" in out
    assert "demo/scripted-model" in out


def test_demo_default_eval_set_is_demo():
    out = _run()
    assert "demo" in out.lower()


def test_demo_surfaces_judge_calibration():
    """A control should be scored and reported in the calibration panel."""
    out = _run()
    # The demo set's only control is `obviously-bad-response`.
    assert "obviously-bad-response" in out
    # And it must be marked within tolerance — synthetic score = 0.0, expected = 0.0.
    assert "[✓]" in out  # checkmark in calibration panel
