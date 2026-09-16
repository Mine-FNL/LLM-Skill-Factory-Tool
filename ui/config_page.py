"""Config page: pick a provider (OpenRouter / MiniMax / Kimi / custom), key, model.

Per-provider values are mirrored into persistent session dicts (``provider_keys`` etc.)
so switching providers — which unmounts the widgets — never loses what you typed.
"""

from __future__ import annotations

import streamlit as st

from skill_factory.llm_client import LLMError, client_from_settings
from skill_factory.providers import PROVIDERS, get_provider, provider_ids
from skill_factory.references import PDF_AVAILABLE

from . import overrides, settings, store


def _persistent_input(store_key: str, pid: str, *, label: str, widget_key: str, **kwargs) -> str:
    """A text input whose value persists per-provider via ``st.session_state[store_key]``."""

    d = st.session_state.setdefault(store_key, {})
    if widget_key not in st.session_state:
        st.session_state[widget_key] = d.get(pid, "")
    val = st.text_input(label, key=widget_key, **kwargs)
    d[pid] = val
    return val


def render() -> None:
    st.header("⚙️ Configuration")

    # --- provider -----------------------------------------------------------
    ids = provider_ids()
    cur = st.session_state.get("provider", ids[0])
    if cur not in ids:
        cur = ids[0]
    chosen = st.radio(
        "Provider",
        ids,
        index=ids.index(cur),
        format_func=lambda i: PROVIDERS[i].label,
        horizontal=True,
    )
    st.session_state["provider"] = chosen
    prov = get_provider(chosen)

    note = prov.note or ""
    if prov.keys_url:
        note = (note + "  ·  " if note else "") + f"[Get an API key]({prov.keys_url})"
    if note:
        st.caption(note)
    st.markdown(
        "Keys are kept in this session only and never written to disk. For persistence, "
        "copy `.env.example` to `.env` and set the relevant key(s)."
    )

    # --- key + default model (persisted per provider) ----------------------
    s = settings()
    env_supplied = (not st.session_state.get("provider_keys", {}).get(chosen)) and s.has_key
    col1, col2 = st.columns(2)
    with col1:
        _persistent_input(
            "provider_keys",
            chosen,
            label=f"{prov.label} API key",
            widget_key=f"cfg_key_{chosen}",
            type="password",
            placeholder="(loaded from environment)" if env_supplied else "sk-...",
        )
    with col2:
        _persistent_input(
            "provider_models",
            chosen,
            label="Default model",
            widget_key=f"cfg_model_{chosen}",
            placeholder=prov.default_model or "model id",
            help="Type any model id this provider supports.",
        )

    s = settings()  # re-resolve after edits
    fcol, ncol = st.columns([1, 2])
    with fcol:
        if st.button("🔄 Fetch models", disabled=not s.has_key or not prov.supports_model_listing):
            try:
                with st.spinner("Querying provider…"):
                    models = client_from_settings(overrides()).list_models()
                cache = dict(st.session_state.get("available_models") or {})
                cache[chosen] = models
                st.session_state["available_models"] = cache
                st.success(f"Loaded {len(models)} models.")
            except LLMError as exc:
                st.error(str(exc))
    with ncol:
        if not prov.supports_model_listing:
            st.caption(
                "No live model listing for this provider — a curated list is used. "
                "Type any model id in the field above."
            )

    with st.expander("Advanced settings"):
        _persistent_input(
            "provider_base_urls",
            chosen,
            label="Base URL",
            widget_key=f"cfg_base_{chosen}",
            placeholder=prov.base_url or "https://…/v1",
            help="Editable for regional endpoints (e.g. Moonshot .cn, MiniMax .chat) or any "
            "OpenAI-compatible gateway.",
        )
        st.text_input("App title (sent to OpenRouter)", key="app_title", placeholder=s.app_title)
        st.text_input("App URL (sent to OpenRouter)", key="app_url", placeholder=s.app_url)
        st.text_input("Skills directory", key="skills_dir", placeholder=str(s.skills_dir))

    # --- status -------------------------------------------------------------
    st.divider()
    st.subheader("Status")
    s = settings()
    cache = st.session_state.get("available_models") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Provider", s.provider_label)
    c2.metric("API key", "set ✅" if s.has_key else "missing ❌")
    c3.metric("Skills", len(store().list_skills()))
    c4.metric("PDF extraction", "on" if PDF_AVAILABLE else "off")
    st.caption(
        f"Model: `{s.default_model}` · Base URL: `{s.base_url or '—'}` · "
        f"{len(cache.get(s.provider_id, []))} models cached · Skills dir: `{s.skills_dir}`"
    )
