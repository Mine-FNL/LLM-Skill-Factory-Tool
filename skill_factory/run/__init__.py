"""``skill-factory run`` — close the dev loop.

Load a saved skill and invoke it as a system prompt against any model
supported by the configured provider. This is what every other authoring
tool has shipped but no eval harness: the moment between "I authored a
skill" and "I see it work on a real prompt".

Public API:

- :func:`run_skill` — programmatic invocation. Returns the model output
  plus usage info.
- :func:`cli_main` — the ``python -m skill_factory run ...`` entrypoint.

Run::

    python -m skill_factory run \\
        --skill qnb-specialist \\
        --prompt "Review QNB's Q3 2026 capital ratios." \\
        --model anthropic/claude-sonnet-4.6
"""

from __future__ import annotations

from .cli import main as cli_main
from .runner import RunResult, run_skill

__all__ = ["RunResult", "cli_main", "run_skill"]
