"""Unit tests for DocumentGenerator and outline-first multi-step workflow (V4 Feature C)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from generation.document_models import (
    DocumentOutline,
    OutlineSection,
)
from generation.document_generator import DocumentGenerator


class TestDocumentGenerator(unittest.TestCase):
    """Test suite for outline drafting, section generation, and artifact assembly."""

    def setUp(self) -> None:
        self.generator = DocumentGenerator()

    def test_draft_outline_docx(self) -> None:
        """Verify drafting a Word outline creates expected hierarchical sections."""
        outline = self.generator.draft_outline(
            topic="Crude Distillation Column C-101 Maintenance",
            deliverable_format="docx",
        )

        self.assertEqual(outline.deliverable_format, "docx")
        self.assertIn("C-101", outline.title)
        self.assertTrue(len(outline.sections) >= 5)

        # Validate outline schema
        errors = outline.validate()
        self.assertEqual(len(errors), 0)

    def test_draft_outline_pptx(self) -> None:
        """Verify drafting a PowerPoint outline creates slide-based sections."""
        outline = self.generator.draft_outline(
            topic="Refinery Turnaround Q4 Overview",
            deliverable_format="pptx",
        )

        self.assertEqual(outline.deliverable_format, "pptx")
        self.assertTrue(len(outline.sections) >= 4)
        errors = outline.validate()
        self.assertEqual(len(errors), 0)

    def test_outline_validation_rejects_empty(self) -> None:
        """Verify outline validation rejects empty title or sections."""
        invalid_outline = DocumentOutline(
            title="",
            deliverable_format="docx",
            sections=[],
        )
        errors = invalid_outline.validate()
        self.assertTrue(len(errors) >= 2)
        self.assertIn("Document title is required.", errors)
        self.assertIn("Outline must contain at least one section.", errors)

    def test_generate_section_with_tables_and_callouts(self) -> None:
        """Verify section generation formats tables and safety callouts."""
        sec_outline = OutlineSection(
            title="3. Operating Parameters & Isolation Limits",
            level=1,
            description="Operational pressure and temperature limits",
            required_elements=["table:operating_limits", "callout:warning"],
        )

        mock_chunk = MagicMock()
        mock_chunk.text = "Column C-101 top pressure operates at 1.8 bar gauge, top temperature 360 C."
        mock_chunk.document_id = "SOP-C101.pdf"
        mock_chunk.page_index = 8

        generated = self.generator.generate_section(sec_outline, context_chunks=[mock_chunk])

        self.assertEqual(generated.title, sec_outline.title)
        self.assertTrue(len(generated.tables) >= 1)
        self.assertEqual(generated.tables[0]["headers"][0], "Parameter / Asset Tag")
        self.assertTrue(len(generated.callouts) >= 1)
        self.assertEqual(generated.callouts[0]["type"], "WARNING")
        self.assertEqual(len(generated.citations), 1)
        self.assertEqual(generated.verification_status, "VERIFIED")

    def test_assemble_document_docx(self) -> None:
        """Verify assembling a Word document produces a valid stored artifact."""
        outline = self.generator.draft_outline("Heat Exchanger Overhaul", deliverable_format="docx")
        sections = [self.generator.generate_section(s) for s in outline.sections]

        mock_storage = MagicMock()
        mock_stored_obj = MagicMock()
        mock_stored_obj.storage_key = "test_key.docx"
        mock_storage.put_bytes.return_value = mock_stored_obj

        mock_repo = MagicMock()

        artifact = self.generator.assemble_document(
            outline=outline,
            sections=sections,
            storage_service=mock_storage,
            metadata_repo=mock_repo,
        )

        self.assertIsNotNone(artifact.artifact_id)
        self.assertEqual(artifact.deliverable_format, "docx")
        self.assertTrue(artifact.file_size_bytes > 0)
        self.assertIn("/documents/", artifact.download_url)
        mock_storage.put_bytes.assert_called_once()
        mock_repo.save_document_metadata.assert_called_once()


if __name__ == "__main__":
    unittest.main()
