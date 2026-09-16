"""Export & integration helpers: zip a skill, copy it into another app, write a guide."""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path

from .models import SkillMeta
from .skill_store import META_FILENAME, SKILL_FILENAME, SkillStore


def zip_skill(
    store: SkillStore, slug: str, *, version: int | None = None, all_versions: bool = False
) -> bytes:
    """Build an in-memory zip of a skill, ready for a Streamlit download button."""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if all_versions:
            for v in store.versions(slug):
                content, meta = store.load(slug, v)
                zf.writestr(f"{slug}/v{v}/{SKILL_FILENAME}", content)
                zf.writestr(
                    f"{slug}/v{v}/{META_FILENAME}",
                    json.dumps(meta.to_dict(), indent=2, ensure_ascii=False),
                )
        else:
            v = version or store.latest_version(slug)
            content, meta = store.load(slug, v)
            # Flat layout: ready to drop into a skills/<slug>/ folder.
            zf.writestr(f"{slug}/{SKILL_FILENAME}", content)
            zf.writestr(
                f"{slug}/{META_FILENAME}",
                json.dumps(meta.to_dict(), indent=2, ensure_ascii=False),
            )
            zf.writestr(f"{slug}/USAGE.md", usage_guide(slug, meta))
    return buf.getvalue()


def copy_skill_to(
    store: SkillStore, slug: str, dest_dir: Path, *, version: int | None = None
) -> Path:
    """Copy a skill's SKILL.md (+ metadata) into ``dest_dir/<slug>/``."""

    v = version or store.latest_version(slug)
    if v is None:
        raise FileNotFoundError(f"No versions for skill '{slug}'")
    src = store.version_dir(slug, v)
    target = Path(dest_dir) / slug
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / SKILL_FILENAME, target / SKILL_FILENAME)
    if (src / META_FILENAME).exists():
        shutil.copy2(src / META_FILENAME, target / META_FILENAME)
    return target


def usage_guide(slug: str, meta: SkillMeta) -> str:
    """A short, generic guide for wiring the skill into a downstream LLM app."""

    return f"""\
# Using the `{slug}` skill

**What it does:** {meta.description or "(see SKILL.md)"}

## How to use
1. Place `{slug}/SKILL.md` in your application's skills directory.
2. Make your agent/runtime load `SKILL.md` (its `description` field tells the model
   when to activate it).
3. For chat-style apps without a skills loader, paste the body of `SKILL.md` into
   your system prompt.

## Details
- Type: {meta.skill_type}
- Tags: {", ".join(meta.tags) if meta.tags else "—"}
- Version: v{meta.version}
{("- Extends base skill: " + meta.base_skill) if meta.base_skill else ""}
"""
