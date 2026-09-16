"""Batch generator: produce many specialist overlays from one base skill.

Generic by design — entities can come from a JSON preset (e.g. QSE banks, S&P 500,
a list of microservices) or simply be pasted one per line.
"""

from __future__ import annotations

import streamlit as st

from skill_factory import pipeline, presets
from skill_factory.config import PROJECT_ROOT
from skill_factory.models import SkillMeta, SkillSpec
from skill_factory.safety import ReservedSlugError, validate_skill_name
from skill_factory.skill_store import slugify
from skill_factory.validator import validate_skill_md

from . import get_client, model_selectbox, require_key, store

PRESETS_DIR = PROJECT_ROOT / "presets"


def render() -> None:
    st.header("🏭 Batch Generator")
    s = store()
    skills = s.list_skills()
    if not skills:
        st.info("Create a base skill first in **New Skill**, then batch-generate overlays from it.")
        return

    st.markdown("Generate one **specialist overlay** per entity, extending a base skill.")
    c1, c2 = st.columns([2, 1])
    base_slug = c1.selectbox("Base skill", skills)
    base_versions = s.versions(base_slug)
    base_version = c2.selectbox(
        "Version", base_versions, index=len(base_versions) - 1, format_func=lambda v: f"v{v}"
    )

    # --- entities: from preset or pasted -----------------------------------
    preset_names = presets.list_presets(PRESETS_DIR)
    pc1, pc2 = st.columns([2, 1])
    preset_choice = pc1.selectbox(
        "Load entities from preset (optional)", ["— none —", *preset_names]
    )
    if pc2.button("Load preset", disabled=preset_choice == "— none —"):
        preset = presets.load_preset(PRESETS_DIR, preset_choice)
        st.session_state["batch_entities"] = "\n".join(presets.entity_labels(preset))

    entities_text = st.text_area(
        "Entities (one per line)",
        key="batch_entities",
        height=160,
        placeholder="Stripe\nPlaid\nAdyen",
    )
    entities = [e.strip() for e in entities_text.splitlines() if e.strip()]

    # --- shared overlay settings -------------------------------------------
    with st.expander("Overlay settings", expanded=True):
        pattern = st.text_input(
            "Name pattern",
            value="{slug}-specialist",
            help="Use {slug} as the placeholder for each entity's slug.",
        )
        sc1, sc2 = st.columns(2)
        tone = sc1.selectbox("Tone", ["concise", "balanced", "comprehensive"], index=1)
        token_budget = sc2.slider("Target body size (tokens)", 300, 3000, 1000, 100)
        tags = [t.strip() for t in st.text_input("Tags (comma-separated)").split(",") if t.strip()]
        requirements = [
            r.strip()
            for r in st.text_area("Shared requirements (one per line)", height=80).splitlines()
            if r.strip()
        ]

    if not require_key():
        return
    model = model_selectbox("Model", key="batch_model")

    if st.button(f"⚙️ Generate {len(entities)} overlay(s)", type="primary", disabled=not entities):
        _run_batch(
            s,
            base_slug,
            base_version,
            entities,
            pattern,
            tone,
            token_budget,
            tags,
            requirements,
            model,
        )

    _render_results()


def _final_slug(entity: str, pattern: str) -> str:
    """Resolve a final slug, refusing reserved names so we never shadow system folders."""
    base = slugify(entity)
    try:
        candidate = slugify(pattern.format(slug=base)) or base
    except Exception:
        candidate = base
    try:
        return validate_skill_name(candidate)
    except (ReservedSlugError, ValueError):
        # Fall back to the entity-only slug if the pattern produced a reserved name.
        try:
            return validate_skill_name(base)
        except (ReservedSlugError, ValueError):
            return base  # last-resort: the entity name itself


def _run_batch(
    s, base_slug, base_version, entities, pattern, tone, token_budget, tags, requirements, model
) -> None:
    base_md = s.load_content(base_slug, base_version)
    client = get_client()
    prog = st.progress(0.0, text="Starting…")
    results = []
    for i, entity in enumerate(entities):
        final_slug = _final_slug(entity, pattern)
        spec = SkillSpec(
            name=final_slug,
            description=f"Use when the work specifically concerns {entity}. "
            f"Specialises the '{base_slug}' base skill.",
            skill_type="specialist",
            tags=tags,
            entities=[entity],
            requirements=requirements,
            base_skill=base_slug,
            token_budget=token_budget,
            tone=tone,
        )
        prog.progress(i / len(entities), text=f"Generating {entity}…")
        try:
            res = pipeline.generate_overlay(client, base_md, entity, spec, model=model)
            meta = SkillMeta.from_spec(
                spec, model=res.model, version_notes=f"Batch overlay from {base_slug}"
            )
            version = s.save_new_version(final_slug, res.content, meta)
            rep = validate_skill_md(res.content, expected_name=final_slug)
            results.append(
                {
                    "entity": entity,
                    "slug": final_slug,
                    "version": version,
                    "status": "ok" if rep.ok else "saved (with warnings)",
                    "issues": rep.summary(),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "entity": entity,
                    "slug": final_slug,
                    "version": None,
                    "status": "failed",
                    "issues": str(exc),
                }
            )
    prog.progress(1.0, text="Done")
    st.session_state["batch_results"] = results


def _render_results() -> None:
    results = st.session_state.get("batch_results")
    if not results:
        return
    st.divider()
    ok = sum(1 for r in results if r["version"] is not None)
    st.subheader(f"Results: {ok}/{len(results)} generated")
    st.dataframe(results, use_container_width=True, hide_index=True)
