"""Unit tests for PdfGenerator (.pdf format)."""

from __future__ import annotations

import unittest

import fitz

from generation.document_models import DocumentOutline, GeneratedSection, OutlineSection
from generation.generators.pdf_generator import PdfGenerator


class TestPdfGenerator(unittest.TestCase):
    """Test suite for direct PyMuPDF PDF creation, rendering, and structural validation."""

    def setUp(self) -> None:
        self.generator = PdfGenerator()

    def test_build_pdf_bytes_and_inspect(self) -> None:
        """Verify building PDF returns valid %PDF- bytes readable by PyMuPDF."""
        outline = DocumentOutline(
            title="Industrial Reliability Report: Exchanger E-102",
            deliverable_format="pdf",
            intended_audience="Reliability Engineering",
            sections=[
                OutlineSection(title="1. Equipment History & Vibration"),
                OutlineSection(title="2. Operating Limit Violations"),
            ],
        )

        sections = [
            GeneratedSection(
                section_id="sec-1",
                title="1. Equipment History & Vibration",
                content_markdown="Shell and tube exchanger E-102 inspected for tube bundle fouling.",
                callouts=[{"type": "CAUTION", "text": "Differential pressure elevated across tube side."}],
            ),
            GeneratedSection(
                section_id="sec-2",
                title="2. Operating Limit Violations",
                content_markdown="Verified differential pressure delta_P exceeds baseline.",
                tables=[{
                    "table_name": "operating_limits",
                    "headers": ["Tag", "Parameter", "Limit", "Measured"],
                    "rows": [
                        ["E-102", "Delta P", "0.8 bar", "1.4 bar"],
                        ["E-102", "Outlet Temp", "85 C", "92 C"],
                    ],
                }],
                citations=[{"document_id": "OEM-EXCHANGER.pdf", "page_index": 14}],
            ),
        ]

        pdf_bytes = self.generator.build_pdf_bytes(outline, sections)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

        # Open and inspect with PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        self.assertTrue(len(doc) >= 1)

        # Extract text across all pages
        full_text = "".join(p.get_text() for p in doc)
        self.assertIn("Industrial Reliability Report", full_text)
        self.assertIn("1. Equipment History & Vibration", full_text)
        self.assertIn("E-102", full_text)
        self.assertIn("Delta P", full_text)
        self.assertIn("OEM-EXCHANGER.pdf", full_text)
        self.assertIn("CONFIDENTIAL & VERIFIED", full_text)
        doc.close()


if __name__ == "__main__":
    unittest.main()
