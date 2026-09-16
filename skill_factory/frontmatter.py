"""Tiny YAML-frontmatter helpers shared by the validator, store and exporter."""

from __future__ import annotations

from typing import Any

import yaml

_DELIM = "---"


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a ``SKILL.md`` into (frontmatter dict, body).

    Returns an empty dict if no valid frontmatter block is present. Never raises
    on malformed YAML — returns ``{}`` so callers can report it as a lint error.
    """

    stripped = text.lstrip("﻿")  # tolerate BOM
    if not stripped.startswith(_DELIM):
        return {}, text

    lines = stripped.splitlines()
    # Find the closing delimiter after the opening one.
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            end = i
            break
    if end is None:
        return {}, text

    fm_block = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    try:
        data = yaml.safe_load(fm_block) or {}
        if not isinstance(data, dict):
            return {}, body
        return data, body
    except yaml.YAMLError:
        return {}, body


def build_skill_md(frontmatter: dict[str, Any], body: str) -> str:
    """Render frontmatter + body back into a ``SKILL.md`` string."""

    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"{_DELIM}\n{fm}\n{_DELIM}\n\n{body.strip()}\n"


def has_frontmatter(text: str) -> bool:
    fm, _ = split_frontmatter(text)
    return bool(fm)
