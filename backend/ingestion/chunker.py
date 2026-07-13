"""Intelligent chunking service for OmniOps ingestion pipeline."""

from __future__ import annotations
import hashlib
import re
from typing import Any

from ingestion.models import DocumentContent
from ingestion.chunk_models import Chunk, ChunkCollection


def _split_text_recursive(text: str, max_chars: int = 1500, overlap_chars: int = 200) -> list[str]:
    """Split text recursively into smaller parts with overlap, preserving boundaries."""
    if len(text) <= max_chars:
        return [text]

    # Split on sentence ends followed by space (or newline)
    sentences = re.split(r'(?<=\. )|(?<=\?\s)|(?<=!\s)', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if not sentence:
            continue
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # Capture overlap
            overlap = current_chunk[-overlap_chars:] if len(current_chunk) > overlap_chars else current_chunk
            # Find first space in overlap to keep word boundary intact
            space_idx = overlap.find(" ")
            if space_idx != -1:
                overlap = overlap[space_idx + 1:]
            current_chunk = overlap + sentence

            # If a single sentence is still larger than max_chars, split on spaces
            if len(current_chunk) > max_chars:
                words = current_chunk.split(" ")
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) + 1 <= max_chars:
                        sub_chunk += (" " if sub_chunk else "") + word
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk.strip())
                        # Prepend overlap of last few words
                        sub_chunk = " ".join(sub_chunk.split(" ")[-5:]) + " " + word
                current_chunk = sub_chunk

    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


