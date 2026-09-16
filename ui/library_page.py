"""Skill Library: browse, search, filter, and jump to edit/test/export."""

from __future__ import annotations

import streamlit as st

from skill_factory.exporter import zip_skill

from . import PAGE_EDITOR, PAGE_PLAYGROUND, goto, store


def render() -> None:
    st.header("📚 Skill Library")
    s = store()
    metas = s.library()

    if not metas:
        st.info("No skills yet. Head to **New Skill** to create your first one.")
        return

    # Filters
    q = st.text_input("Search", placeholder="name, description, domain…").strip().lower()
    fcol1, fcol2 = st.columns(2)
    all_types = sorted({m.skill_type for m in metas})
    all_tags = sorted({t for m in metas for t in m.tags})
    sel_types = fcol1.multiselect("Type", all_types)
    sel_tags = fcol2.multiselect("Tags", all_tags)

    def matches(m) -> bool:
        if q and q not in f"{m.name} {m.description} {m.domain_focus}".lower():
            return False
        if sel_types and m.skill_type not in sel_types:
            return False
        return not (sel_tags and not set(sel_tags) & set(m.tags))

    filtered = [m for m in metas if matches(m)]
    st.caption(f"{len(filtered)} of {len(metas)} skills")

    cols = st.columns(3)
    for i, m in enumerate(filtered):
        with cols[i % 3]:
            _card(s, m)


def _card(s, m) -> None:
    slug = m.name
    n_versions = len(s.versions(slug))
    with st.container(border=True):
        st.markdown(f"### {slug}")
        badges = [
            f"`{m.skill_type}`",
            f"v{m.version}" + (f" ({n_versions} versions)" if n_versions > 1 else ""),
        ]
        if m.base_skill:
            badges.append(f"⤷ extends `{m.base_skill}`")
        st.caption(" · ".join(badges))
        if m.description:
            st.write(m.description[:160] + ("…" if len(m.description) > 160 else ""))
        if m.tags:
            st.caption("🏷 " + ", ".join(m.tags))

        b1, b2, b3 = st.columns(3)
        if b1.button("📝 Edit", key=f"edit_{slug}"):
            goto(PAGE_EDITOR, editor_slug=slug, editor_version=m.version, editor_loaded_key=None)
        if b2.button("🧪 Test", key=f"test_{slug}"):
            goto(PAGE_PLAYGROUND, pg_slug=slug, pg_version=m.version)
        b3.download_button(
            "⬇️ Zip",
            data=zip_skill(s, slug),
            file_name=f"{slug}.zip",
            mime="application/zip",
            key=f"zip_{slug}",
        )
