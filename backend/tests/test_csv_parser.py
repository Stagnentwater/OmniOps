"""Unit tests for the CSV parser."""

import unittest

from parser.csv_parser import parse_csv


def make_csv_bytes() -> bytes:
    csv_content = """Name,Temperature,Status
Pump A,90,Warning
Pump B,75,Normal
Pump C,110,Critical"""
    return csv_content.encode("utf-8")


def make_single_row_csv() -> bytes:
    csv_content = """Equipment,Location,Interval
Bearing 1,Zone A,5000"""
    return csv_content.encode("utf-8")


class TestCsvParser(unittest.TestCase):
    def test_parse_csv_converts_rows_to_readable_format(self):
        csv_bytes = make_csv_bytes()

        result = parse_csv(csv_bytes=csv_bytes, filename="equipment.csv")

        self.assertEqual(result.filename, "equipment.csv")
        self.assertEqual(result.page_count, 3)
        self.assertEqual(len(result.pages), 3)
        
        # Verify first row is human-readable
        self.assertIn("Name: Pump A", result.pages[0])
        self.assertIn("Temperature: 90", result.pages[0])
        self.assertIn("Status: Warning", result.pages[0])
        
        # Verify all rows appear in combined text
        self.assertIn("Pump A", result.text)
        self.assertIn("Pump B", result.text)
        self.assertIn("Pump C", result.text)

    def test_parse_csv_preserves_metadata(self):
        csv_bytes = make_csv_bytes()

        result = parse_csv(csv_bytes=csv_bytes, filename="equipment.csv")

        self.assertEqual(result.metadata.get("column_count"), 3)
        self.assertEqual(result.metadata.get("row_count"), 3)
        self.assertEqual(result.metadata.get("column_names"), "Name, Temperature, Status")
        self.assertEqual(result.metadata.get("delimiter"), ",")
        self.assertEqual(result.metadata.get("encoding"), "utf-8")

    def test_parse_csv_handles_single_row(self):
        csv_bytes = make_single_row_csv()

        result = parse_csv(csv_bytes=csv_bytes, filename="single.csv")

        self.assertEqual(result.page_count, 1)
        self.assertEqual(result.metadata.get("row_count"), 1)
        self.assertIn("Bearing 1", result.text)

    def test_parse_csv_rejects_empty_bytes(self):
        with self.assertRaises(ValueError):
            parse_csv(csv_bytes=b"", filename="empty.csv")

    def test_parse_csv_rejects_empty_filename(self):
        csv_bytes = make_csv_bytes()

        with self.assertRaises(ValueError):
            parse_csv(csv_bytes=csv_bytes, filename="")

    def test_parse_csv_detects_utf8_encoding(self):
        csv_bytes = "Asset,Value\nPump,100".encode("utf-8")

        result = parse_csv(csv_bytes=csv_bytes, filename="test.csv")

        self.assertEqual(result.metadata.get("encoding"), "utf-8")


if __name__ == "__main__":
    unittest.main()
