"""Normalization services for ingested documents."""

from __future__ import annotations

import re

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
