"""Language-tag normalization for providers.

Evaluator language selections may be a bare ISO-639 code (``hi``) or already
region-tagged (``hi-IN``). Provider APIs (Sarvam) require BCP-47 language tags,
so normalize at the boundary instead of trusting the stored selection.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "en-IN"


def normalize_bcp47(code: str | None, *, default: str = DEFAULT_LANGUAGE) -> str:
    """Return a BCP-47 tag, mapping a bare code to its ``-IN`` region."""
    if not code:
        return default
    value = str(code).strip()
    if not value:
        return default
    if "-" in value or "_" in value:
        return value.replace("_", "-")
    return f"{value.lower()}-IN"


__all__ = ["DEFAULT_LANGUAGE", "normalize_bcp47"]
