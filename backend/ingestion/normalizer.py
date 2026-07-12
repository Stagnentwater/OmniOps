"""Normalization services for ingested documents."""

from __future__ import annotations

import re
import unicodedata

from ingestion.models import DocumentContent


def _clean_whitespace_simple(text: str) -> str:
    """Clean whitespace within text while preserving paragraph structure.

    Rules:
    - Remove leading/trailing whitespace
    - Normalize multiple spaces to single space
    - Preserve single newlines and double newlines (paragraph breaks)
    - Preserve indentation (leading spaces on lines)
    """
    if not text:
        return text

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        # Strip trailing whitespace from each line
        line = line.rstrip()

        # Normalize internal spaces (multiple consecutive spaces → single space)
        # But preserve leading spaces (indentation)
        stripped_left = line.lstrip()
        leading_spaces = len(line) - len(stripped_left)

        if stripped_left:
            # Normalize internal whitespace
            normalized = re.sub(r" +", " ", stripped_left)
            cleaned_lines.append(" " * leading_spaces + normalized)
        else:
            # Empty or whitespace-only line
            cleaned_lines.append("")

    # Reconstruct text, collapsing excessive blank lines
    # Keep single blank lines (paragraph breaks) but remove multiple consecutive blank lines
    result_lines = []
    blank_count = 0

    for line in cleaned_lines:
        if not line or not line.strip():
            blank_count += 1
            if blank_count <= 1:
                result_lines.append("")
        else:
            blank_count = 0
            result_lines.append(line)

    # Join and strip overall leading/trailing whitespace
    result = "\n".join(result_lines).strip()
    return result


def _clean_pages(pages: tuple[str, ...]) -> tuple[str, ...]:
    """Clean whitespace from individual pages.

    Each page is normalized independently, preserving the page structure.
    """
    if not pages:
        return pages

    cleaned = tuple(_clean_whitespace_simple(page) for page in pages)
    return cleaned


def clean_whitespace(document_content: DocumentContent) -> DocumentContent:
    """Clean whitespace from document content.

    Normalizes whitespace in both the full text and individual pages while
    preserving:
    - Paragraph structure (blank lines)
    - Meaningful indentation
    - Page boundaries

    Returns:
        New DocumentContent with whitespace cleaned.
    """
    cleaned_text = _clean_whitespace_simple(document_content.text)
    cleaned_pages = _clean_pages(document_content.pages)

    return DocumentContent(
        filename=document_content.filename,
        text=cleaned_text,
        pages=cleaned_pages,
        page_count=document_content.page_count,
        metadata=document_content.metadata,
    )


# NORM-002: Encoding Normalization


def _normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC form.

    NFC (Canonical Decomposition, followed by Canonical Composition) is the
    recommended normalization form for most text processing, as it:
    - Combines equivalent characters consistently
    - Ensures canonical ordering
    - Improves downstream search and comparison
    - Handles composed vs decomposed accented characters uniformly

    Example:
        é (U+00E9) and é (U+0065 U+0301) normalize to the same form.
    """
    if not text:
        return text
    return unicodedata.normalize("NFC", text)


def _remove_control_characters(text: str) -> str:
    """Remove control characters except newlines and tabs.

    Control characters (Cc category) can cause:
    - Text processing issues
    - Rendering problems
    - Search/index corruption

    Preserves:
    - Newlines (U+000A)
    - Tabs (U+0009)
    - Carriage returns (U+000D) for Windows line endings
    """
    if not text:
        return text

    # Define characters to preserve
    preserve = {"\n", "\t", "\r"}

    result = "".join(
        char for char in text
        if char in preserve or unicodedata.category(char)[0] != "C"
    )
    return result


def _replace_replacement_character(text: str) -> str:
    """Replace Unicode replacement character (U+FFFD) with space.

    The replacement character indicates encoding errors or invalid sequences.
    Replacing with space preserves word boundaries while removing corruption.
    """
    if not text:
        return text
    return text.replace("\ufffd", " ")


def normalize_encoding(document_content: DocumentContent) -> DocumentContent:
    """Normalize Unicode encoding in document content.

    Transformations applied to both text and pages:
    1. Normalize Unicode to NFC form (canonical composition)
    2. Remove control characters (except newlines, tabs, carriage returns)
    3. Replace Unicode replacement characters with spaces

    Returns:
        New DocumentContent with normalized encoding.

    Note:
        This function does NOT change the document's declared encoding or
        re-decode bytes. It normalizes Unicode strings that are already decoded.
    """
    # Normalize text
    normalized_text = _normalize_unicode(document_content.text)
    normalized_text = _remove_control_characters(normalized_text)
    normalized_text = _replace_replacement_character(normalized_text)

    # Normalize pages
    normalized_pages = tuple(
        _replace_replacement_character(
            _remove_control_characters(_normalize_unicode(page))
        )
        for page in document_content.pages
    )

    # Enrich metadata with normalization info
    enriched_metadata = dict(document_content.metadata)
    enriched_metadata["encoding_normalized"] = True
    enriched_metadata["unicode_form"] = "NFC"

    return DocumentContent(
        filename=document_content.filename,
        text=normalized_text,
        pages=normalized_pages,
        page_count=document_content.page_count,
        metadata=enriched_metadata,
    )
