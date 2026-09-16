"""Standalone healthcheck for orchestrators (Docker HEALTHCHECK, k8s probes).

Runs a fast, network-free smoke test that:

1. Verifies the package is importable and reports the running version.
2. Resolves :func:`skill_factory.config.get_settings` cleanly (no key required
   for this step).
3. Confirms the configured skills directory exists or can be created.
4. Pings the configured LLM provider's ``GET /models`` endpoint with a short
   timeout, IF a key is available. The endpoint probe is best-effort: a network
   failure is reported but does NOT fail the overall healthcheck (the app still
   works without a live model listing — it falls back to curated lists).

Exit codes:

- ``0`` — app is ready to serve traffic (or runs in a no-key degraded mode).
- ``1`` — something is fundamentally wrong (config invalid, FS inaccessible).

Run::

    python -m skill_factory.healthcheck
    python -m skill_factory.healthcheck --strict   # also fail if no API key
    python -m skill_factory.healthcheck --json     # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from . import __version__
from .config import get_settings
from .logging_setup import configure_logging


@dataclass
class HealthReport:
    ok: bool = True
    version: str = __version__
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        name: str,
        ok: bool,
        detail: str = "",
        *,
        info: bool = False,
        **extras: Any,
    ) -> None:
        """Record a check.

        ``info=True`` records the check but does NOT flip ``self.ok`` to False
        when ``ok=False``. Use this for informational warnings (e.g. "API key
        is missing") that should not make the deployment look unhealthy.
        """

        entry: dict[str, Any] = {"name": name, "ok": ok, "detail": detail, **extras}
        self.checks.append(entry)
        if not ok and not info:
            self.ok = False

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "version": self.version, "checks": self.checks}


def run_healthcheck(*, probe_provider: bool = True, strict_key: bool = False) -> HealthReport:
    report = HealthReport()

    # 1. Settings resolve cleanly.
    try:
        s = get_settings()
        report.add(
            "settings",
            True,
            f"provider={s.provider_id} model={s.default_model or '(none)'}",
        )
    except Exception as exc:
        report.add("settings", False, f"failed to resolve settings: {exc}")
        return report  # nothing else is meaningful

    # 2. Skills directory is usable.
    try:
        s.skills_dir.mkdir(parents=True, exist_ok=True)
        probe = s.skills_dir / ".healthcheck_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        report.add("skills_dir", True, f"writable at {s.skills_dir}")
    except Exception as exc:
        report.add("skills_dir", False, f"{s.skills_dir}: {exc}")

    # 3. Key presence — informational; only fatal in strict mode.
    report.add(
        "api_key",
        bool(s.has_key),
        "configured" if s.has_key else "missing — app will run in degraded mode",
        info=True,
    )
    if strict_key and not s.has_key:
        report.ok = False

    # 4. Optional: live provider probe. A network failure here is informational
    # — the app still works with a curated fallback list — so it doesn't flip
    # overall ok. Set ``strict_key`` to escalate key issues, but never probe errors.
    if probe_provider and s.has_key and s.base_url:
        try:
            from .llm_client import LLMClient

            client = LLMClient(
                api_key=s.api_key,
                base_url=s.base_url,
                default_model=s.default_model or "healthcheck",
                timeout=5.0,
                max_retries=0,
            )
            models = client.list_models()
            report.add(
                "provider_probe",
                True,
                f"reachable, {len(models)} model(s) listed",
            )
        except Exception as exc:
            report.add(
                "provider_probe",
                False,
                f"could not reach {s.base_url}: {exc}",
                info=True,
            )

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m skill_factory.healthcheck",
        description="Smoke test the Skill Factory deployment.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail (exit 1) when no API key is configured.",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="Skip the live /models provider probe.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON report on stdout instead of human-readable output.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output except the JSON report (implies --json).",
    )
    args = parser.parse_args(argv)

    configure_logging(level="WARNING")

    report = run_healthcheck(
        probe_provider=not args.no_probe,
        strict_key=args.strict,
    )

    json_mode = args.json or args.quiet
    if json_mode:
        json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        marker = "✅" if report.ok else "❌"
        print(f"{marker} Skill Factory v{report.version}")
        for c in report.checks:
            tick = "✓" if c["ok"] else "✗"
            print(f"  [{tick}] {c['name']}: {c['detail']}")

    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
