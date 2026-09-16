"""YAML loader for eval sets.

Eval sets live under ``evals/`` (configurable via ``SF_EVALS_DIR``). Each
``*.yaml`` file describes one held-out prompt set.

Format (see ``evals/backend-api-engineer.yaml`` for a real example)::

    name: backend-api-engineer-eval
    description: Held-out API design prompts
    version: 1
    pass_threshold: 0.5
    judge:
      prompt: |
        ...
    prompts:
      - id: idempotency-design
        prompt: |
          Design a POST /transfers endpoint...
        expected_traits:
          - "discusses idempotency keys"
          - ...
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from .types import EvalSet

DEFAULT_EVALS_DIR = Path(__file__).resolve().parent.parent.parent / "evals"


def evals_dir() -> Path:
    """Resolve the eval-sets directory (env-overridable for tests / CI)."""

    raw = os.environ.get("SF_EVALS_DIR")
    return Path(raw) if raw else DEFAULT_EVALS_DIR


def list_eval_sets(directory: Path | None = None) -> list[str]:
    """Return the stems of ``*.yaml``/``*.yml`` files in ``directory`` (sorted)."""

    p = Path(directory) if directory is not None else evals_dir()
    if not p.exists():
        return []
    stems: set[str] = set()
    for ext in ("*.yaml", "*.yml"):
        stems.update(f.stem for f in p.glob(ext))
    return sorted(stems)


def load_eval_set(name: str, directory: Path | None = None) -> EvalSet:
    """Load an eval set by stem (with or without ``.yaml``)."""

    stem = name
    for suffix in (".yaml", ".yml"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    p = Path(directory) if directory is not None else evals_dir()
    for ext in (".yaml", ".yml"):
        candidate = p / f"{stem}{ext}"
        if candidate.exists():
            data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                raise ValueError(
                    f"Eval set '{name}' must be a YAML mapping at the top level, "
                    f"got {type(data).__name__}."
                )
            return EvalSet.from_dict(data)
    raise FileNotFoundError(f"No eval set named '{name}' in {p} (looked for .yaml and .yml).")
