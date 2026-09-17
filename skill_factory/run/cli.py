"""``python -m skill_factory run ...`` CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config import get_settings
from ..llm_client import LLMError, client_from_settings
from ..logging_setup import configure_logging
from ..skill_store import SkillStore
from .runner import run_skill


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m skill_factory run",
        description=(
            "Load a saved skill, invoke it as a system prompt against a model, "
            "and print the output. Closes the dev loop on top of the eval harness."
        ),
    )
    p.add_argument("slug", help="Skill slug to run.")
    p.add_argument(
        "--prompt",
        "-p",
        required=True,
        help="User prompt to send (the skill is the system prompt).",
    )
    p.add_argument(
        "--version",
        "-v",
        type=int,
        default=None,
        help="Specific skill version (defaults to latest).",
    )
    p.add_argument(
        "--model",
        "-m",
        default=None,
        help="Model id (defaults to the configured default model).",
    )
    p.add_argument(
        "--temperature",
        "-t",
        type=float,
        default=0.7,
        help="Sampling temperature (default 0.7).",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Max output tokens (default 1024).",
    )
    p.add_argument(
        "--skills-dir",
        default=None,
        help="Override the skills directory (default: SKILLS_DIR or ./skills).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON record instead of human-readable output.",
    )
    p.add_argument(
        "--show-system",
        action="store_true",
        help="Print the skill body (system prompt) before the model output.",
    )
    p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Print only the model output (one line trimmed to fit terminal).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _build_parser().parse_args(argv)

    if args.skills_dir:
        store = SkillStore(Path(args.skills_dir))
    else:
        store = SkillStore(Path(get_settings().skills_dir))

    try:
        client = client_from_settings()
    except LLMError as exc:
        print(f"error: could not build LLM client: {exc}", file=sys.stderr)
        return 2

    result = run_skill(
        store,
        client,
        slug=args.slug,
        prompt=args.prompt,
        version=args.version,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    if args.json:
        sys.stdout.write(json.dumps(result.__dict__, indent=2, default=str))
        sys.stdout.write("\n")
        return 0 if result.ok else 1

    if not result.ok:
        print(f"error: {result.error}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f"▶ skill: {result.skill_slug} v{result.skill_version} "
            f"on {result.model} ({result.elapsed_ms}ms)"
        )
        if result.skill_description and not args.quiet:
            print(f"  {result.skill_description}")
        if args.show_system:
            from ..skill_store import SkillStore as _Store  # noqa: F401

            content = store.load_content(result.skill_slug, result.skill_version)
            _fm, body = (
                content.split("---\n", 2)[1:3] if content.startswith("---\n") else ("", content)
            )
            print()
            print("  --- system prompt (skill body) ---")
            print(body.strip())
            print("  --- end system prompt ---")
        print()
        print(result.output)
        print()
        if result.usage:
            usage = result.usage
            parts = []
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                v = usage.get(k)
                if v is not None:
                    parts.append(f"{k}={v}")
            if parts:
                print(f"  usage: {' '.join(parts)}")
                print()
    else:
        # Quiet mode: just the trimmed output, one logical line.
        sys.stdout.write(result.output.strip())
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
