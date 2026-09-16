"""``python -m skill_factory eval <slug> [--eval-set NAME] [...]`` CLI.

Examples::

    python -m skill_factory eval backend-api-engineer
    python -m skill_factory eval qnb-analyst --eval-set financial-statement-analyst \\
        --model anthropic/claude-sonnet-4.6 --judge-model openai/gpt-4o-mini
    python -m skill_factory eval backend-api-engineer --eval-set backend-api-engineer \\
        --version 2 --json
    python -m skill_factory eval backend-api-engineer --dry-run  # show what would run
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from ..config import get_settings
from ..llm_client import LLMError, client_from_settings
from ..logging_setup import configure_logging
from ..skill_store import SkillStore
from . import list_eval_sets, load_eval_set, run_eval, save_report_to_skill_meta
from .loader import evals_dir


def _resolve_store(skills_dir: str | None) -> SkillStore:
    if skills_dir:
        return SkillStore(Path(skills_dir))
    return SkillStore(Path(get_settings().skills_dir))


def _default_eval_set_for_slug(slug: str) -> str | None:
    """Pick a default eval set for a slug by name-matching the eval stems."""

    stems = list_eval_sets()
    if slug in stems:
        return slug
    for stem in stems:
        if slug in stem or stem in slug:
            return stem
    return None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m skill_factory eval",
        description=(
            "Run an eval set against a saved skill and report the lift over "
            "the base model (with bootstrap 95% CI)."
        ),
    )
    p.add_argument("slug", help="Skill slug to evaluate (must already be saved).")
    p.add_argument(
        "--version",
        "-v",
        type=int,
        default=None,
        help="Specific skill version to evaluate (defaults to latest).",
    )
    p.add_argument(
        "--eval-set",
        default=None,
        help=(
            "Eval set name (stem of a YAML under evals/). Defaults to the slug "
            "if a matching set exists, else the first available set."
        ),
    )
    p.add_argument(
        "--model",
        default=None,
        help="Model id to evaluate on. Defaults to the configured default model.",
    )
    p.add_argument(
        "--judge-model",
        default=None,
        help="Model id used by the LLM-as-judge. Defaults to the eval model.",
    )
    p.add_argument(
        "--n-bootstrap",
        type=int,
        default=1000,
        help="Bootstrap resample count for the lift CI (default 1000).",
    )
    p.add_argument(
        "--bootstrap-seed",
        type=int,
        default=0,
        help="RNG seed for the bootstrap (deterministic by default).",
    )
    p.add_argument(
        "--skills-dir",
        default=None,
        help="Override the skills directory (default: SKILLS_DIR or ./skills).",
    )
    p.add_argument(
        "--evals-dir",
        default=None,
        help="Override the eval-sets directory (default: ./evals).",
    )
    p.add_argument(
        "--save",
        action="store_true",
        help="Persist the report into the skill's metadata.json.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON report on stdout.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without making any LLM calls.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _build_parser().parse_args(argv)

    # Override the eval-sets dir for this run if requested.
    if args.evals_dir:
        import os

        os.environ["SF_EVALS_DIR"] = args.evals_dir

    store = _resolve_store(args.skills_dir)
    if not store.exists(args.slug, args.version):
        print(
            f"❌ skill '{args.slug}' (version={args.version or 'latest'}) not found.",
            file=sys.stderr,
        )
        return 2

    # Resolve eval set.
    eval_set_name = args.eval_set or _default_eval_set_for_slug(args.slug)
    if not eval_set_name:
        available = list_eval_sets()
        if not available:
            print(
                f"❌ no eval sets found in {evals_dir()}. "
                "Add a YAML under evals/ or pass --eval-set.",
                file=sys.stderr,
            )
            return 2
        eval_set_name = available[0]
        print(f"note: defaulting to eval set '{eval_set_name}'", file=sys.stderr)

    try:
        eval_set = load_eval_set(eval_set_name)
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(
            json.dumps(
                {
                    "skill": args.slug,
                    "version": args.version or store.latest_version(args.slug),
                    "eval_set": eval_set.to_dict(),
                    "model": args.model,
                    "judge_model": args.judge_model,
                    "n_prompts": len(eval_set.prompts),
                    "evals_dir": str(evals_dir()),
                    "skills_dir": str(store.root),
                },
                indent=2,
            )
        )
        return 0

    # Build the client and run.
    try:
        client = client_from_settings()
    except LLMError as exc:
        print(f"❌ could not build LLM client: {exc}", file=sys.stderr)
        return 2

    skill_version = args.version or store.latest_version(args.slug)
    skill_md = store.load_content(args.slug, skill_version)

    print(
        f"▶ evaluating '{args.slug}' v{skill_version} on '{eval_set.name}' "
        f"({len(eval_set.prompts)} prompts)…",
        file=sys.stderr,
    )

    report = run_eval(
        client,
        eval_set,
        skill_md=skill_md,
        skill_slug=args.slug,
        skill_version=skill_version,
        model=args.model,
        judge_model=args.judge_model,
        n_bootstrap=args.n_bootstrap,
        bootstrap_seed=args.bootstrap_seed,
    )

    if args.save:
        save_report_to_skill_meta(store, args.slug, skill_version, report)
        print(f"💾 saved report to {args.slug}/v{skill_version}/metadata.json", file=sys.stderr)

    if args.json:
        # Trim large free-form outputs before printing to keep --json useful in pipes.
        blob = asdict(report)
        for pr in blob.get("prompt_results", []):
            pr["base_output"] = (pr.get("base_output") or "")[:200]
            pr["skill_output"] = (pr.get("skill_output") or "")[:200]
        json.dump(blob, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print()
        print(f"  eval set : {report.eval_set_name} (n={report.n_prompts})")
        print(f"  eval model: {report.eval_model}")
        print(f"  judge     : {report.judge_model}")
        print()

        # Judge self-calibration controls first (so warnings are loud).
        if report.control_results:
            plural = "s" if len(report.control_results) > 1 else ""
            print(f"  judge calibration ({len(report.control_results)} control{plural}):")
            for c in report.control_results:
                ok = "✓" if c["within_tolerance"] else "✗"
                print(
                    f"    [{ok}] {c['id']:<28} expected={c['expected_score']:.1f} "
                    f"judge={c['judge_score']:.1f} delta={c['delta']:+.1f}"
                )
                if c["warning"]:
                    print(f"        WARNING: {c['warning']}")
            if not report.judge_calibration_ok():
                print()
                print(
                    "  WARNING: judge is miscalibrated — the lift number below "
                    "should be treated with caution until controls pass."
                )
            print()

        print(f"  base pass  : {report.base_pass_rate:>6.1%}")
        print(f"  skill pass : {report.skill_pass_rate:>6.1%}")
        print(f"  lift       : {report.lift_pp:+6.1f}pp")
        print(
            f"  95% CI     : [{report.lift_ci_low_pp:+5.1f}, {report.lift_ci_high_pp:+5.1f}]pp "
            f"(bootstrap n={report.n_bootstrap})"
        )
        print()

        # Per-prompt mini-table.
        header = f"  {'prompt_id':<28} {'base':>5} {'skill':>5}  {'lift':>6}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for pr in report.prompt_results:
            base_mark = "✓" if pr.base_passed else "✗"
            skill_mark = "✓" if pr.skill_passed else "✗"
            per_lift_pp = (pr.skill_score - pr.base_score) * 100.0
            print(f"  {pr.prompt_id:<28} {base_mark:>5} {skill_mark:>5}  {per_lift_pp:+6.1f}")
        print()
        verdict = (
            "✓ lift > 0"
            if report.lift_pp > 0 and report.lift_ci_low_pp > 0
            else (
                "≈ no clear lift (CI overlaps 0)"
                if report.lift_ci_low_pp <= 0 <= report.lift_ci_high_pp
                else "✗ lift < 0"
            )
        )
        print(f"  {verdict}")
        print()

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
