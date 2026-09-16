"""Provider-agnostic LLM client.

All supported providers (OpenRouter, MiniMax, Kimi/Moonshot, or any custom
OpenAI-compatible endpoint) are driven through the OpenAI SDK pointed at the
provider's ``base_url``. The pipeline only depends on the small interface here
(``complete`` / ``chat``), which makes it trivial to mock in tests.

Production hardening (v0.2+):

- Configurable ``timeout`` on every API call (no more silent hangs).
- Automatic retry with exponential backoff for transient failures
  (HTTP 408/409/425/429/500/502/503/504, connection errors, read timeouts).
- Typed :class:`LLMError` subclasses so the UI / tests can distinguish
  retryable from non-retryable failures (``RetryableLLMError`` vs the rest).
- A single shared :class:`requests.Session` for ``list_models`` so connection
  pooling is reused across calls.
- Lightweight structured logging through the standard ``logging`` module.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from .config import get_settings
from .models import GenerationResult

if TYPE_CHECKING:
    import requests

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised for configuration or API problems with a human-readable message."""


class RetryableLLMError(LLMError):
    """A failure that the client has exhausted its retries on.

    The underlying cause was transient (network error, rate limit, 5xx). Callers
    may decide to surface this as a warning ("try again later") rather than a
    hard error.
    """


# Backwards-compatible alias (the project began as OpenRouter-only).
OpenRouterError = LLMError


# HTTP status codes worth retrying. Anything not in this set (notably 400, 401,
# 403, 404) is treated as a permanent failure and surfaced immediately.
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}

# Default retry policy. Override per-client via ``max_retries`` / ``backoff_*``.
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.6  # seconds
DEFAULT_BACKOFF_MAX = 8.0  # seconds
DEFAULT_TIMEOUT = 60.0  # seconds


