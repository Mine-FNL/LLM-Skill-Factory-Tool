"""Render a Markdown table of measured skills for the README.

Walks ``examples/**/v*/metadata.json`` and ``skills/**/v*/metadata.json``,
collects every ``SkillMeta`` with a non-zero ``lift_pp``, and prints a
human-readable table. Designed to be copy-pasted into the README.

Run::

    python scripts/render_measured_skills.py

Optional flags::

    --illustrative    include rows with metadata.json notes.illustrative=true
                      (default: exclude — these are placeholder examples)
    --json            emit JSON instead of a Markdown table
    --search-dir PATH additional search root (repeatable). Overrides the default
                      examples/ + skills/ roots. Useful for tests.

Env::

    SF_MEASURED_SEARCH_DIRS  colon-separated (or comma-separated on Windows) list
                             of additional search directories.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEARCH_DIRS = [REPO_ROOT / "examples", REPO_ROOT / "skills"]


def _resolve_search_dirs(extra: list[str]) -> list[Path]:
    """Resolve the list of search directories.

    Precedence (highest first): explicit ``--search-dir`` CLI flags, then
    ``SF_MEASURED_SEARCH_DIRS`` env var, then the default ``examples/ + skills/``
    roots in the repo.
    """

    if extra:
        return [Path(p).resolve() for p in extra]
    env = os.environ.get("SF_MEASURED_SEARCH_DIRS", "").strip()
    if env:
        sep = ";" if os.name == "nt" else ":"
        return [Path(p).resolve() for p in env.split(sep) if p.strip()]
    return list(DEFAULT_SEARCH_DIRS)


def _iter_metadata(search_dirs: list[Path]) -> list[dict[str, Any]]:
    """Yield every ``metadata.json`` under the search dirs (deep-walked)."""

    rows: list[dict[str, Any]] = []
    for root in search_dirs:
        if not root.exists():
            continue
        for meta_path in root.glob("**/v*/metadata.json"):
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            try:
                rel = meta_path.relative_to(REPO_ROOT)
            except ValueError:
                # File is outside the repo (test fixture, etc.) — store absolute.
                rel = meta_path
            data["_path"] = str(rel)
            rows.append(data)
    return rows


def _is_illustrative(data: dict[str, Any]) -> bool:
    # Check both top-level notes and the most-recent eval_result notes.
    if bool(data.get("notes", {}).get("illustrative")):
        return True
    for ev in data.get("eval_results", []) or []:
        if bool(ev.get("notes", {}).get("illustrative")):
            return True
    return False


def _render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            "_No skills have been measured yet. Run "
            "`python -m skill_factory eval <slug> --save` against a saved skill "
            "to populate this table._"
        )
    header = (
        "| Skill | Version | Eval set | Lift | 95% CI | n | Base / Skill | Model |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )
    body_lines: list[str] = []
    for r in rows:
        ci = r.get("lift_ci_pp") or [0.0, 0.0]
        ci_lo, ci_hi = float(ci[0]), float(ci[1]) if len(ci) == 2 else (0.0, 0.0)
        body_lines.append(
            "| `{slug}` | v{version} | `{eval_set}` | **{lift:+.1f}pp** | "
            "[{lo:+.1f}, {hi:+.1f}] | {n} | {base:.0%} / {skill:.0%} | `{model}` |".format(
                slug=r.get("name", "?"),
                version=int(r.get("version", 1)),
                eval_set=r.get("last_eval_set") or "—",
                lift=float(r.get("lift_pp") or 0.0),
                lo=ci_lo,
                hi=ci_hi,
                n=int(r.get("n_prompts") or (len(r.get("eval_results", []) or []) or 0)),
                base=float(r.get("base_pass_rate") or 0.0),
                skill=float(r.get("skill_pass_rate") or 0.0),
                model=(r.get("eval_model") or r.get("model") or "—"),
            )
        )
    return header + "\n".join(body_lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--illustrative",
        action="store_true",
        help="Include illustrative placeholder rows (default: exclude).",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of a Markdown table.")
    p.add_argument(
        "--search-dir",
        action="append",
        default=[],
        help=(
            "Additional search root (repeatable). Overrides the default "
            "examples/ + skills/ roots. Useful for tests."
        ),
    )
    args = p.parse_args(argv)

    search_dirs = _resolve_search_dirs(args.search_dir)
    all_rows = _iter_metadata(search_dirs)
    if not args.illustrative:
        all_rows = [r for r in all_rows if not _is_illustrative(r)]
    # Drop rows with no measured lift (haven't been eval'd).
    all_rows = [r for r in all_rows if (r.get("lift_pp") or 0.0) != 0.0]

    if args.json:
        json.dump(all_rows, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_render_table(all_rows))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
