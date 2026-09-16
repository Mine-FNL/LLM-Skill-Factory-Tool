"""Tests for LLMClient retry / backoff / error classification.

We mock the OpenAI SDK so the tests stay fast and deterministic — no network,
no real keys.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from skill_factory.llm_client import (
    DEFAULT_MAX_RETRIES,
    LLMClient,
    LLMError,
    OpenRouterError,
    RetryableLLMError,
)


def _client(**kwargs: Any) -> LLMClient:
    base = {
        "api_key": "k",
        "base_url": "https://example.invalid/v1",
        "default_model": "m",
        "timeout": 1.0,
        "max_retries": 2,
        "backoff_base": 0.01,  # keep tests fast
        "backoff_max": 0.05,
    }
    base.update(kwargs)
    return LLMClient(**base)


def test_requires_positive_timeout():
    with pytest.raises(LLMError):
        LLMClient("k", base_url="https://x/v1", default_model="m", timeout=0)


def test_requires_non_negative_retries():
    with pytest.raises(LLMError):
        LLMClient("k", base_url="https://x/v1", default_model="m", max_retries=-1)


def test_is_retryable_classifies_openai_errors():
    """The classifier should treat SDK errors with retryable status codes as retryable."""

    client = _client()

    # Fake the openai imports lazily.
    fake_api_timeout = type("APITimeoutError", (Exception,), {})
    fake_api_conn = type("APIConnectionError", (Exception,), {})
    fake_rate = type("RateLimitError", (Exception,), {})
    fake_api_status = type("APIStatusError", (Exception,), {})

    class _StatusErr(fake_api_status):
        def __init__(self, status_code: int):
            super().__init__("boom")
            self.status_code = status_code

    with patch.dict(
        "sys.modules",
        {
            "openai": MagicMock(
                APITimeoutError=fake_api_timeout,
                APIConnectionError=fake_api_conn,
                RateLimitError=fake_rate,
                APIStatusError=fake_api_status,
            )
        },
    ):
        assert client._is_retryable(fake_api_timeout("t"))
        assert client._is_retryable(fake_api_conn("c"))
        assert client._is_retryable(fake_rate("r"))
        assert client._is_retryable(_StatusErr(429))
        assert client._is_retryable(_StatusErr(503))
        # 400/401/403/404 are NOT retryable.
        assert not client._is_retryable(_StatusErr(400))
        assert not client._is_retryable(_StatusErr(401))
        assert not client._is_retryable(_StatusErr(404))
        # Random exceptions aren't retryable.
        assert not client._is_retryable(ValueError("nope"))


def test_with_retries_recovers_after_transient_failure(monkeypatch):
    """A transient failure followed by success should yield the success result."""

    client = _client(max_retries=3)

    fake_rate = type("RateLimitError", (Exception,), {})
    call_log: list[int] = []

    def fake_fn():
        call_log.append(1)
        if len(call_log) < 3:
            raise fake_rate("rate limited")
        return "ok"

    # Force the classifier to treat RateLimitError as retryable.
    monkeypatch.setattr(client, "_is_retryable", lambda exc: isinstance(exc, fake_rate))
    # Skip actual sleeping.
    monkeypatch.setattr(client, "_sleep", lambda *a, **kw: None)

    assert client._with_retries("test", fake_fn) == "ok"
    assert len(call_log) == 3


def test_with_retries_gives_up_after_max(monkeypatch):
    client = _client(max_retries=2)

    fake_rate = type("RateLimitError", (Exception,), {})

    def fake_fn():
        raise fake_rate("still rate limited")

    monkeypatch.setattr(client, "_is_retryable", lambda exc: isinstance(exc, fake_rate))
    monkeypatch.setattr(client, "_sleep", lambda *a, **kw: None)

    with pytest.raises(RetryableLLMError):
        client._with_retries("test", fake_fn)


def test_with_retries_does_not_retry_permanent_errors(monkeypatch):
    """A non-retryable exception should result in a single attempt before surfacing."""

    client = _client(max_retries=5)

    call_log: list[int] = []

    def fake_fn():
        call_log.append(1)
        raise ValueError("nope")  # not retryable

    # Classifier returns False for this ValueError.
    monkeypatch.setattr(client, "_is_retryable", lambda exc: False)
    monkeypatch.setattr(client, "_sleep", lambda *a, **kw: None)

    # The base Exception is wrapped into an LLMError (either as Retryable or
    # plain, depending on retry exhaustion) — but never into ValueError.
    with pytest.raises(Exception) as excinfo:
        client._with_retries("test", fake_fn)
    assert not isinstance(excinfo.value, ValueError)
    assert len(call_log) == 1  # only the first attempt


def test_with_retries_propagates_llm_error_immediately():
    """A pre-classified LLMError should bypass retries entirely."""

    client = _client(max_retries=3)
    call_log: list[int] = []

    def fake_fn():
        call_log.append(1)
        raise LLMError("config problem")

    with pytest.raises(LLMError):
        client._with_retries("test", fake_fn)
    assert len(call_log) == 1


def test_chat_uses_retries(monkeypatch):
    """End-to-end: client.chat retries on a transient SDK error then succeeds."""

    client = _client(max_retries=2)
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="hi"))]
    fake_response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

    fake_rate = type("RateLimitError", (Exception,), {})
    call_log: list[int] = []

    def fake_create(**_kwargs):
        call_log.append(1)
        if len(call_log) < 2:
            raise fake_rate("rate limited")
        return fake_response

    fake_client.chat.completions.create = fake_create
    monkeypatch.setattr(client, "_ensure_client", lambda: fake_client)
    monkeypatch.setattr(client, "_is_retryable", lambda exc: isinstance(exc, fake_rate))
    monkeypatch.setattr(client, "_sleep", lambda *a, **kw: None)

    result = client.chat([{"role": "user", "content": "hi"}])
    assert result.content == "hi"
    assert result.model == "m"
    assert len(call_log) == 2


def test_chat_surfaces_4xx_without_retry(monkeypatch):
    """A 400 must NOT trigger retry attempts."""

    client = _client(max_retries=5)
    fake_client = MagicMock()

    fake_status_err = type("APIStatusError", (Exception,), {})

    def fake_create(**_kwargs):
        err = fake_status_err("bad request")
        err.status_code = 400
        raise err

    fake_client.chat.completions.create = fake_create
    monkeypatch.setattr(client, "_ensure_client", lambda: fake_client)
    monkeypatch.setattr(
        client, "_is_retryable", lambda exc: getattr(exc, "status_code", None) in {429, 500}
    )
    monkeypatch.setattr(client, "_sleep", lambda *a, **kw: None)

    with pytest.raises(LLMError):
        client.chat([{"role": "user", "content": "hi"}])


def test_retryable_error_is_llm_error():
    """RetryableLLMError must subclass LLMError so existing except clauses still catch it."""
    assert issubclass(RetryableLLMError, LLMError)
    assert issubclass(RetryableLLMError, RuntimeError)


def test_openrouter_alias_still_works():
    assert OpenRouterError is LLMError


def test_default_max_retries_is_sane():
    """The default policy should permit at least one retry."""
    assert DEFAULT_MAX_RETRIES >= 1
