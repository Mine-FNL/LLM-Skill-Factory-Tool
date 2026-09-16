"""New Skill wizard: spec form -> outline -> draft, with human approval at each gate."""

from __future__ import annotations

import streamlit as st

from skill_factory import pipeline
from skill_factory.llm_client import LLMError
from skill_factory.models import SKILL_TYPE_HELP, SKILL_TYPES, TONES, SkillMeta, SkillSpec
from skill_factory.references import combine_references, extract_text_from_upload
from skill_factory.safety import InputLimitError, ReservedSlugError, validate_skill_name
from skill_factory.skill_store import slugify
from skill_factory.validator import validate_skill_md

from . import (
    PAGE_EDITOR,
    goto,
    model_selectbox,
    render_validation,
    require_key,
    store,
    token_badge,
)

_STAGES = ["spec", "outline", "draft"]
_STAGE_LABELS = {"spec": "1 · Specify", "outline": "2 · Outline", "draft": "3 · Draft"}


def _parse_list(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        for piece in line.split(","):
            piece = piece.strip()
            if piece:
                items.append(piece)
    return items


def render() -> None:
    st.header("✨ New Skill")
    stage = st.session_state.get("wiz_stage", "spec")
    st.caption(
        " → ".join(f"**{_STAGE_LABELS[s]}**" if s == stage else _STAGE_LABELS[s] for s in _STAGES)
    )
    st.divider()

    if stage == "spec":
        _spec_stage()
    elif stage == "outline":
        _outline_stage()
    else:
        _draft_stage()


# ---------------------------------------------------------------------------
def _spec_stage() -> None:
    existing = [None, *store().list_skills()]
    with st.form("spec_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(
                "Skill name",
                placeholder="backend-api-engineer",
                help="Will be slugified to kebab-case.",
            )
            skill_type = st.selectbox(
                "Type",
                SKILL_TYPES,
                help="\n".join(f"- **{k}**: {v}" for k, v in SKILL_TYPE_HELP.items()),
            )
            domain_focus = st.text_input("Domain / focus", placeholder="REST API design in Python")
        with c2:
            tone = st.selectbox("Tone", TONES, index=1)
            token_budget = st.slider("Target body size (tokens)", 400, 4000, 1500, 100)
            base_skill = st.selectbox(
                "Extend base skill (optional)", existing, format_func=lambda x: x or "— none —"
            )

        description = st.text_area(
            "Trigger description (frontmatter `description`)",
            placeholder="Use when the user asks to design, review, or implement a REST API…",
            help="State what the skill does AND when to use it. This drives activation.",
            height=80,
        )
        tags = st.text_input("Tags (comma-separated)", placeholder="backend, api, python")
        entities = st.text_area(
            "Specific subjects/entities (optional, one per line or comma-separated)",
            placeholder="(e.g. specific services, companies, frameworks to cover)",
            height=68,
        )
        requirements = st.text_area(
            "Key requirements / must-haves (one per line)",
            placeholder="Cover idempotency\nInclude an output template\nList common pitfalls",
            height=100,
        )

        st.markdown("**Reference material (optional)** — grounds the generation in facts.")
        ref_paste = st.text_area(
            "Paste reference text",
            height=80,
            placeholder="Paste durable facts, standards, internal notes…",
        )
        uploads = st.file_uploader(
            "Or upload files (.txt/.md, .pdf if supported)", accept_multiple_files=True
        )

        submitted = st.form_submit_button("Continue to outline →", type="primary")

    if submitted:
        if not name.strip():
            st.error("Please provide a skill name.")
            return
        try:
            slug = validate_skill_name(name)
        except ReservedSlugError as exc:
            st.error(str(exc))
            return
        except ValueError as exc:
            st.error(str(exc))
            return

        # Gather reference material.
        file_texts: list[tuple[str, str]] = []
        for up in uploads or []:
            try:
                file_texts.append((up.name, extract_text_from_upload(up.name, up.getvalue())))
            except InputLimitError as exc:
                st.warning(f"Could not read {up.name}: {exc}")
            except Exception as exc:
                st.warning(f"Could not read {up.name}: {exc}")
        try:
            reference_text = combine_references(ref_paste, file_texts)
        except InputLimitError as exc:
            st.error(str(exc))
            return

        spec = SkillSpec(
            name=slug,
            description=description.strip(),
            skill_type=skill_type,
            domain_focus=domain_focus.strip(),
            tags=_parse_list(tags),
            entities=_parse_list(entities),
            requirements=[r.strip() for r in requirements.splitlines() if r.strip()],
            base_skill=base_skill,
            token_budget=token_budget,
            tone=tone,
            reference_text=reference_text,
        )
        st.session_state["wiz_spec"] = spec
        st.session_state["wiz_outline"] = ""
        st.session_state["wiz_draft"] = ""
        st.session_state["wiz_stage"] = "outline"
        st.rerun()


# ---------------------------------------------------------------------------
def _spec_summary(spec: SkillSpec) -> None:
    bits = [f"`{spec.name}`", f"type: {spec.skill_type}", f"tone: {spec.tone}"]
    if spec.base_skill:
        bits.append(f"extends: `{spec.base_skill}`")
    if spec.reference_text:
        bits.append(f"{token_badge(spec.reference_text)} of references")
    st.caption(" · ".join(bits))


def _outline_stage() -> None:
    spec: SkillSpec | None = st.session_state.get("wiz_spec")
    if spec is None:
        st.session_state["wiz_stage"] = "spec"
        st.rerun()
        return
    _spec_summary(spec)

    if require_key():
        model = model_selectbox("Model", key="wiz_outline_model")
        if st.button("✨ Generate / regenerate outline"):
            try:
                with st.spinner("Planning outline…"):
                    res = pipeline.plan_outline(_client(), spec, model=model)
                st.session_state["wiz_outline"] = res.content
            except LLMError as exc:
                st.error(str(exc))

    st.text_area("Outline (edit freely before drafting)", key="wiz_outline", height=320)

    c1, _c2, c3 = st.columns([1, 1, 1])
    if c1.button("← Back"):
        st.session_state["wiz_stage"] = "spec"
        st.rerun()
    if c3.button("Generate draft →", type="primary"):
        st.session_state["wiz_stage"] = "draft"
        st.session_state["wiz_draft"] = ""
        st.rerun()


def _draft_stage() -> None:
    spec: SkillSpec | None = st.session_state.get("wiz_spec")
    if spec is None:
        st.session_state["wiz_stage"] = "spec"
        st.rerun()
        return
    _spec_summary(spec)

    if require_key():
        model = model_selectbox("Model", key="wiz_draft_model")
        if st.button("✨ Generate / regenerate draft", type="primary"):
            try:
                with st.spinner("Drafting SKILL.md…"):
                    res = pipeline.generate_draft(
                        _client(), spec, st.session_state.get("wiz_outline", ""), model=model
                    )
                st.session_state["wiz_draft"] = res.content
                st.session_state["wiz_draft_model"] = res.model
            except LLMError as exc:
                st.error(str(exc))

    draft = st.session_state.get("wiz_draft", "")
    if not draft:
        st.info("Generate a draft to preview, validate and save it.")
        if st.button("← Back to outline"):
            st.session_state["wiz_stage"] = "outline"
            st.rerun()
        return

    edit_col, view_col = st.columns(2)
    with edit_col:
        st.text_area("Draft SKILL.md", key="wiz_draft", height=480)
        st.caption(token_badge(st.session_state.get("wiz_draft", "")))
    with view_col:
        tab_prev, tab_val = st.tabs(["Preview", "Validation"])
        with tab_prev:
            st.markdown(st.session_state.get("wiz_draft", ""))
        with tab_val:
            report = validate_skill_md(
                st.session_state.get("wiz_draft", ""),
                expected_name=slugify(spec.name),
                token_budget=spec.token_budget,
            )
            st.caption(report.summary())
            render_validation(report)

    st.divider()
    slug = slugify(spec.name)
    notes = st.text_input("Version notes", placeholder="Initial draft")
    b1, b2, b3 = st.columns(3)
    if b1.button("← Back to outline"):
        st.session_state["wiz_stage"] = "outline"
        st.rerun()
    if b2.button("💾 Save version", type="primary"):
        meta = SkillMeta.from_spec(
            spec, model=st.session_state.get("wiz_draft_model", ""), version_notes=notes
        )
        version = store().save_new_version(slug, st.session_state["wiz_draft"], meta)
        st.success(f"Saved `{slug}` v{version}.")
        st.session_state["editor_slug"] = slug
        st.session_state["editor_version"] = version
    if b3.button("📝 Open in Editor"):
        meta = SkillMeta.from_spec(
            spec, model=st.session_state.get("wiz_draft_model", ""), version_notes=notes
        )
        version = store().save_new_version(slug, st.session_state["wiz_draft"], meta)
        goto(PAGE_EDITOR, editor_slug=slug, editor_version=version, editor_loaded_key=None)


def _client():
    from . import get_client

    return get_client()
