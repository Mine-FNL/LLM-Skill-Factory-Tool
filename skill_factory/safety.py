"""Input validation and resource limits.

Centralised so the UI, the CLI, and any embedder apply the same rules. Hard
limits exist because every byte the user uploads gets injected into an LLM
prompt — runaway sizes can blow out context windows or blow through rate
limits in seconds.

Defaults are sized for a typical LLM context:

- 200 KB pasted/uploaded reference text (≈ 50k tokens — well below modern
  200k-token context windows but large enough for real docs).
- 5 MB binary upload (PDFs can be surprisingly large for 100-page docs).
- 64-character skill names (matches the validator's MAX_NAME_LEN).

Override via the ``SF_MAX_REF_TEXT_BYTES`` and ``SF_MAX_UPLOAD_BYTES`` env vars
if your deployment has different constraints.

Env vars are read at *call time*, not at import time, so tests can monkeypatch
them with ``monkeypatch.setenv(...)``.
"""

from __future__ import annotations

import os
from pathlib import Path

from .skill_store import slugify

# Skill slugs we refuse to create so we don't shadow library-internal folders
# or filesystems (Windows reserved names included for safety on shared volumes).
RESERVED_SLUGS: frozenset[str] = frozenset(
    {
        # current / parent / special
        "",
        ".",
        "..",
        "~",
        # Windows reserved device names
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }
)


class InputLimitError(ValueError):
    """A user-supplied input exceeded a configured size limit."""


class ReservedSlugError(ValueError):
    """A skill slug collides with a reserved name."""


def _env_int(name: str, default: int) -> int:
    """Read an int from the environment, falling back to ``default`` on any error."""

    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


# Default values kept as module constants for documentation / introspection,
# but the validators always re-read the env at call time so test overrides work.
DEFAULT_REF_TEXT_BYTES = 200 * 1024  # 200 KB
DEFAULT_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_NAME_LEN = 64


def _max_ref_text_bytes() -> int:
    return _env_int("SF_MAX_REF_TEXT_BYTES", DEFAULT_REF_TEXT_BYTES)


def _max_upload_bytes() -> int:
    return _env_int("SF_MAX_UPLOAD_BYTES", DEFAULT_UPLOAD_BYTES)


def _max_name_len() -> int:
    return _env_int("SF_MAX_NAME_LEN", DEFAULT_NAME_LEN)


# Module-level proxies that always re-read the env. Cheaper than attributes
# and still readable from other modules (`from skill_factory.safety import MAX_NAME_LEN`).
def MAX_REF_TEXT_BYTES() -> int:
    return _max_ref_text_bytes()


def MAX_UPLOAD_BYTES() -> int:
    return _max_upload_bytes()


def MAX_NAME_LEN() -> int:
    return _max_name_len()


def validate_reference_text(text: str) -> str:
    """Reject oversized reference text. Returns the text unchanged on success."""
    if not isinstance(text, str):
        raise InputLimitError("Reference text must be a string.")
    size = len(text.encode("utf-8", errors="replace"))
    cap = _max_ref_text_bytes()
    if size > cap:
        raise InputLimitError(
            f"Reference text is {size:,} bytes; limit is {cap:,}. "
            "Trim it or split it across multiple generations."
        )
    return text


def validate_upload(filename: str, data: bytes) -> bytes:
    """Reject oversize uploads before extraction. Returns bytes unchanged on success."""
    if not isinstance(data, (bytes, bytearray)):
        raise InputLimitError(f"Upload '{filename}' is not binary data.")
    size = len(data)
    cap = _max_upload_bytes()
    if size > cap:
        raise InputLimitError(f"Upload '{filename}' is {size:,} bytes; limit is {cap:,}.")
    return bytes(data)


def validate_skill_name(name: str) -> str:
    """Slugify the name and reject collisions with reserved slugs.

    Reserved names are checked *after* slugification so an input of ``"."``
    or ``"con"`` is rejected with a clear ``ReservedSlugError`` rather than a
    generic empty-slug ``ValueError``.
    """

    if not isinstance(name, str):
        raise ValueError("Skill name must be a string.")
    slug = slugify(name)
    cap = _max_name_len()
    if slug in RESERVED_SLUGS:
        raise ReservedSlugError(
            f"'{slug or name}' is a reserved name; pick a different skill name."
        )
    if not slug:
        raise ValueError("Skill name is empty after slugification.")
    if len(slug) > cap:
        raise ValueError(f"Skill slug '{slug}' is {len(slug)} chars; limit is {cap}.")
    return slug


def safe_path_within(root: Path, target: Path) -> Path:
    """Return ``target`` resolved, or raise if it escapes ``root``.

    Defence in depth against path traversal when constructing on-disk paths
    from user input (e.g. custom preset stems).
    """

    root_resolved = root.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Path '{target}' is outside the allowed root '{root}'.") from exc
    return target_resolved
