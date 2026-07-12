"""Unit tests for the PDF parser."""

import unittest

import fitz

from parser.pdf_parser import parse_pdf


def make_pdf_bytes(text: str, title: str = "Test Document") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.set_metadata({"title": title, "author": "OmniOps Test"})
    pdf_bytes = document.write()
    document.close()
    return pdf_bytes


class TestPdfParser(unittest.TestCase):
    def test_parse_pdf_returns_document_content(self):
        pdf_bytes = make_pdf_bytes("Hello OmniOps")

        result = parse_pdf(pdf_bytes=pdf_bytes, filename="sample.pdf")

        self.assertEqual(result.filename, "sample.pdf")
        self.assertIn("Hello OmniOps", result.text)
        self.assertEqual(result.page_count, 1)
        self.assertEqual(len(result.pages), 1)
        self.assertEqual(result.metadata.get("title"), "Test Document")
        self.assertEqual(result.metadata.get("author"), "OmniOps Test")

    def test_parse_pdf_preserves_page_text(self):
        document = fitz.open()
        first_page = document.new_page()
        first_page.insert_text((72, 72), "Page 1")
        second_page = document.new_page()
        second_page.insert_text((72, 72), "Page 2")
        pdf_bytes = document.write()
        document.close()

        result = parse_pdf(pdf_bytes=pdf_bytes, filename="multi-page.pdf")

        self.assertEqual(result.page_count, 2)
        self.assertEqual(result.pages[0].strip(), "Page 1")
        self.assertEqual(result.pages[1].strip(), "Page 2")
        self.assertIn("Page 1", result.text)
        self.assertIn("Page 2", result.text)

    def test_parse_pdf_rejects_empty_bytes(self):
        with self.assertRaises(ValueError):
            parse_pdf(pdf_bytes=b"", filename="empty.pdf")

    def test_parse_pdf_rejects_empty_filename(self):
        pdf_bytes = make_pdf_bytes("Content")

        with self.assertRaises(ValueError):
            parse_pdf(pdf_bytes=pdf_bytes, filename="")


if __name__ == "__main__":
    unittest.main()
