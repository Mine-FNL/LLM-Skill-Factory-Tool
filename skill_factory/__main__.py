"""Console entrypoint for the ``skill-factory`` command.

Without arguments: print the package version.
With ``healthcheck``: delegate to :mod:`skill_factory.healthcheck`.
"""

from __future__ import annotations

import sys

from . import __version__


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "healthcheck":
        # Defer so importing this module doesn't drag in the LLM client.
        from . import healthcheck as _hc

        return _hc.main(sys.argv[2:])
    print(f"LLM Skill Factory v{__version__}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
