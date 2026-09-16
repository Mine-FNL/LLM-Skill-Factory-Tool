"""Editor: edit a skill, preview it, validate it, refine sections via the LLM, save versions."""

from __future__ import annotations

import datetime as _dt

import streamlit as st

from skill_factory import pipeline
from skill_factory.exporter import zip_skill
from skill_factory.frontmatter import split_frontmatter
from skill_factory.llm_client import LLMError
from skill_factory.models import SkillMeta
from skill_factory.validator import validate_skill_md

from . import (
    get_client,
    model_selectbox,
    render_validation,
    require_key,
    store,
    token_badge,
)


def render() -> None:
    st.header("📝 Editor")

    # Apply any content produced by a refine action on the previous run, before
    # the text_area widget for "editor_content" is instantiated.
    pending = st.session_state.pop("_pending_editor_content", None)
    if pending is not None:
        st.session_state["editor_content"] = pending

    s = store()
    skills = s.list_skills()
    if not skills:
        st.info("No skills to edit yet. Create one in **New Skill**.")
        return

    # --- selection (index-based so we can freely sync session state) --------
    cur_slug = st.session_state.get("editor_slug")
    if cur_slug not in skills:
        cur_slug = skills[0]
    c1, c2, c3 = st.columns([2, 1, 1])
    slug = c1.selectbox("Skill", skills, index=skills.index(cur_slug))
    versions = s.versions(slug)
    cur_v = st.session_state.get("editor_version")
    if cur_v not in versions:
        cur_v = versions[-1]
    version = c2.selectbox(
        "Version", versions, index=versions.index(cur_v), format_func=lambda v: f"v{v}"
    )
    st.session_state["editor_slug"] = slug
    st.session_state["editor_version"] = version

    # Load content into the editor only when the selection changes (preserve edits).
    load_key = f"{slug}:{version}"
    if st.session_state.get("editor_loaded_key") != load_key:
        st.session_state["editor_content"] = s.load_content(slug, version)
        st.session_state["editor_loaded_key"] = load_key

    c3.download_button(
        "⬇️ Zip",
        data=zip_skill(s, slug),
        file_name=f"{slug}.zip",
        mime="application/zip",
        key="editor_zip",
    )

    # --- edit + preview -----------------------------------------------------
    edit_col, view_col = st.columns(2)
    with edit_col:
        st.text_area("SKILL.md", key="editor_content", height=500)
        st.caption(token_badge(st.session_state.get("editor_content", "")))
    with view_col:
        tab_prev, tab_val, tab_meta = st.tabs(["Preview", "Validation", "Metadata"])
        content = st.session_state.get("editor_content", "")
        with tab_prev:
            st.markdown(content)
        with tab_val:
            report = validate_skill_md(content, expected_name=slug)
            st.caption(report.summary())
            render_validation(report)
        with tab_meta:
            _metadata_panel(s, slug, version)

    _refine_panel(slug)
    st.divider()
    _save_panel(s, slug, version)


# ---------------------------------------------------------------------------
def _refine_panel(slug: str) -> None:
    st.subheader("🪄 Refine with the LLM")
    if not require_key():
        return
    instruction = st.text_input(
        "Instruction",
        placeholder="Make the red flags section more concrete and add a checklist",
    )
    rc1, rc2 = st.columns([1, 1])
    section = rc1.text_input("Target section (optional)", placeholder="Red Flags")
    with rc2:
        model = model_selectbox("Model", key="editor_refine_model")
    if st.button("🪄 Refine", type="primary", disabled=not instruction.strip()):
        try:
            with st.spinner("Refining…"):
                res = pipeline.refine_section(
                    get_client(),
                    st.session_state["editor_content"],
                    instruction,
                    section=section,
                    model=model,
                )
            # Defer applying the new content to the next run (see render()).
            st.session_state["_pending_editor_content"] = res.content
            st.rerun()
        except LLMError as exc:
            st.error(str(exc))


def _save_panel(s, slug: str, version: int) -> None:
    st.subheader("💾 Save")
    notes = st.text_input("Version notes", placeholder="What changed?")
    b1, b2 = st.columns(2)
    if b1.button("Save as NEW version", type="primary"):
        meta = _meta_for_save(
            s, slug, version, st.session_state["editor_content"], notes, new_version=True
        )
        new_v = s.save_new_version(slug, st.session_state["editor_content"], meta)
        st.session_state["editor_version"] = new_v
        st.session_state["editor_loaded_key"] = None  # reload from disk next run
        st.success(f"Saved as v{new_v}.")
        st.rerun()
    if b2.button(f"Overwrite v{version}"):
        meta = _meta_for_save(
            s, slug, version, st.session_state["editor_content"], notes, new_version=False
        )
        s.overwrite_version(slug, version, st.session_state["editor_content"], meta)
        st.success(f"Overwrote v{version}.")


def _meta_for_save(
    s, slug: str, version: int, content: str, notes: str, *, new_version: bool
) -> SkillMeta:
    """Carry forward existing metadata, updating description from the frontmatter."""

    fm, _ = split_frontmatter(content)
    base = s.load_meta(slug, version)
    meta = SkillMeta(
        name=slug,
        description=str(fm.get("description", base.description)),
        skill_type=base.skill_type,
        domain_focus=base.domain_focus,
        tags=base.tags,
        entities=base.entities,
        base_skill=base.base_skill,
        version=version,
        version_notes=notes or base.version_notes,
        model=base.model,
        # New versions start with a clean test history; overwrites keep it.
        test_results=[] if new_version else base.test_results,
    )
    return meta


def _metadata_panel(s, slug: str, version: int) -> None:
    meta = s.load_meta(slug, version)
    created = _dt.datetime.fromtimestamp(meta.created_at).strftime("%Y-%m-%d %H:%M")
    st.write(
        {
            "name": meta.name,
            "type": meta.skill_type,
            "domain": meta.domain_focus or "—",
            "tags": meta.tags or [],
            "entities": meta.entities or [],
            "base_skill": meta.base_skill or "—",
            "version": meta.version,
            "version_notes": meta.version_notes or "—",
            "model": meta.model or "—",
            "created": created,
            "test_runs": len(meta.test_results),
        }
    )
