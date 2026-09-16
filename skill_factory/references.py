"""Reference-material ingestion for the optional context-injection stage.

Plain text and markdown are always supported. PDF extraction is enabled only if
``pypdf`` is installed; otherwise the feature degrades gracefully with a clear
message instead of crashing.

All inputs pass through :mod:`skill_factory.safety` so oversized uploads /
pasted text are rejected before they reach the LLM prompt.
"""

from __future__ import annotations

import importlib.util
import io

from .safety import validate_reference_text, validate_upload

# Detect pypdf without importing it: importing pypdf eagerly pulls in `cryptography`,
# whose native bindings can panic on misconfigured systems. find_spec is cheap and
# side-effect-free, so we defer the real import to extraction time.
PDF_AVAILABLE = importlib.util.find_spec("pypdf") is not None

TEXT_EXTENSIONS = (".txt", ".md", ".markdown", ".rst", ".csv", ".json")


def extract_text_from_upload(filename: str, data: bytes) -> str:
    """Extract text from an uploaded file's raw bytes.

    Raises ``ValueError`` for unsupported types (e.g. PDF when pypdf is missing)
    or ``InputLimitError`` when the upload exceeds the configured size limit.
    """

    # Reject oversize uploads BEFORE extracting — a 200MB PDF doesn't need to
    # be parsed to know we don't want it.
    validate_upload(filename, data)

    lower = filename.lower()
    if lower.endswith(TEXT_EXTENSIONS):
        return data.decode("utf-8", errors="replace")

    if lower.endswith(".pdf"):
        if not PDF_AVAILABLE:
            raise ValueError(
                "PDF support requires the 'pypdf' package. Install it or paste the text manually."
            )
        try:
            from pypdf import PdfReader
        except BaseException as exc:  # native backend may be misconfigured
            raise ValueError(f"PDF support is unavailable on this system: {exc}") from exc
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return "\n\n".join(pages).strip()

    raise ValueError(
        f"Unsupported file type for '{filename}'. Supported: "
        f"{', '.join(TEXT_EXTENSIONS)}" + (", .pdf" if PDF_AVAILABLE else "")
    )


def combine_references(pasted: str, files: list[tuple[str, str]]) -> str:
    """Combine pasted text and (name, extracted_text) pairs into one context blob.

    Enforces the global reference-text size cap; callers receive ``InputLimitError``
    rather than a silently truncated prompt.
    """

    chunks: list[str] = []
    if pasted.strip():
        chunks.append(pasted.strip())
    for name, text in files:
        if text.strip():
            chunks.append(f"# Source: {name}\n{text.strip()}")
    combined = "\n\n---\n\n".join(chunks)
    return validate_reference_text(combined)
