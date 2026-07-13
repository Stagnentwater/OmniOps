"""Unit tests for chunking service in ingestion/chunker.py."""

import unittest

from ingestion.models import DocumentContent
from ingestion.chunk_models import Chunk, ChunkCollection
from ingestion.chunker import chunk_document, _split_text_recursive


class TestChunker(unittest.TestCase):
    def test_recursive_splitter_with_overlap(self):
        # A long string with sentence boundaries
        text = "This is sentence one. " * 50  # ~1100 chars
        chunks = _split_text_recursive(text, max_chars=400, overlap_chars=50)
        
        self.assertTrue(len(chunks) > 1)
        for chunk in chunks:
            self.assertTrue(len(chunk) <= 400)
            
        # Verify overlap contains some text from previous chunk
        self.assertIn("This is sentence one.", chunks[1])

    def test_basic_chunking_with_heading_prepending(self):
        doc = DocumentContent(
            filename="manual.pdf",
            text="",
            pages=(
                "Header Line\n1.0 System Overview\nThis is paragraph one.\nFooter Line",
            ),
            page_count=1,
            metadata={
                "headers": ["Header Line"],
                "footers": ["Footer Line"],
                "sections": ["1.0 System Overview"],
                "page_segments": [
                    [
                        {"type": "header", "text": "Header Line"},
                        {"type": "heading", "text": "1.0 System Overview"},
                        {"type": "paragraph", "text": "This is paragraph one."},
                        {"type": "footer", "text": "Footer Line"},
                    ]
                ]
            },
        )
        
        collection = chunk_document(doc, "doc-123")
        self.assertIsInstance(collection, ChunkCollection)
        self.assertEqual(collection.document_id, "doc-123")
        self.assertEqual(collection.chunk_count, 1)
        
        chunk = collection.chunks[0]
        self.assertEqual(chunk.page_index, 0)
        self.assertEqual(chunk.chunk_index, 0)
        self.assertEqual(chunk.section, "1.0 System Overview")
        self.assertIn("Section: 1.0 System Overview", chunk.text)
        self.assertIn("This is paragraph one.", chunk.text)
        self.assertFalse(chunk.metadata["has_tables"])

    def test_table_preservation_and_formatting(self):
        doc = DocumentContent(
            filename="report.docx",
            text="Intro paragraph.\nCol 1 | Col 2\nVal 1 | Val 2\nVal 3 | Val 4\nOutro paragraph.",
            pages=(
                "Intro paragraph.",
                "Col 1 | Col 2\nVal 1 | Val 2\nVal 3 | Val 4",
                "Outro paragraph."
            ),
            page_count=3,
            metadata={
                "extracted_tables": [
                    {
                        "type": "pipe_delimited",
                        "headers": ["Col 1", "Col 2"],
                        "rows": [["Val 1", "Val 2"], ["Val 3", "Val 4"]]
                    }
                ],
                "page_segments": [
                    [{"type": "paragraph", "text": "Intro paragraph."}],
                    [{"type": "paragraph", "text": "Col 1 | Col 2\nVal 1 | Val 2\nVal 3 | Val 4"}],
                    [{"type": "paragraph", "text": "Outro paragraph."}]
                ]
            },
        )

        collection = chunk_document(doc, "doc-456")
        # Should have table chunk first, then intro paragraph chunk, then outro paragraph chunk
        # Total chunk count should be 3 (1 table + 2 paragraph chunks)
        # Note: table cells in second paragraph block should be skipped to prevent duplication
        self.assertEqual(collection.chunk_count, 3)

        # Check table chunk
        table_chunk = collection.chunks[0]
        self.assertEqual(table_chunk.section, "Tables")
        self.assertTrue(table_chunk.metadata["has_tables"])
        self.assertIn("| Col 1 | Col 2 |", table_chunk.text)
        self.assertIn("| Val 1 | Val 2 |", table_chunk.text)

        # Check paragraph chunks
        intro_chunk = collection.chunks[1]
        self.assertIn("Intro paragraph.", intro_chunk.text)
        self.assertFalse(intro_chunk.metadata["has_tables"])

        outro_chunk = collection.chunks[2]
        self.assertIn("Outro paragraph.", outro_chunk.text)
        self.assertFalse(outro_chunk.metadata["has_tables"])

    def test_figure_image_reference_linking(self):
        doc = DocumentContent(
            filename="manual.pdf",
            text="This is paragraph mentioning Figure 1.\nAnother line with Fig. 2 referenced.",
            pages=(
                "This is paragraph mentioning Figure 1.\nAnother line with Fig. 2 referenced.",
            ),
            page_count=1,
            metadata={
                "extracted_images": [
                    {"id": "Figure 1", "label": "Figure", "number": "1", "caption": "Flow schematic", "page_index": 0},
                    {"id": "Figure 2", "label": "Figure", "number": "2", "caption": "Panel Layout", "page_index": 0}
                ]
            },
        )

        collection = chunk_document(doc, "doc-789")
        self.assertTrue(collection.chunk_count > 0)
        for chunk in collection.chunks:
            self.assertTrue(chunk.metadata["has_images"])

    def test_deterministic_chunk_ids(self):
        doc = DocumentContent(
            filename="manual.pdf",
            text="Heading\nParagraph content.",
            pages=("Heading\nParagraph content.",),
            page_count=1,
            metadata={},
        )

        col1 = chunk_document(doc, "doc-deterministic")
        col2 = chunk_document(doc, "doc-deterministic")

        self.assertEqual(col1.chunk_count, col2.chunk_count)
        for c1, c2 in zip(col1.chunks, col2.chunks):
            self.assertEqual(c1.chunk_id, c2.chunk_id)


if __name__ == "__main__":
    unittest.main()