class LLMClient:
    """Minimal wrapper over the OpenAI SDK configured for any compatible provider."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        default_model: str,
        fallback_models: tuple[str, ...] = (),
        supports_model_listing: bool = True,
        app_title: str = "LLM Skill Factory",
        app_url: str = "",
        send_app_headers: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_max: float = DEFAULT_BACKOFF_MAX,
    ) -> None:
        if not api_key:
            raise LLMError("No API key configured for this provider.")
        if not base_url:
            raise LLMError("No base URL configured for this provider.")
        if timeout <= 0:
            raise LLMError("timeout must be a positive number of seconds.")
        if max_retries < 0:
            raise LLMError("max_retries must be >= 0.")

        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.fallback_models = tuple(fallback_models)
        self.supports_model_listing = supports_model_listing
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.backoff_base = float(backoff_base)
        self.backoff_max = float(backoff_max)
        self._extra_headers: dict[str, str] = {}
        if send_app_headers:
            self._extra_headers["X-Title"] = app_title
            if app_url:
                self._extra_headers["HTTP-Referer"] = app_url
        self._client = None  # lazily created
        self._session: requests.Session | None = None  # lazily created

    # -- internal -----------------------------------------------------------
    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover
                raise LLMError(
                    "The 'openai' package is required. Run: pip install -r requirements.txt"
                ) from exc
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=0,  # we own retries; double-retry would be confusing
            )
        return self._client

    def _ensure_session(self) -> requests.Session:
        """A shared requests.Session for ``list_models`` with retry+backoff."""
        if self._session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            retry = Retry(
                total=self.max_retries,
                connect=self.max_retries,
                read=self.max_retries,
                status=self.max_retries,
                status_forcelist=sorted(_RETRYABLE_STATUS),
                allowed_methods=frozenset(["GET"]),
                backoff_factor=self.backoff_base,
                backoff_max=self.backoff_max,
                raise_on_status=False,
                respect_retry_after_header=True,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self._session = session
        return self._session

    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        """Decide whether an exception from the OpenAI SDK is worth retrying.

        The SDK raises a hierarchy of types; the most useful ones are
        ``APITimeoutError``, ``APIConnectionError``, ``RateLimitError``, and the
        generic ``APIStatusError`` (which carries ``status_code``).
        """

        # Lazy import so the rest of the module works without openai.
        try:
            from openai import APIConnectionError, APITimeoutError, RateLimitError
        except ImportError:
            return False

        if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
            return True
        try:
            from openai import APIStatusError
        except ImportError:
            return False
        if isinstance(exc, APIStatusError):
            return getattr(exc, "status_code", None) in _RETRYABLE_STATUS
        return False

    def _sleep(self, attempt: int) -> None:
        """Exponential backoff with full jitter, capped at ``backoff_max``."""
        delay = min(self.backoff_max, self.backoff_base * (2**attempt))
        delay = random.uniform(0, delay)
        if delay > 0:
            logger.debug("LLMClient retry %s in %.2fs", attempt + 1, delay)
            time.sleep(delay)

    def _with_retries(self, op_name: str, fn):
        """Run ``fn`` with bounded exponential-backoff retries."""
        attempts = self.max_retries + 1  # initial try + N retries
        last_exc: BaseException | None = None
        for attempt in range(attempts):
            try:
                return fn()
            except LLMError:
                # Already classified as a permanent LLM error — don't retry.
                raise
            except Exception as exc:  # surface a clean message to the UI
                last_exc = exc
                if attempt >= attempts - 1 or not self._is_retryable(exc):
                    break
                logger.warning(
                    "LLM %s failed (attempt %s/%s): %s",
                    op_name,
                    attempt + 1,
                    attempts,
                    exc,
                )
                self._sleep(attempt)
        # Exhausted retries on a retryable failure.
        raise RetryableLLMError(
            f"{op_name} failed after {attempts} attempt(s): {last_exc}"
        ) from last_exc

    # -- public API ---------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> GenerationResult | Iterator[str]:
        """Run a chat completion.

        Returns a :class:`GenerationResult` normally, or an iterator of text
        chunks when ``stream=True``.
        """

        client = self._ensure_client()
        model = model or self.default_model
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if self._extra_headers:
            kwargs["extra_headers"] = self._extra_headers
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        if stream:
            return self._stream(client, kwargs, model)

        try:
            resp = self._with_retries(
                "chat.completions.create",
                lambda: client.chat.completions.create(**kwargs),
            )
        except LLMError:
            raise
        except Exception as exc:  # pragma: no cover - defensive net
            raise LLMError(f"Request failed: {exc}") from exc

        content = resp.choices[0].message.content or ""
        usage: dict[str, Any] = {}
        if getattr(resp, "usage", None) is not None:
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                "total_tokens": getattr(resp.usage, "total_tokens", None),
            }
        return GenerationResult(content=content, model=model, usage=usage)

    def _stream(self, client, kwargs: dict, model: str) -> Iterator[str]:
        # Streamed responses are not retried mid-stream — the connection has
        # already started. We still wrap each chunk pull to surface a clean error.
        kwargs = {**kwargs, "stream": True}
        try:
            stream = client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover - network dependent
            raise LLMError(f"Stream failed: {exc}") from exc
        try:
            for chunk in stream:
                if not chunk.choices:
                    continue
                piece = getattr(chunk.choices[0].delta, "content", None)
                if piece:
                    yield piece
        except Exception as exc:  # pragma: no cover - network dependent
            raise LLMError(f"Stream failed: {exc}") from exc

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """Convenience for a single system+user turn used by the pipeline."""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        result = self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        assert isinstance(result, GenerationResult)
        return result

    def list_models(self) -> list[str]:
        """Fetch available model ids from the provider; fall back to the curated list."""

        if not self.supports_model_listing:
            return list(self.fallback_models)
        try:
            session = self._ensure_session()
            resp = session.get(
                f"{self.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            ids = sorted(m["id"] for m in data if isinstance(m, dict) and "id" in m)
            return ids or list(self.fallback_models)
        except Exception as exc:
            logger.warning("list_models failed (%s); using curated fallback list", exc)
            return list(self.fallback_models)


def client_from_settings(overrides: dict | None = None) -> LLMClient:
    """Build a client from resolved :class:`~skill_factory.config.Settings`."""

    s = get_settings(overrides)

    # Pick up retry/timeout tunables from env without bloating the Settings
    # dataclass. These are operational knobs, not user-facing configuration.
    import os

    try:
        timeout = float(os.environ.get("LLM_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    try:
        max_retries = int(os.environ.get("LLM_MAX_RETRIES", DEFAULT_MAX_RETRIES))
    except ValueError:
        max_retries = DEFAULT_MAX_RETRIES

    return LLMClient(
        api_key=s.api_key,
        base_url=s.base_url,
        default_model=s.default_model,
        fallback_models=s.fallback_models,
        supports_model_listing=s.supports_model_listing,
        app_title=s.app_title,
        app_url=s.app_url,
        send_app_headers=s.sends_app_headers,
        timeout=timeout,
        max_retries=max_retries,
    )
