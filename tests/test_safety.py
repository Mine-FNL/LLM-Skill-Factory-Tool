"""Tests for input safety: size caps, reserved slugs, path-traversal guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from skill_factory.safety import (
    DEFAULT_NAME_LEN,
    DEFAULT_REF_TEXT_BYTES,
    DEFAULT_UPLOAD_BYTES,
    RESERVED_SLUGS,
    InputLimitError,
    ReservedSlugError,
    safe_path_within,
    validate_reference_text,
    validate_skill_name,
    validate_upload,
)


def test_validate_reference_text_accepts_under_limit():
    text = "hello world"
    assert validate_reference_text(text) == text


def test_validate_reference_text_rejects_oversize(monkeypatch):
    monkeypatch.setenv("SF_MAX_REF_TEXT_BYTES", "10")
    with pytest.raises(InputLimitError):
        validate_reference_text("x" * 100)


def test_validate_upload_accepts_small():
    assert validate_upload("a.txt", b"hi") == b"hi"


def test_validate_upload_rejects_oversize(monkeypatch):
    monkeypatch.setenv("SF_MAX_UPLOAD_BYTES", "4")
    with pytest.raises(InputLimitError):
        validate_upload("huge.bin", b"x" * 1024)


def test_validate_upload_rejects_non_bytes():
    with pytest.raises(InputLimitError):
        validate_upload("weird.txt", "not bytes")  # type: ignore[arg-type]


def test_validate_skill_name_normalises():
    assert validate_skill_name("My Skill!!") == "my-skill"


def test_validate_skill_name_rejects_empty():
    with pytest.raises(ValueError):
        validate_skill_name("   ///  ")


def test_validate_skill_name_rejects_reserved():
    for reserved in ["con", "aux", "com1", "nul", ".", ".."]:
        with pytest.raises(ReservedSlugError):
            validate_skill_name(reserved)


def test_validate_skill_name_enforces_max_len(monkeypatch):
    monkeypatch.setenv("SF_MAX_NAME_LEN", "8")
    with pytest.raises(ValueError):
        validate_skill_name("this-is-a-long-skill")


def test_validate_skill_name_rejects_non_string():
    with pytest.raises(ValueError):
        validate_skill_name(123)  # type: ignore[arg-type]


def test_safe_path_within_accepts_nested(tmp_path):
    target = tmp_path / "a" / "b" / "c.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    resolved = safe_path_within(tmp_path, target)
    assert resolved == target.resolve()


def test_safe_path_within_rejects_traversal(tmp_path):
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError):
        safe_path_within(tmp_path, outside / "..")


def test_safe_path_within_rejects_absolute_outside(tmp_path):
    with pytest.raises(ValueError):
        safe_path_within(tmp_path, Path("/etc/passwd"))


def test_reserved_slugs_is_a_frozenset():
    """RESERVED_SLUGS must be immutable — callers depend on it being static."""
    assert isinstance(RESERVED_SLUGS, frozenset)
    assert "con" in RESERVED_SLUGS
    assert "" in RESERVED_SLUGS


def test_default_caps_are_positive():
    """A zero or negative default cap would block every skill name / upload / reference."""
    assert DEFAULT_NAME_LEN > 0
    assert DEFAULT_REF_TEXT_BYTES > 0
    assert DEFAULT_UPLOAD_BYTES > 0
