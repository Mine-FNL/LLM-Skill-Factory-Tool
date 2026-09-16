"""Tests for skill_factory.logging_setup."""

from __future__ import annotations

import json
import logging

import pytest

from skill_factory.logging_setup import configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset_logging():
    """Each test starts from a clean logging configuration."""

    yield
    # Force the next test to rebuild the handler — re-imports the env vars.
    import skill_factory.logging_setup as ls

    ls._CONFIGURED = False


def test_get_logger_under_skill_factory_namespace():
    log = get_logger("foo")
    assert log.name == "skill_factory.foo"


def test_configure_logging_is_idempotent_without_force():
    """Two calls without force must return the same object with one handler."""

    root = configure_logging()
    again = configure_logging()
    assert root is again
    assert len(root.handlers) == 1


def test_configure_logging_force_rebuilds():
    configure_logging()
    again = configure_logging(force=True)
    assert len(again.handlers) == 1


def test_configure_logging_respects_level_env(monkeypatch):
    monkeypatch.setenv("SKILL_FACTORY_LOG_LEVEL", "DEBUG")
    root = configure_logging()
    assert root.level == logging.DEBUG


def test_configure_logging_json_format(monkeypatch):
    monkeypatch.setenv("SKILL_FACTORY_LOG_FORMAT", "json")
    configure_logging(force=True)
    root = logging.getLogger("skill_factory")
    handler = root.handlers[0]
    record = logging.LogRecord(
        name="skill_factory.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    out = handler.format(record)
    parsed = json.loads(out)
    assert parsed["level"] == "INFO"
    assert parsed["msg"] == "hello"


def test_configure_logging_silences_noisy_third_parties(monkeypatch):
    monkeypatch.setenv("SKILL_FACTORY_LOG_LEVEL", "DEBUG")
    configure_logging(force=True)
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("urllib3.connectionpool").level >= logging.WARNING


def test_configure_logging_does_not_propagate():
    root = configure_logging()
    assert root.propagate is False
