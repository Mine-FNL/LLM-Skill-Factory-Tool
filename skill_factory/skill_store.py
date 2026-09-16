"""Filesystem-first storage for skills, with simple version folders.

Layout::

    skills/
      <slug>/
        v1/
          SKILL.md
          metadata.json
        v2/
          ...

Everything is plain text/JSON so it is git-friendly and trivially inspectable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import SkillMeta

_SLUG_RE = re.compile(r"[^a-z0-9]+")
SKILL_FILENAME = "SKILL.md"
META_FILENAME = "metadata.json"


def slugify(name: str) -> str:
    """Convert an arbitrary name to a kebab-case slug (valid skill name)."""

    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug[:64]


class SkillStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # -- paths --------------------------------------------------------------
    def skill_dir(self, slug: str) -> Path:
        return self.root / slug

    def version_dir(self, slug: str, version: int) -> Path:
        return self.skill_dir(slug) / f"v{version}"

    # -- queries ------------------------------------------------------------
    def list_skills(self) -> list[str]:
        """Slugs that have at least one version folder, sorted alphabetically."""

        if not self.root.exists():
            return []
        out = []
        for child in sorted(self.root.iterdir()):
            if child.is_dir() and self.versions(child.name):
                out.append(child.name)
        return out

    def versions(self, slug: str) -> list[int]:
        d = self.skill_dir(slug)
        if not d.exists():
            return []
        nums = []
        for child in d.iterdir():
            m = re.fullmatch(r"v(\d+)", child.name)
            if m and (child / SKILL_FILENAME).exists():
                nums.append(int(m.group(1)))
        return sorted(nums)

    def latest_version(self, slug: str) -> int | None:
        vs = self.versions(slug)
        return vs[-1] if vs else None

    def exists(self, slug: str, version: int | None = None) -> bool:
        if version is None:
            return bool(self.versions(slug))
        return (self.version_dir(slug, version) / SKILL_FILENAME).exists()

    # -- read ---------------------------------------------------------------
    def load_content(self, slug: str, version: int | None = None) -> str:
        version = version or self.latest_version(slug)
        if version is None:
            raise FileNotFoundError(f"No versions for skill '{slug}'")
        path = self.version_dir(slug, version) / SKILL_FILENAME
        return path.read_text(encoding="utf-8")

    def load_meta(self, slug: str, version: int | None = None) -> SkillMeta:
        version = version or self.latest_version(slug)
        if version is None:
            raise FileNotFoundError(f"No versions for skill '{slug}'")
        path = self.version_dir(slug, version) / META_FILENAME
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return SkillMeta.from_dict(data)
        # Fall back to a minimal meta if metadata.json is missing.
        return SkillMeta(name=slug, version=version)

    def load(self, slug: str, version: int | None = None) -> tuple[str, SkillMeta]:
        version = version or self.latest_version(slug)
        return self.load_content(slug, version), self.load_meta(slug, version)

    # -- write --------------------------------------------------------------
    def save_new_version(self, slug: str, content: str, meta: SkillMeta) -> int:
        """Write content as the next version, returning the new version number."""

        next_v = (self.latest_version(slug) or 0) + 1
        meta.version = next_v
        self._write(slug, next_v, content, meta)
        return next_v

    def overwrite_version(self, slug: str, version: int, content: str, meta: SkillMeta) -> None:
        """Overwrite an existing version in place (e.g. small metadata edits)."""

        meta.version = version
        self._write(slug, version, content, meta)

    def update_meta(self, slug: str, version: int, meta: SkillMeta) -> None:
        """Persist only metadata.json (used to record playground test results)."""

        vdir = self.version_dir(slug, version)
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / META_FILENAME).write_text(
            json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _write(self, slug: str, version: int, content: str, meta: SkillMeta) -> None:
        vdir = self.version_dir(slug, version)
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / SKILL_FILENAME).write_text(content, encoding="utf-8")
        (vdir / META_FILENAME).write_text(
            json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- library listing ----------------------------------------------------
    def library(self) -> list[SkillMeta]:
        """Latest-version metadata for every skill, for the library view."""

        metas = []
        for slug in self.list_skills():
            try:
                metas.append(self.load_meta(slug))
            except Exception:
                continue
        return metas
