"""Playground: run a skill as a system prompt against OpenRouter and record results."""

from __future__ import annotations

import streamlit as st

from skill_factory.frontmatter import split_frontmatter
from skill_factory.llm_client import LLMError
from skill_factory.models import TestResult

from . import get_client, model_selectbox, require_key, store


def render() -> None:
    st.header("🧪 Testing Playground")
    s = store()
    skills = s.list_skills()
    if not skills:
        st.info("No skills to test yet. Create one in **New Skill**.")
        return
    if not require_key():
        return

    cur_slug = st.session_state.get("pg_slug")
    if cur_slug not in skills:
        cur_slug = skills[0]
    c1, c2 = st.columns([2, 1])
    slug = c1.selectbox("Skill", skills, index=skills.index(cur_slug))
    versions = s.versions(slug)
    cur_v = st.session_state.get("pg_version")
    if cur_v not in versions:
        cur_v = versions[-1]
    version = c2.selectbox(
        "Version", versions, index=versions.index(cur_v), format_func=lambda v: f"v{v}"
    )
    st.session_state["pg_slug"] = slug
    st.session_state["pg_version"] = version

    content = s.load_content(slug, version)
    _, body = split_frontmatter(content)
    system_prompt = body or content

    with st.expander("System prompt (the skill body sent to the model)"):
        st.code(system_prompt, language="markdown")

    model = model_selectbox("Model", key="pg_model")
    user_prompt = st.text_area(
        "Test prompt (the user turn)",
        placeholder="e.g. Review this API design for idempotency issues: …",
        height=140,
    )

    run = st.button("▶️ Run", type="primary", disabled=not user_prompt.strip())
    st.divider()

    if run:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            with st.spinner("Running…"):
                stream = get_client().chat(messages, model=model, stream=True)
                output = st.write_stream(stream)
            st.session_state["pg_last"] = {
                "prompt": user_prompt,
                "output": output,
                "model": model,
            }
        except LLMError as exc:
            st.error(str(exc))
    elif st.session_state.get("pg_last"):
        st.markdown(st.session_state["pg_last"]["output"])

    _rating_panel(s, slug, version)


def _rating_panel(s, slug: str, version: int) -> None:
    last = st.session_state.get("pg_last")
    if not last:
        return
    st.divider()
    st.caption("Record this run against the skill version:")
    name = st.text_input("Test name", value="ad-hoc test")
    notes = st.text_input("Notes (optional)")
    b1, b2, b3 = st.columns(3)
    rating = None
    if b1.button("👍 Save as good"):
        rating = "up"
    if b2.button("👎 Save as poor"):
        rating = "down"
    if b3.button("💾 Save (no rating)"):
        rating = ""
    if rating is not None:
        meta = s.load_meta(slug, version)
        meta.test_results.append(
            TestResult(
                test_name=name,
                user_prompt=last["prompt"],
                output=last["output"],
                model=last["model"],
                rating=rating,
                notes=notes,
            )
        )
        s.update_meta(slug, version, meta)
        st.success(f"Recorded ({len(meta.test_results)} total for v{version}).")
