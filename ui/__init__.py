"""Streamlit UI helpers shared across pages.

Keeps page modules thin and centralises session-state, settings and client wiring.
"""

from __future__ import annotations

import copy

import streamlit as st

from skill_factory.config import get_settings
from skill_factory.llm_client import client_from_settings
from skill_factory.providers import DEFAULT_PROVIDER
from skill_factory.skill_store import SkillStore
from skill_factory.validator import estimate_tokens

# Sidebar navigation labels (also used for programmatic navigation).
PAGE_CONFIG = "Config"
PAGE_NEW = "New Skill"
PAGE_LIBRARY = "Library"
PAGE_EDITOR = "Editor"
PAGE_PLAYGROUND = "Playground"
PAGE_BATCH = "Batch"
PAGES = [PAGE_CONFIG, PAGE_NEW, PAGE_LIBRARY, PAGE_EDITOR, PAGE_PLAYGROUND, PAGE_BATCH]

_STATE_DEFAULTS = {
    "nav": PAGE_CONFIG,
    # config overrides (never written to disk). Per-provider values persist in plain
    # session dicts so switching providers (which unmounts the widgets) never loses them.
    "provider": DEFAULT_PROVIDER,
    "provider_keys": {},  # provider_id -> api key
    "provider_models": {},  # provider_id -> default model
    "provider_base_urls": {},  # provider_id -> base url override
    "app_title": "",
    "app_url": "",
    "skills_dir": "",
    "available_models": {},  # provider_id -> [model ids]
    # new-skill wizard
    "wiz_stage": "spec",
    "wiz_spec": None,
    "wiz_outline": "",
    "wiz_draft": "",
    # editor
    "editor_slug": None,
    "editor_version": None,
    "editor_content": "",
    "editor_loaded_key": None,
    # playground
    "pg_slug": None,
    "pg_version": None,
}


def ensure_state() -> None:
    for k, v in _STATE_DEFAULTS.items():
        if k not in st.session_state:
            # Fresh copy for mutable defaults so sessions don't share one object.
            st.session_state[k] = copy.deepcopy(v) if isinstance(v, (dict, list)) else v


def overrides() -> dict:
    pid = st.session_state.get("provider", DEFAULT_PROVIDER)
    return {
        "provider": pid,
        "api_key": st.session_state.get("provider_keys", {}).get(pid, ""),
        "base_url": st.session_state.get("provider_base_urls", {}).get(pid, ""),
        "default_model": st.session_state.get("provider_models", {}).get(pid, ""),
        "app_title": st.session_state.get("app_title", ""),
        "app_url": st.session_state.get("app_url", ""),
        "skills_dir": st.session_state.get("skills_dir", ""),
    }


def settings():
    return get_settings(overrides())


def store() -> SkillStore:
    return SkillStore(settings().skills_dir)


def get_client():
    """Build the LLM client for the selected provider (may raise if not configured)."""

    return client_from_settings(overrides())


def has_key() -> bool:
    return settings().has_key


def require_key() -> bool:
    if not has_key():
        st.warning(
            "Set an API key for your selected provider on the **Config** page first.", icon="🔑"
        )
        return False
    return True


def goto(page: str, **state) -> None:
    """Switch pages programmatically and rerun, optionally seeding session state."""

    for k, v in state.items():
        st.session_state[k] = v
    st.session_state["nav"] = page
    st.rerun()


def model_selectbox(label: str = "Model", key: str | None = None):
    s = settings()
    cache = st.session_state.get("available_models") or {}
    models = list(cache.get(s.provider_id, [])) or list(s.fallback_models)
    default = s.default_model
    if default and default not in models:
        models = [default, *models]
    help_text = "Pick a model, or set the default on the Config page."
    if models:
        # Seed/repair the keyed state (avoids passing index alongside key).
        if key:
            if st.session_state.get(key) not in models:
                st.session_state[key] = default if default in models else models[0]
            return st.selectbox(label, models, key=key)
        index = models.index(default) if default in models else 0
        return st.selectbox(label, models, index=index)
    # No cached model list — free-text entry.
    if key:
        st.session_state.setdefault(key, default)
        return st.text_input(label, key=key, help=help_text)
    return st.text_input(label, value=default, help=help_text)


def render_validation(report) -> None:
    """Render a ValidationReport with appropriate severity styling."""

    if report.ok and not report.warnings and not report.suggestions:
        st.success("Looks great — no issues found. ✅")
        return
    if report.errors:
        for e in report.errors:
            st.error(e, icon="⛔")
    for w in report.warnings:
        st.warning(w, icon="⚠️")
    for s in report.suggestions:
        st.info(s, icon="💡")


def token_badge(text: str) -> str:
    return f"~{estimate_tokens(text):,} tokens · {len(text.splitlines())} lines"
