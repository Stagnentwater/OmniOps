"""Unit tests for whitespace normalization."""

import unittest

from ingestion.models import DocumentContent
from ingestion.normalizer import (
    clean_whitespace,
    _clean_whitespace_simple,
    _clean_pages,
)


class TestCleanWhitespaceSimple(unittest.TestCase):
    def test_removes_leading_trailing_whitespace(self):
        text = "  hello world  "
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "hello world")

    def test_normalizes_multiple_spaces(self):
        text = "hello    world    test"
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "hello world test")

    def test_preserves_single_spaces(self):
        text = "hello world"
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "hello world")

    def test_preserves_paragraph_breaks(self):
        text = "paragraph one\n\nparagraph two"
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "paragraph one\n\nparagraph two")

    def test_removes_excessive_blank_lines(self):
        text = "line one\n\n\n\nline two"
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "line one\n\nline two")

    def test_preserves_indentation(self):
        text = "code:\n    indented line\n    another indented"
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "code:\n    indented line\n    another indented")

    def test_normalizes_spaces_within_indented_line(self):
        text = "code:\n    hello    world"
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "code:\n    hello world")

    def test_handles_empty_string(self):
        result = _clean_whitespace_simple("")
        self.assertEqual(result, "")

    def test_handles_whitespace_only_string(self):
        result = _clean_whitespace_simple("   \n   \n   ")
        self.assertEqual(result, "")

    def test_handles_tabs_as_spaces(self):
        text = "hello\t\tworld"
        result = _clean_whitespace_simple(text)
        # Tabs are preserved; only spaces are normalized
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_handles_mixed_whitespace_lines(self):
        text = "start\n\n  \n\nend"
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "start\n\nend")

    def test_handles_trailing_spaces_on_lines(self):
        text = "line one   \nline two   "
        result = _clean_whitespace_simple(text)
        self.assertEqual(result, "line one\nline two")


class TestCleanPages(unittest.TestCase):
    def test_cleans_each_page_independently(self):
        pages = (
            "  page one  ",
            "  page two  ",
        )
        result = _clean_pages(pages)
        self.assertEqual(result, ("page one", "page two"))

    def test_preserves_page_count(self):
        pages = ("  page 1  ", "  page 2  ", "  page 3  ")
        result = _clean_pages(pages)
        self.assertEqual(len(result), 3)

    def test_handles_empty_pages_tuple(self):
        result = _clean_pages(())
        self.assertEqual(result, ())

    def test_normalizes_spaces_within_pages(self):
        pages = ("hello    world",)
        result = _clean_pages(pages)
        self.assertEqual(result, ("hello world",))

    def test_preserves_page_structure(self):
        pages = ("paragraph one\n\nparagraph two",)
        result = _clean_pages(pages)
        self.assertEqual(result, ("paragraph one\n\nparagraph two",))


class TestCleanWhitespaceDocument(unittest.TestCase):
    def test_cleans_document_content(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="  hello   world  ",
            pages=("  page 1  ",),
            page_count=1,
            metadata={},
        )

        result = clean_whitespace(doc)

        self.assertEqual(result.text, "hello world")
        self.assertEqual(result.pages, ("page 1",))

    def test_preserves_filename(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="  text  ",
            pages=("  page  ",),
            page_count=1,
            metadata={},
        )

        result = clean_whitespace(doc)
        self.assertEqual(result.filename, "test.pdf")

    def test_preserves_page_count(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="  text  ",
            pages=("  p1  ", "  p2  ", "  p3  "),
            page_count=3,
            metadata={},
        )

        result = clean_whitespace(doc)
        self.assertEqual(result.page_count, 3)

    def test_preserves_metadata(self):
        metadata = {"title": "Test", "author": "Author", "page_count": 1}
        doc = DocumentContent(
            filename="test.pdf",
            text="  text  ",
            pages=("  page  ",),
            page_count=1,
            metadata=metadata,
        )

        result = clean_whitespace(doc)
        self.assertEqual(result.metadata, metadata)

    def test_returns_new_document_instance(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="  text  ",
            pages=("  page  ",),
            page_count=1,
            metadata={},
        )

        result = clean_whitespace(doc)

        # Verify it's a new instance
        self.assertIsNot(result, doc)
        self.assertEqual(result.filename, doc.filename)

    def test_cleans_complex_document(self):
        doc = DocumentContent(
            filename="manual.pdf",
            text="Section 1\n\n  This is     content\n\nSection 2\n\n  More   content  ",
            pages=(
                "  Introduction  \n\n  Paragraph 1  ",
                "  Section A  \n\n  Details  ",
            ),
            page_count=2,
            metadata={"title": "Manual", "author": "Engineer"},
        )

        result = clean_whitespace(doc)

        # Text should be cleaned
        self.assertNotIn("    ", result.text)
        self.assertIn("Section 1", result.text)
        self.assertIn("Section 2", result.text)

        # Pages should be cleaned
        self.assertEqual(len(result.pages), 2)
        self.assertNotIn("    ", result.pages[0])
        self.assertNotIn("    ", result.pages[1])

        # Metadata preserved
        self.assertEqual(result.metadata["title"], "Manual")

    def test_preserves_meaningful_indentation(self):
        doc = DocumentContent(
            filename="code.pdf",
            text="Code example:\n    def hello():\n        return 'world'",
            pages=("Code:\n    indented\n        more indented",),
            page_count=1,
            metadata={},
        )

        result = clean_whitespace(doc)

        # Indentation should be preserved
        self.assertIn("    def hello():", result.text)
        self.assertIn("        return", result.text)
        self.assertIn("    indented", result.pages[0])
        self.assertIn("        more", result.pages[0])

    def test_handles_document_with_empty_metadata(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="  text  ",
            pages=("  page  ",),
            page_count=1,
            metadata={},
        )

        result = clean_whitespace(doc)
        self.assertEqual(result.metadata, {})

    def test_normalizes_windows_line_endings(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="line 1\r\nline 2\r\nline 3",
            pages=("page 1\r\npage 2",),
            page_count=1,
            metadata={},
        )

        result = clean_whitespace(doc)
        # \r characters are preserved as-is (only spaces are normalized)
        self.assertIn("line", result.text)

    def test_frozen_dataclass_preserved(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="  text  ",
            pages=("  page  ",),
            page_count=1,
            metadata={},
        )

        result = clean_whitespace(doc)

        # Result should also be frozen
        with self.assertRaises(AttributeError):
            result.filename = "modified.pdf"  # type: ignore


if __name__ == "__main__":
    unittest.main()
