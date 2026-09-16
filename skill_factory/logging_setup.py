"""Logging configuration for the Skill Factory.

Centralises setup so the app, the CLI entrypoint, the healthcheck, and any
external embedder all log to the same place with the same format.

Defaults are deliberately Streamlit-friendly: only WARNING+ shows up on the
console because Streamlit captures stdout/stderr and would otherwise spam the
UI. Set ``SKILL_FACTORY_LOG_LEVEL=DEBUG`` to see everything, or
``SKILL_FACTORY_LOG_FORMAT=json`` for a single-line JSON log suitable for
container log aggregators.

Usage::

    from skill_factory.logging_setup import configure_logging
    configure_logging()           # idempotent; safe to call from app entrypoints
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Final

_CONFIGURED = False

_LEVELS: Final[dict[str, int]] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Namespaces that get noisy in dev — silenced unless explicitly debug-enabled.
_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "httpx",
    "httpcore",
    "urllib3.connectionpool",
    "openai._base_client",
)


class _JsonFormatter(logging.Formatter):
    """Single-line JSON log records — useful in containerised deployments."""

    def __init__(self) -> None:
        super().__init__()
        self._RESERVED = frozenset(
            {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
            }
        )

    def format(self, record: logging.LogRecord) -> str:
        import json

        out: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        # Carry structured extras (anything passed via `logger.info(..., extra={...})`).
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            out[key] = value
        return json.dumps(out, ensure_ascii=False, default=str)


def configure_logging(
    level: str | int | None = None,
    *,
    fmt: str | None = None,
    stream=None,
    force: bool = False,
) -> logging.Logger:
    """Configure the root logger for the Skill Factory.

    Idempotent: subsequent calls without ``force=True`` are no-ops so importing
    modules never double-configure handlers. Tests can pass ``force=True`` to
    re-read env vars and rebuild handlers between assertions.
    """

    global _CONFIGURED
    if _CONFIGURED and not force:
        return logging.getLogger("skill_factory")

    chosen_level = (
        _LEVELS.get(str(level).upper(), logging.WARNING)
        if level is None or isinstance(level, str)
        else int(level)
    )
    env_level = os.environ.get("SKILL_FACTORY_LOG_LEVEL")
    if env_level:
        chosen_level = _LEVELS.get(env_level.upper(), chosen_level)

    chosen_format = fmt or os.environ.get("SKILL_FACTORY_LOG_FORMAT") or "plain"
    out_stream = stream or sys.stderr

    handler = logging.StreamHandler(out_stream)
    if chosen_format == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root = logging.getLogger("skill_factory")
    # Replace any previously configured handlers (Streamlit installs its own
    # root handler that we don't want for our namespace).
    root.handlers = [handler]
    root.setLevel(chosen_level)
    root.propagate = False

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(chosen_level, logging.WARNING))

    _CONFIGURED = True
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``skill_factory`` namespace, configuring if needed."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name if name.startswith("skill_factory") else f"skill_factory.{name}")
