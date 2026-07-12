"""Unit tests for encoding normalization."""

import unittest
import unicodedata

from ingestion.models import DocumentContent
from ingestion.normalizer import (
    normalize_encoding,
    _normalize_unicode,
    _remove_control_characters,
    _replace_replacement_character,
)


class TestNormalizeUnicode(unittest.TestCase):
    def test_normalizes_precomposed_accents(self):
        # Decomposed form: é = e + combining acute
        decomposed = "café"  # With combining character
        result = _normalize_unicode(decomposed)
        # Should be in NFC form
        self.assertEqual(result, unicodedata.normalize("NFC", decomposed))

    def test_handles_empty_string(self):
        result = _normalize_unicode("")
        self.assertEqual(result, "")

    def test_preserves_ascii(self):
        text = "Hello World"
        result = _normalize_unicode(text)
        self.assertEqual(result, text)

    def test_normalizes_greek_letters(self):
        # Greek alpha with combining mark
        text = "ά"  # alpha with combining acute
        result = _normalize_unicode(text)
        self.assertEqual(result, unicodedata.normalize("NFC", text))

    def test_handles_emoji(self):
        text = "Hello 👍"
        result = _normalize_unicode(text)
        self.assertEqual(result, text)


class TestRemoveControlCharacters(unittest.TestCase):
    def test_removes_null_character(self):
        text = "hello\x00world"
        result = _remove_control_characters(text)
        self.assertEqual(result, "helloworld")

    def test_preserves_newlines(self):
        text = "line1\nline2"
        result = _remove_control_characters(text)
        self.assertEqual(result, "line1\nline2")

    def test_preserves_tabs(self):
        text = "col1\tcol2"
        result = _remove_control_characters(text)
        self.assertEqual(result, "col1\tcol2")

    def test_preserves_carriage_returns(self):
        text = "line1\r\nline2"
        result = _remove_control_characters(text)
        self.assertEqual(result, "line1\r\nline2")

    def test_removes_bell_character(self):
        text = "hello\x07world"
        result = _remove_control_characters(text)
        self.assertEqual(result, "helloworld")

    def test_removes_escape_character(self):
        text = "hello\x1bworld"
        result = _remove_control_characters(text)
        self.assertEqual(result, "helloworld")

    def test_handles_empty_string(self):
        result = _remove_control_characters("")
        self.assertEqual(result, "")

    def test_preserves_printable_ascii(self):
        text = "Hello World 123!@#"
        result = _remove_control_characters(text)
        self.assertEqual(result, text)

    def test_preserves_unicode_letters(self):
        text = "Hëllö Wørld"
        result = _remove_control_characters(text)
        self.assertEqual(result, text)


class TestReplaceReplacementCharacter(unittest.TestCase):
    def test_replaces_replacement_character_with_space(self):
        text = "hello\ufffdworld"
        result = _replace_replacement_character(text)
        self.assertEqual(result, "hello world")

    def test_preserves_other_characters(self):
        text = "hello world"
        result = _replace_replacement_character(text)
        self.assertEqual(result, "hello world")

    def test_handles_multiple_replacement_characters(self):
        text = "he\ufffdlo\ufffdwo\ufffdrld"
        result = _replace_replacement_character(text)
        self.assertEqual(result, "he lo wo rld")

    def test_handles_empty_string(self):
        result = _replace_replacement_character("")
        self.assertEqual(result, "")


class TestNormalizeEncodingDocument(unittest.TestCase):
    def test_normalizes_document_encoding(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="Hello\x00World",
            pages=("Page\x001",),
            page_count=1,
            metadata={},
        )

        result = normalize_encoding(doc)

        self.assertEqual(result.text, "HelloWorld")
        self.assertEqual(result.pages, ("Page1",))

    def test_enriches_metadata_with_encoding_info(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="test",
            pages=("test",),
            page_count=1,
            metadata={"title": "Test"},
        )

        result = normalize_encoding(doc)

        self.assertTrue(result.metadata["encoding_normalized"])
        self.assertEqual(result.metadata["unicode_form"], "NFC")
        self.assertEqual(result.metadata["title"], "Test")

    def test_preserves_filename(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="test",
            pages=("test",),
            page_count=1,
            metadata={},
        )

        result = normalize_encoding(doc)
        self.assertEqual(result.filename, "test.pdf")

    def test_preserves_page_count(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="test",
            pages=("p1", "p2", "p3"),
            page_count=3,
            metadata={},
        )

        result = normalize_encoding(doc)
        self.assertEqual(result.page_count, 3)

    def test_normalizes_multiple_pages(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="Page\x001\nPage\x002",
            pages=("Page\x001", "Page\x002"),
            page_count=2,
            metadata={},
        )

        result = normalize_encoding(doc)

        self.assertEqual(result.pages[0], "Page1")
        self.assertEqual(result.pages[1], "Page2")

    def test_handles_document_with_accents(self):
        # Decomposed form
        doc = DocumentContent(
            filename="test.pdf",
            text="café",
            pages=("café",),
            page_count=1,
            metadata={},
        )

        result = normalize_encoding(doc)

        # Should be in NFC form
        self.assertEqual(result.text, unicodedata.normalize("NFC", "café"))

    def test_preserves_newlines_and_tabs(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="col1\tcol2\nrow2",
            pages=("header\thead\ndata",),
            page_count=1,
            metadata={},
        )

        result = normalize_encoding(doc)

        self.assertIn("\t", result.text)
        self.assertIn("\n", result.text)
        self.assertIn("\t", result.pages[0])
        self.assertIn("\n", result.pages[0])

    def test_returns_new_document_instance(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="test",
            pages=("test",),
            page_count=1,
            metadata={},
        )

        result = normalize_encoding(doc)

        self.assertIsNot(result, doc)

    def test_frozen_dataclass_preserved(self):
        doc = DocumentContent(
            filename="test.pdf",
            text="test",
            pages=("test",),
            page_count=1,
            metadata={},
        )

        result = normalize_encoding(doc)

        # Result should also be frozen
        with self.assertRaises(AttributeError):
            result.filename = "modified.pdf"  # type: ignore

    def test_handles_document_with_control_and_replacement_chars(self):
        replacement_char = "\ufffd"
        doc = DocumentContent(
            filename="test.pdf",
            text="hello\x00" + replacement_char + "world",
            pages=("page\x00" + replacement_char + "id",),
            page_count=1,
            metadata={},
        )

        result = normalize_encoding(doc)

        # Both control char (removed) and replacement char (replaced with space)
        self.assertNotIn("\x00", result.text)
        self.assertNotIn(replacement_char, result.text)
        self.assertIn("hello", result.text)
        self.assertIn("world", result.text)

    def test_combined_normalization_unicode_and_control(self):
        # Text with both Unicode normalization needs and control chars
        doc = DocumentContent(
            filename="test.pdf",
            text="café\x00naïve",
            pages=("café\x00test",),
            page_count=1,
            metadata={},
        )

        result = normalize_encoding(doc)

        # Control char removed, accents normalized
        self.assertNotIn("\x00", result.text)
        self.assertIn("caf", result.text)
        self.assertIn("naive", result.text.replace("ï", "i"))


if __name__ == "__main__":
    unittest.main()