def _format_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format a list of headers and rows into a standard Markdown table."""
    if not headers:
        return ""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |"
    ]
    for row in rows:
        # Pad row values if shorter than headers
        padded_row = row + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(padded_row) + " |")
    return "\n".join(lines)


def chunk_document(document_content: DocumentContent, document_id: str) -> ChunkCollection:
    """Perform hybrid structural + recursive chunking on normalized DocumentContent.

    1. Removes header and footer lines.
    2. Identifies and extracts tables as standalone, well-formatted Markdown chunks.
    3. Segments body paragraphs, prepending section/heading context.
    4. Recursively splits large blocks with overlap.
    5. Generates deterministic chunk IDs.
    """
    chunks: list[Chunk] = []
    chunk_index = 0

    # Retrieve normalizations
    metadata = document_content.metadata or {}
    headers = set(metadata.get("headers", []))
    footers = set(metadata.get("footers", []))
    extracted_tables = metadata.get("extracted_tables", [])
    extracted_images = metadata.get("extracted_images", [])

    # Keep track of table row texts to skip duplicating them during regular text chunking
    # e.g. for DOCX/PDF tables, we skip lines matching raw table cells
    table_lines_to_skip = set()
    for table in extracted_tables:
        for row in table.get("rows", []):
            table_lines_to_skip.add(" | ".join(row).strip())
            table_lines_to_skip.add("  ".join(row).strip())
            # Add individual cells and line fragments
            row_line = " ".join(row).strip()
            if len(row_line) > 5:
                table_lines_to_skip.add(row_line)

    # Process all tables as clean, segmented chunks
    # For large tables, we group them in blocks of 15 rows to preserve context without exceeding token size
    for tbl_idx, table in enumerate(extracted_tables):
        tbl_headers = table.get("headers", [])
        tbl_rows = table.get("rows", [])
        tbl_type = table.get("type", "table")
        
        # Determine table page index if specified (e.g. from csv_reconstructed or metadata)
        tbl_page_idx = 0
        
        # Split table into rows blocks
        block_size = 15
        for block_start in range(0, max(1, len(tbl_rows)), block_size):
            block_rows = tbl_rows[block_start:block_start + block_size]
            table_text = _format_markdown_table(tbl_headers, block_rows)
            if not table_text:
                continue

            chunk_text = f"Table {tbl_idx + 1} (Rows {block_start + 1}-{block_start + len(block_rows)}):\n{table_text}"
            
            # Deterministic Chunk ID
            chunk_raw_id = f"{document_id}_{chunk_index}_{chunk_text.strip()}"
            chunk_id = hashlib.sha256(chunk_raw_id.encode("utf-8")).hexdigest()

            chunk_metadata = {
                "document_id": document_id,
                "filename": document_content.filename,
                "page_index": tbl_page_idx,
                "chunk_index": chunk_index,
                "has_tables": True,
                "has_images": False,
                "character_count": len(chunk_text),
                "table_type": tbl_type
            }

            chunks.append(Chunk(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=chunk_index,
                text=chunk_text,
                page_index=tbl_page_idx,
                section="Tables",
                metadata=chunk_metadata
            ))
            chunk_index += 1

    # Figure caption regexes to link images
    fig_ref_pattern = re.compile(r'\b(Figure|Fig\.|Image|Img\.)\s+(\d+)\b', re.IGNORECASE)

    # Process regular paragraphs
    current_section = None
    page_segments = metadata.get("page_segments", [])

    for page_idx, page_text in enumerate(document_content.pages):
        # 1. Use page segments if available
        if page_idx < len(page_segments) and page_segments[page_idx]:
            segments = page_segments[page_idx]
            for seg in segments:
                seg_type = seg.get("type")
                seg_text = seg.get("text", "").strip()

                if not seg_text:
                    continue

                if seg_type == "header" or seg_type == "footer":
                    continue

                if seg_type == "heading":
                    current_section = seg_text
                    continue

                # Skip if this line belongs to an extracted table to prevent duplicate chunking
                if any(t_line in seg_text for t_line in table_lines_to_skip):
                    continue

                # Regular paragraph chunking
                # Prepend section heading for context
                prefix = f"Section: {current_section}\n\n" if current_section else ""
                
                # Split if paragraph is too long
                sub_texts = _split_text_recursive(seg_text)
                for sub_text in sub_texts:
                    chunk_text = prefix + sub_text
                    
                    # Detect figure references in chunk
                    has_images = bool(fig_ref_pattern.search(chunk_text))
                    
                    chunk_raw_id = f"{document_id}_{chunk_index}_{chunk_text.strip()}"
                    chunk_id = hashlib.sha256(chunk_raw_id.encode("utf-8")).hexdigest()

                    chunk_metadata = {
                        "document_id": document_id,
                        "filename": document_content.filename,
                        "page_index": page_idx,
                        "chunk_index": chunk_index,
                        "has_tables": False,
                        "has_images": has_images,
                        "character_count": len(chunk_text)
                    }

                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        page_index=page_idx,
                        section=current_section,
                        metadata=chunk_metadata
                    ))
                    chunk_index += 1

        else:
            # 2. Fallback to simple paragraph split if page segments are missing
            paragraphs = page_text.split("\n\n")
            for para in paragraphs:
                para_stripped = para.strip()
                if not para_stripped:
                    continue

                # Skip header/footer line exact matches
                if para_stripped in headers or para_stripped in footers:
                    continue

                # Skip table rows
                if any(t_line in para_stripped for t_line in table_lines_to_skip):
                    continue

                # Detect if this paragraph is actually a section heading
                is_heading = (
                    re.match(r"^\d+(\.\d+)*\s+[A-Z_a-z].*", para_stripped) or
                    re.match(r"^(Section|Chapter|Appendix)\s+[A-Za-z0-9]+.*", para_stripped, re.IGNORECASE) or
                    (re.match(r"^[A-Z0-9\s\-_\(\),.:;']{3,80}$", para_stripped) and not para_stripped.isdigit())
                )
                if is_heading:
                    current_section = para_stripped
                    continue

                prefix = f"Section: {current_section}\n\n" if current_section else ""
                sub_texts = _split_text_recursive(para_stripped)
                for sub_text in sub_texts:
                    chunk_text = prefix + sub_text
                    has_images = bool(fig_ref_pattern.search(chunk_text))

                    chunk_raw_id = f"{document_id}_{chunk_index}_{chunk_text.strip()}"
                    chunk_id = hashlib.sha256(chunk_raw_id.encode("utf-8")).hexdigest()

                    chunk_metadata = {
                        "document_id": document_id,
                        "filename": document_content.filename,
                        "page_index": page_idx,
                        "chunk_index": chunk_index,
                        "has_tables": False,
                        "has_images": has_images,
                        "character_count": len(chunk_text)
                    }

                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        page_index=page_idx,
                        section=current_section,
                        metadata=chunk_metadata
                    ))
                    chunk_index += 1

    return ChunkCollection(
        document_id=document_id,
        chunks=tuple(chunks),
        chunk_count=len(chunks)
    )
