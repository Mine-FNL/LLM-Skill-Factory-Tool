"""Console entrypoint for the ``skill-factory`` command.

Subcommands:

- (none)         — print the package version.
- ``healthcheck`` — delegate to :mod:`skill_factory.healthcheck`.
- ``eval``        — run an eval set against a saved skill (see :mod:`skill_factory.eval`).
- ``run``         — load a saved skill and call it against a model (see :mod:`skill_factory.run`).
"""

from __future__ import annotations

import sys

from . import __version__


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "healthcheck":
        from . import healthcheck as _hc

        return _hc.main(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "eval":
        from .eval import cli as _eval_cli

        return _eval_cli.main(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "run":
        from .run import cli_main

        return cli_main(sys.argv[2:])
    print(f"LLM Skill Factory v{__version__}")
    print("Subcommands: healthcheck, eval, run")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
