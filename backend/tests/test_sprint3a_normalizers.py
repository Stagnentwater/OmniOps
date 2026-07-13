"""Unit tests for Sprint 3A normalizers: Page Segmentation, Table Extraction, and Image Extraction."""

import unittest

from ingestion.models import DocumentContent
from ingestion.normalizer import (
    segment_pages,
    extract_tables,
    extract_images,
)


class TestPageSegmentation(unittest.TestCase):
    def test_detects_headers_and_footers_multi_page(self):
        doc = DocumentContent(
            filename="multi_page.pdf",
            text="Header Title\nContent 1\nFooter Msg\nHeader Title\nContent 2\nFooter Msg",
            pages=(
                "Header Title\nLine 1\nFooter Msg",
                "Header Title\nLine 2\nFooter Msg",
            ),
            page_count=2,
            metadata={},
        )
        result = segment_pages(doc)
        self.assertIn("Header Title", result.metadata["headers"])
        self.assertIn("Footer Msg", result.metadata["footers"])
        self.assertTrue(result.metadata["page_segmentation_completed"])

    def test_classifies_headings_and_paragraphs(self):
        doc = DocumentContent(
            filename="doc.pdf",
            text="",
            pages=(
                "1.0 Introduction\nThis is the intro.\n\nSection A: Detail\nSome detail here.\n\nALL CAPS HEADING\nNormal text line.",
            ),
            page_count=1,
            metadata={},
        )
        result = segment_pages(doc)
        self.assertIn("1.0 Introduction", result.metadata["sections"])
        self.assertIn("Section A: Detail", result.metadata["sections"])
        self.assertIn("ALL CAPS HEADING", result.metadata["sections"])

        # Check page segments classification
        segments = result.metadata["page_segments"][0]
        heading_texts = [s["text"] for s in segments if s["type"] == "heading"]
        para_texts = [s["text"] for s in segments if s["type"] == "paragraph"]

        self.assertIn("1.0 Introduction", heading_texts)
        self.assertIn("This is the intro.", para_texts)
        self.assertIn("Section A: Detail", heading_texts)
        self.assertIn("ALL CAPS HEADING", heading_texts)
        self.assertIn("Normal text line.", para_texts)

    def test_handles_single_page_without_header_footer_frequency(self):
        doc = DocumentContent(
            filename="single_page.pdf",
            text="Intro text",
            pages=("Intro text",),
            page_count=1,
            metadata={},
        )
        result = segment_pages(doc)
        self.assertEqual(result.metadata["headers"], [])
        self.assertEqual(result.metadata["footers"], [])


class TestTableExtraction(unittest.TestCase):
    def test_reconstructs_csv_tables(self):
        doc = DocumentContent(
            filename="data.csv",
            text="Asset: Pump P301\nStatus: Online\nAsset: Boiler B2\nStatus: Offline",
            pages=(
                "Asset: Pump P301\nStatus: Online",
                "Asset: Boiler B2\nStatus: Offline",
            ),
            page_count=2,
            metadata={"delimiter": ","},
        )
        result = extract_tables(doc)
        self.assertTrue(result.metadata["has_tables"])
        tables = result.metadata["extracted_tables"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["type"], "csv_reconstructed")
        self.assertEqual(tables[0]["headers"], ["Asset", "Status"])
        self.assertEqual(tables[0]["rows"], [["Pump P301", "Online"], ["Boiler B2", "Offline"]])

    def test_extracts_docx_pipe_delimited_tables(self):
        doc = DocumentContent(
            filename="doc.docx",
            text="Intro paragraphs\n\nPump ID | Location | Status\nP301 | Area A | Active\nP302 | Area B | Maintenance\n\nOutro paragraph",
            pages=("Intro paragraphs", "Pump ID | Location | Status\nP301 | Area A | Active\nP302 | Area B | Maintenance", "Outro paragraph"),
            page_count=3,
            metadata={},
        )
        result = extract_tables(doc)
        self.assertTrue(result.metadata["has_tables"])
        tables = result.metadata["extracted_tables"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["type"], "pipe_delimited")
        self.assertEqual(tables[0]["headers"], ["Pump ID", "Location", "Status"])
        self.assertEqual(tables[0]["rows"], [["P301", "Area A", "Active"], ["P302", "Area B", "Maintenance"]])

    def test_extracts_pdf_space_aligned_tables(self):
        doc = DocumentContent(
            filename="doc.pdf",
            text="Some PDF text.\n\nComponent      Status      Pressure\nPump P301      Online      12 bar\nBoiler B2      Offline     0 bar\n\nSome trailing text.",
            pages=("Some PDF text.\n\nComponent      Status      Pressure\nPump P301      Online      12 bar\nBoiler B2      Offline     0 bar\n\nSome trailing text.",),
            page_count=1,
            metadata={},
        )
        result = extract_tables(doc)
        self.assertTrue(result.metadata["has_tables"])
        tables = result.metadata["extracted_tables"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["type"], "space_aligned")
        self.assertEqual(tables[0]["headers"], ["Component", "Status", "Pressure"])
        self.assertEqual(tables[0]["rows"], [["Pump P301", "Online", "12 bar"], ["Boiler B2", "Offline", "0 bar"]])

    def test_no_tables_found(self):
        doc = DocumentContent(
            filename="doc.pdf",
            text="Simple document with only regular sentences and no alignment.",
            pages=("Simple document with only regular sentences and no alignment.",),
            page_count=1,
            metadata={},
        )
        result = extract_tables(doc)
        self.assertFalse(result.metadata["has_tables"])
        self.assertEqual(result.metadata["extracted_tables"], [])


class TestImageExtraction(unittest.TestCase):
    def test_extracts_figure_captions(self):
        doc = DocumentContent(
            filename="doc.pdf",
            text="",
            pages=(
                "Figure 1: System Diagram\nSome text.\nFig. 2 - Flow schematic\nMore text.\nImage 3. Panel layout",
            ),
            page_count=1,
            metadata={},
        )
        result = extract_images(doc)
        self.assertTrue(result.metadata["has_images"])
        images = result.metadata["extracted_images"]
        self.assertEqual(len(images), 3)

        self.assertEqual(images[0]["id"], "Figure 1")
        self.assertEqual(images[0]["caption"], "System Diagram")

        self.assertEqual(images[1]["id"], "Figure 2")
        self.assertEqual(images[1]["caption"], "Flow schematic")

        self.assertEqual(images[2]["id"], "Image 3")
        self.assertEqual(images[2]["caption"], "Panel layout")

    def test_extracts_inline_references(self):
        doc = DocumentContent(
            filename="doc.pdf",
            text="",
            pages=(
                "Check details in Figure 1 and Fig. 2.",
            ),
            page_count=1,
            metadata={},
        )
        result = extract_images(doc)
        self.assertTrue(result.metadata["has_images"])
        images = result.metadata["extracted_images"]
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0]["id"], "Figure 1")
        self.assertEqual(images[0]["caption"], "")
        self.assertEqual(images[1]["id"], "Figure 2")
        self.assertEqual(images[1]["caption"], "")

    def test_captions_overwrite_references(self):
        doc = DocumentContent(
            filename="doc.pdf",
            text="",
            pages=(
                "As seen in Figure 1, the pump is active.\nFigure 1: Schematic flow layout",
            ),
            page_count=1,
            metadata={},
        )
        result = extract_images(doc)
        images = result.metadata["extracted_images"]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["id"], "Figure 1")
        self.assertEqual(images[0]["caption"], "Schematic flow layout")


if __name__ == "__main__":
    unittest.main()
