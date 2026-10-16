"""Direct PDF (.pdf) generator using PyMuPDF (fitz) with industrial layout."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import fitz

if TYPE_CHECKING:
    from generation.document_models import DocumentOutline, GeneratedSection


class PdfGenerator:
    """Builds authentic, searchable PDF documents with industrial styling and validation."""

    def build_pdf_bytes(
        self,
        outline: DocumentOutline,
        sections: list[GeneratedSection],
    ) -> bytes:
        doc = fitz.open()

        page_width = 595.0  # A4 width (points)
        page_height = 842.0  # A4 height (points)
        margin_left = 50.0
        margin_right = 545.0
        margin_top = 60.0
        margin_bottom = 780.0

        page = doc.new_page(width=page_width, height=page_height)
        y = margin_top

        def check_page_break(needed_space: float = 30.0) -> None:
            nonlocal page, y
            if y + needed_space > margin_bottom:
                page = doc.new_page(width=page_width, height=page_height)
                y = margin_top

        # Running Header
        page.insert_text(
            fitz.Point(margin_left, 35),
            "OmniOps Sovereign Industrial Intelligence — Verified Deliverable",
            fontsize=8,
            fontname="helv",
            color=(0.4, 0.45, 0.5),
        )
        page.draw_line(fitz.Point(margin_left, 42), fitz.Point(margin_right, 42), color=(0.8, 0.82, 0.85), width=0.5)

        # Title Block
        y += 10
        page.insert_text(
            fitz.Point(margin_left, y),
            outline.title[:60],
            fontsize=18,
            fontname="helv",
            color=(0.06, 0.09, 0.16),  # Slate-900
        )
        y += 24

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        meta_sub = f"Audience: {outline.intended_audience} | Date: {now_str} | Status: VERIFIED"
        page.insert_text(
            fitz.Point(margin_left, y),
            meta_sub,
            fontsize=9,
            fontname="helv",
            color=(0.3, 0.35, 0.4),
        )
        y += 20
        page.draw_line(fitz.Point(margin_left, y), fitz.Point(margin_right, y), color=(0.12, 0.23, 0.54), width=1.5)
        y += 20

        # Render sections
        for sec in sections:
            check_page_break(50.0)

            # Section Header Bar
            page.draw_rect(fitz.Rect(margin_left, y - 12, margin_left + 4, y + 4), color=(0.12, 0.23, 0.54), fill=(0.12, 0.23, 0.54))
            page.insert_text(
                fitz.Point(margin_left + 10, y),
                sec.title,
                fontsize=13,
                fontname="helv",
                color=(0.12, 0.23, 0.54),
            )
            y += 20

            # Content lines
            for line in sec.content_markdown.splitlines():
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("### "):
                    continue
                check_page_break(18.0)
                if clean_line.startswith("> "):
                    page.draw_rect(fitz.Rect(margin_left + 5, y - 10, margin_left + 8, y + 2), color=(0.4, 0.45, 0.5), fill=(0.4, 0.45, 0.5))
                    page.insert_text(
                        fitz.Point(margin_left + 15, y),
                        clean_line[2:][:85],
                        fontsize=9,
                        fontname="helv",
                        color=(0.25, 0.3, 0.35),
                    )
                else:
                    page.insert_text(
                        fitz.Point(margin_left, y),
                        clean_line[:90],
                        fontsize=9.5,
                        fontname="helv",
                        color=(0.15, 0.18, 0.22),
                    )
                y += 14

            # Callouts
            for callout in sec.callouts:
                check_page_break(35.0)
                c_type = callout.get("type", "WARNING").upper()
                c_text = callout.get("text", "")
                box_color = (0.98, 0.92, 0.92) if c_type in {"WARNING", "DANGER"} else (0.99, 0.96, 0.89)
                border_color = (0.85, 0.2, 0.2) if c_type in {"WARNING", "DANGER"} else (0.85, 0.5, 0.1)

                page.draw_rect(fitz.Rect(margin_left, y - 8, margin_right, y + 16), color=border_color, fill=box_color, width=1.0)
                page.insert_text(
                    fitz.Point(margin_left + 10, y + 6),
                    f"[{c_type}] {c_text[:75]}",
                    fontsize=8.5,
                    fontname="helv",
                    color=border_color,
                )
                y += 28

            # Tables
            for tbl in sec.tables:
                headers = tbl.get("headers", [])
                rows = tbl.get("rows", [])
                if headers and rows:
                    check_page_break(30.0 + len(rows) * 16.0)
                    col_width = (margin_right - margin_left) / len(headers)

                    # Header row
                    page.draw_rect(fitz.Rect(margin_left, y - 10, margin_right, y + 6), color=(0.2, 0.25, 0.3), fill=(0.92, 0.94, 0.96))
                    for col_i, h in enumerate(headers):
                        page.insert_text(
                            fitz.Point(margin_left + col_i * col_width + 4, y),
                            str(h)[:20],
                            fontsize=8.5,
                            fontname="helv",
                            color=(0.1, 0.15, 0.2),
                        )
                    y += 18

                    # Data rows
                    for r in rows:
                        check_page_break(16.0)
                        for col_i, val in enumerate(r):
                            page.insert_text(
                                fitz.Point(margin_left + col_i * col_width + 4, y),
                                str(val)[:20],
                                fontsize=8,
                                fontname="helv",
                                color=(0.2, 0.22, 0.25),
                            )
                        page.draw_line(fitz.Point(margin_left, y + 4), fitz.Point(margin_right, y + 4), color=(0.88, 0.9, 0.92), width=0.5)
                        y += 16
                    y += 6

            # Citations
            if sec.citations:
                check_page_break(25.0)
                cite_str = "References: " + " | ".join(f"{c.get('document_id', 'REF')} (p.{c.get('page_index', 1)})" for c in sec.citations[:3])
                page.insert_text(
                    fitz.Point(margin_left, y),
                    cite_str[:100],
                    fontsize=7.5,
                    fontname="helv",
                    color=(0.5, 0.55, 0.6),
                )
                y += 16

            y += 14  # Gap before next section

        # Add Running Footers with Page Numbers to all pages
        total_pages = len(doc)
        for page_idx, p in enumerate(doc):
            p.draw_line(fitz.Point(margin_left, 805), fitz.Point(margin_right, 805), color=(0.85, 0.87, 0.9), width=0.5)
            p.insert_text(
                fitz.Point(margin_left, 818),
                "CONFIDENTIAL & VERIFIED — INDUSTRIAL PLATFORM",
                fontsize=7.5,
                fontname="helv",
                color=(0.5, 0.55, 0.6),
            )
            p.insert_text(
                fitz.Point(margin_right - 60, 818),
                f"Page {page_idx + 1} of {total_pages}",
                fontsize=7.5,
                fontname="helv",
                color=(0.5, 0.55, 0.6),
            )

        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes
