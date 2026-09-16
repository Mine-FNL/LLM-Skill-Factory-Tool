"""LLM Skill Factory — Streamlit entrypoint.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from ui import (
    PAGE_BATCH,
    PAGE_CONFIG,
    PAGE_EDITOR,
    PAGE_LIBRARY,
    PAGE_NEW,
    PAGE_PLAYGROUND,
    PAGES,
    batch_page,
    config_page,
    editor_page,
    ensure_state,
    library_page,
    new_skill_page,
    playground_page,
    settings,
)

st.set_page_config(page_title="LLM Skill Factory", page_icon="🏭", layout="wide")

ensure_state()

ROUTES = {
    PAGE_CONFIG: config_page.render,
    PAGE_NEW: new_skill_page.render,
    PAGE_LIBRARY: library_page.render,
    PAGE_EDITOR: editor_page.render,
    PAGE_PLAYGROUND: playground_page.render,
    PAGE_BATCH: batch_page.render,
}

with st.sidebar:
    st.title("🏭 Skill Factory")
    st.caption("Author great SKILL.md files for any domain.")

    nav = st.session_state.get("nav", PAGE_CONFIG)
    if nav not in PAGES:
        nav = PAGE_CONFIG
    choice = st.radio("Navigate", PAGES, index=PAGES.index(nav), label_visibility="collapsed")
    st.session_state["nav"] = choice

    st.divider()
    s = settings()
    st.caption(("🟢 " if s.has_key else "🔴 ") + f"**{s.provider_label}**")
    st.caption(f"Model: `{s.default_model}`")

# Render the selected page.
ROUTES[choice]()
