import pytest

from skill_factory.references import combine_references, extract_text_from_upload
from skill_factory.safety import InputLimitError


def test_extract_text_file():
    assert extract_text_from_upload("notes.txt", b"hello world") == "hello world"
    assert extract_text_from_upload("doc.md", b"# Title") == "# Title"


def test_unsupported_extension_raises():
    with pytest.raises(ValueError):
        extract_text_from_upload("image.png", b"\x89PNG")


def test_extract_rejects_oversize_upload(monkeypatch):
    monkeypatch.setenv("SF_MAX_UPLOAD_BYTES", "4")
    with pytest.raises(InputLimitError):
        extract_text_from_upload("huge.txt", b"x" * 1024)


def test_combine_references():
    out = combine_references("pasted facts", [("a.md", "from file a"), ("empty.md", "  ")])
    assert "pasted facts" in out
    assert "# Source: a.md" in out
    assert "from file a" in out
    # empty file is skipped
    assert "empty.md" not in out


def test_combine_references_empty():
    assert combine_references("", []) == ""


def test_combine_references_enforces_size_cap(monkeypatch):
    monkeypatch.setenv("SF_MAX_REF_TEXT_BYTES", "20")
    with pytest.raises(InputLimitError):
        combine_references("x" * 100, [])
