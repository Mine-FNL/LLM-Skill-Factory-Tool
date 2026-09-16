"""Configuration & settings resolution.

Resolution order for any value is: explicit override (e.g. the UI session) >
environment variable > provider default > built-in default. The core never
hardcodes an API key and never persists one to disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .providers import DEFAULT_PROVIDER, get_provider

try:  # python-dotenv is a hard dependency, but keep import resilient for tests
    from dotenv import load_dotenv
except Exception:  # pragma: no cover

    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False


# Project root = parent of this package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

_ENV_LOADED = False


def load_env() -> None:
    """Load ``.env`` from the project root exactly once (idempotent)."""

    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv(PROJECT_ROOT / ".env")
        _ENV_LOADED = True


@dataclass
class Settings:
    provider_id: str = DEFAULT_PROVIDER
    provider_label: str = "OpenRouter"
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    fallback_models: tuple[str, ...] = field(default_factory=tuple)
    supports_model_listing: bool = True
    sends_app_headers: bool = False
    app_title: str = "LLM Skill Factory"
    app_url: str = "https://github.com/0xBingBong69/LLM-Skill-Factory-Tool"
    skills_dir: Path = PROJECT_ROOT / "skills"

    @property
    def has_key(self) -> bool:
        return bool(self.api_key.strip())


def get_settings(overrides: dict | None = None) -> Settings:
    """Build a :class:`Settings` from overrides > env > provider defaults.

    ``overrides`` is typically the Streamlit session state, so a key/model typed
    into the UI wins over the environment without ever being written to disk.
    """

    load_env()
    overrides = overrides or {}

    def first(*candidates: str) -> str:
        """Return the first non-empty candidate (treats '' as unset)."""

        for c in candidates:
            if c:
                return c
        return ""

    provider_id = first(
        overrides.get("provider", ""),
        os.environ.get("LLM_PROVIDER", ""),
        DEFAULT_PROVIDER,
    )
    prov = get_provider(provider_id)

    api_key = first(overrides.get("api_key", ""), os.environ.get(prov.api_key_env, ""))
    base_url = first(overrides.get("base_url", ""), prov.base_url)
    default_model = first(
        overrides.get("default_model", ""),
        os.environ.get(f"{prov.id.upper()}_DEFAULT_MODEL", ""),
        prov.default_model,
    )

    skills_dir_raw = first(overrides.get("skills_dir", ""), os.environ.get("SKILLS_DIR", ""))
    skills_dir = Path(skills_dir_raw) if skills_dir_raw else PROJECT_ROOT / "skills"

    return Settings(
        provider_id=prov.id,
        provider_label=prov.label,
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        fallback_models=prov.models,
        supports_model_listing=prov.supports_model_listing,
        sends_app_headers=prov.sends_app_headers,
        app_title=first(
            overrides.get("app_title", ""),
            os.environ.get("APP_TITLE", ""),
            os.environ.get("OPENROUTER_APP_TITLE", ""),
            "LLM Skill Factory",
        ),
        app_url=first(
            overrides.get("app_url", ""),
            os.environ.get("APP_URL", ""),
            os.environ.get("OPENROUTER_APP_URL", ""),
            "https://github.com/0xBingBong69/LLM-Skill-Factory-Tool",
        ),
        skills_dir=skills_dir,
    )
