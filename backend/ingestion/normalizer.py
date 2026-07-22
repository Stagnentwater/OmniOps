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


# NORM-003: Page Segmentation

def segment_pages(document_content: DocumentContent) -> DocumentContent:
    """Segment pages of document content into structural components.

    Identifies headers, footers, section headings, and body paragraphs.
    Enriches metadata with:
    - headers: list of detected header lines
    - footers: list of detected footer lines
    - sections: list of section headings
    - page_segments: list of segments per page
    """
    # Split pages into lines
    pages_lines = [page.split("\n") for page in document_content.pages]
    page_count = len(document_content.pages)

    headers = set()
    footers = set()

    # Detect headers and footers across pages (only if multi-page)
    if page_count > 1:
        # Check first line of each page
        first_lines = [lines[0].strip() for lines in pages_lines if lines]
        if first_lines:
            freq: dict[str, int] = {}
            for line in first_lines:
                if line:
                    freq[line] = freq.get(line, 0) + 1
            # If any line appears in >= 50% of the pages (or at least 2 pages), it is a header
            for line, count in freq.items():
                if count >= max(2, page_count // 2):
                    headers.add(line)

        # Check last line of each page
        last_lines = [lines[-1].strip() for lines in pages_lines if lines]
        if last_lines:
            freq = {}
            for line in last_lines:
                if line:
                    freq[line] = freq.get(line, 0) + 1
            for line, count in freq.items():
                if count >= max(2, page_count // 2):
                    footers.add(line)

    # Detect section headings and build page segments
    sections = []
    page_segments = []

    # Heading patterns:
    # 1. 1.2.3 Heading Name
    # 2. Section 1: Intro
    # 3. ALL CAPS line (between 3 and 80 chars, only letters/numbers/spaces/some punctuation)
    num_pattern = re.compile(r"^\d+(\.\d+)*\s+[A-Z_a-z].*")
    sec_pattern = re.compile(r"^(Section|Chapter|Appendix)\s+[A-Za-z0-9]+.*", re.IGNORECASE)
    all_caps_pattern = re.compile(r"^[A-Z0-9\s\-_\(\),.:;']{3,80}$")

    for page_idx, lines in enumerate(pages_lines):
        segments = []
        current_paragraph = []
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                if current_paragraph:
                    segments.append({"type": "paragraph", "text": " ".join(current_paragraph)})
                    current_paragraph = []
                continue

            # Classify
            if line_stripped in headers:
                if current_paragraph:
                    segments.append({"type": "paragraph", "text": " ".join(current_paragraph)})
                    current_paragraph = []
                segments.append({"type": "header", "text": line_stripped})
            elif line_stripped in footers:
                if current_paragraph:
                    segments.append({"type": "paragraph", "text": " ".join(current_paragraph)})
                    current_paragraph = []
                segments.append({"type": "footer", "text": line_stripped})
            elif (num_pattern.match(line_stripped) or 
                  sec_pattern.match(line_stripped) or 
                  (all_caps_pattern.match(line_stripped) and not line_stripped.isdigit())):
                if current_paragraph:
                    segments.append({"type": "paragraph", "text": " ".join(current_paragraph)})
                    current_paragraph = []
                segments.append({"type": "heading", "text": line_stripped})
                sections.append(line_stripped)
            else:
                current_paragraph.append(line_stripped)
                
        if current_paragraph:
            segments.append({"type": "paragraph", "text": " ".join(current_paragraph)})
            
        page_segments.append(segments)

    # Enrich metadata
    new_metadata = dict(document_content.metadata)
    new_metadata["headers"] = sorted(list(headers))
    new_metadata["footers"] = sorted(list(footers))
    new_metadata["sections"] = sections
    new_metadata["page_segments"] = page_segments
    new_metadata["page_segmentation_completed"] = True

    return DocumentContent(
        filename=document_content.filename,
        text=document_content.text,
        pages=document_content.pages,
        page_count=document_content.page_count,
        metadata=new_metadata,
    )


# NORM-004: Table Extraction

def extract_tables(document_content: DocumentContent) -> DocumentContent:
    """Identify and extract tabular data from document text or page content.

    For CSV: reconstructs row tables from pages.
    For DOCX: detects contiguous pipe-delimited lines.
    For PDF: detects space/tab aligned column layouts.
    """
    extracted_tables = []
    has_tables = False

    # 1. Check if CSV file
    is_csv = (
        document_content.filename.lower().endswith(".csv") or
        document_content.metadata.get("delimiter") == ","
    )

    if is_csv and document_content.pages:
        headers = []
        rows = []
        for page in document_content.pages:
            row_dict = {}
            for line in page.split("\n"):
                if ": " in line:
                    k, v = line.split(": ", 1)
                    k = k.strip()
                    v = v.strip()
                    row_dict[k] = v
                    if k not in headers:
                        headers.append(k)
            if row_dict:
                row_values = [row_dict.get(h, "") for h in headers]
                rows.append(row_values)
        if headers:
            extracted_tables.append({
                "type": "csv_reconstructed",
                "headers": headers,
                "rows": rows
            })
            has_tables = True

    # 2. Check for DOCX pipe-delimited tables or PDF/text tables
    if not is_csv:
        lines = document_content.text.split("\n")

        in_pipe_table = False
        current_pipe_table = None

        in_space_table = False
        current_space_table = None
        expected_cols = 0

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                # Empty line closes any active table
                if in_pipe_table:
                    if current_pipe_table and len(current_pipe_table["rows"]) >= 0:
                        extracted_tables.append(current_pipe_table)
                    in_pipe_table = False
                    current_pipe_table = None
                if in_space_table:
                    if current_space_table and len(current_space_table["rows"]) >= 1:
                        extracted_tables.append(current_space_table)
                    in_space_table = False
                    current_space_table = None
                continue

            # Try parsing pipe-delimited line
            if "|" in line_stripped:
                if in_space_table:
                    if current_space_table and len(current_space_table["rows"]) >= 1:
                        extracted_tables.append(current_space_table)
                    in_space_table = False
                    current_space_table = None

                cells = [c.strip() for c in line_stripped.split("|")]
                if len(cells) > 1:
                    if not in_pipe_table:
                        in_pipe_table = True
                        current_pipe_table = {
                            "type": "pipe_delimited",
                            "headers": cells,
                            "rows": []
                        }
                    else:
                        if current_pipe_table is not None:
                            current_pipe_table["rows"].append(cells)
                continue
            else:
                if in_pipe_table:
                    if current_pipe_table and len(current_pipe_table["rows"]) >= 0:
                        extracted_tables.append(current_pipe_table)
                    in_pipe_table = False
                    current_pipe_table = None

            # Try parsing space/tab-separated line
            cols = [c.strip() for c in re.split(r'\s{2,}|\t', line_stripped) if c.strip()]
            if len(cols) >= 2:
                if not in_space_table:
                    in_space_table = True
                    expected_cols = len(cols)
                    current_space_table = {
                        "type": "space_aligned",
                        "headers": cols,
                        "rows": []
                    }
                else:
                    if len(cols) == expected_cols:
                        if current_space_table is not None:
                            current_space_table["rows"].append(cols)
                    else:
                        if current_space_table and len(current_space_table["rows"]) >= 1:
                            extracted_tables.append(current_space_table)
                        in_space_table = True
                        expected_cols = len(cols)
                        current_space_table = {
                            "type": "space_aligned",
                            "headers": cols,
                            "rows": []
                        }
            else:
                if in_space_table:
                    if current_space_table and len(current_space_table["rows"]) >= 1:
                        extracted_tables.append(current_space_table)
                    in_space_table = False
                    current_space_table = None

        # Clean up open tables
        if in_pipe_table and current_pipe_table:
            extracted_tables.append(current_pipe_table)
        if in_space_table and current_space_table and len(current_space_table["rows"]) >= 1:
            extracted_tables.append(current_space_table)

        if extracted_tables:
            has_tables = True

    new_metadata = dict(document_content.metadata)
    new_metadata["has_tables"] = has_tables or new_metadata.get("has_tables", False)
    new_metadata["extracted_tables"] = extracted_tables
    new_metadata["table_extraction_completed"] = True

    return DocumentContent(
        filename=document_content.filename,
        text=document_content.text,
        pages=document_content.pages,
        page_count=document_content.page_count,
        metadata=new_metadata,
    )


# NORM-005: Image Extraction

def extract_images(document_content: DocumentContent) -> DocumentContent:
    """Identify and extract image/figure references and captions from text.

    Scans the pages for figure caption lines and inline figure references.
    """
    extracted_images = []
    has_images = False

    # Check parser metadata first
    parser_metadata = document_content.metadata or {}
    if "image" in str(parser_metadata).lower() or parser_metadata.get("has_images"):
        has_images = True

    seen_ids = set()

    for page_idx, page in enumerate(document_content.pages):
        for line in page.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check if line matches a figure caption/definition
            cap_match = re.match(
                r'^\s*(Figure|Fig\.|Image|Img\.)\s+(\d+)(?:[\s\.:\-]+(.*))?$',
                line_stripped,
                re.IGNORECASE
            )
            if cap_match:
                label_type = cap_match.group(1)
                num = cap_match.group(2)
                caption = cap_match.group(3) or ""

                normalized_label = label_type.capitalize()
                if normalized_label.startswith("Fig"):
                    normalized_label = "Figure"
                elif normalized_label.startswith("Img"):
                    normalized_label = "Image"
                fig_id = f"{normalized_label} {num}"

                seen_ids.add(fig_id)
                # Overwrite/update if it was added as inline reference earlier
                extracted_images = [img for img in extracted_images if img["id"] != fig_id]
                extracted_images.append({
                    "id": fig_id,
                    "label": normalized_label,
                    "number": num,
                    "caption": caption.strip(),
                    "page_index": page_idx
                })
                has_images = True
            else:
                # Check for inline references
                ref_matches = re.findall(
                    r'\b(Figure|Fig\.|Image|Img\.)\s+(\d+)\b',
                    line_stripped,
                    re.IGNORECASE
                )
                for label_type, num in ref_matches:
                    normalized_label = label_type.capitalize()
                    if normalized_label.startswith("Fig"):
                        normalized_label = "Figure"
                    elif normalized_label.startswith("Img"):
                        normalized_label = "Image"
                    fig_id = f"{normalized_label} {num}"

                    if fig_id not in seen_ids:
                        seen_ids.add(fig_id)
                        extracted_images.append({
                            "id": fig_id,
                            "label": normalized_label,
                            "number": num,
                            "caption": "",
                            "page_index": page_idx
                        })
                        has_images = True

    # Enrich metadata
    new_metadata = dict(document_content.metadata)
    new_metadata["has_images"] = has_images or new_metadata.get("has_images", False)
    new_metadata["extracted_images"] = extracted_images
    new_metadata["image_extraction_completed"] = True

    return DocumentContent(
        filename=document_content.filename,
        text=document_content.text,
        pages=document_content.pages,
        page_count=document_content.page_count,
        metadata=new_metadata,
    )

