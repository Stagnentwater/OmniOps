"""Unit tests for chat query image processing and attachment handling."""

from __future__ import annotations

import base64
import unittest
from unittest.mock import MagicMock, patch

from api.routes.query import QueryRequest, _process_attached_image


class TestImageChatQuery(unittest.TestCase):
    """Test image attachment decoding, storage, and metadata persistence."""

    def test_query_request_model_with_image(self) -> None:
        """Verify QueryRequest accepts image_base64 and image_filename."""
        req = QueryRequest(
            query="Inspect this pump",
            session_id="session-123",
            image_base64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            image_filename="pump.png",
        )
        self.assertEqual(req.query, "Inspect this pump")
        self.assertEqual(req.image_filename, "pump.png")
        self.assertTrue(req.image_base64.startswith("data:image/png;base64,"))

    @patch("storage.factory.get_storage_service")
    @patch("database.repositories.MetadataRepository")
    def test_process_attached_image(self, mock_meta_repo_cls, mock_get_storage) -> None:
        """Verify _process_attached_image decodes, stores via StorageService, and returns metadata."""
        mock_storage = MagicMock()
        mock_stored = MagicMock()
        mock_stored.storage_key = "documents/test_id/sample.png"
        mock_storage.put_bytes.return_value = mock_stored
        mock_get_storage.return_value = mock_storage

        mock_meta_repo = MagicMock()
        mock_meta_repo_cls.return_value = mock_meta_repo

        # 1x1 transparent PNG base64
        fake_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        doc_id, local_path, storage_url = _process_attached_image(fake_b64, "sample.png")

        self.assertTrue(len(doc_id) > 10)
        self.assertEqual(storage_url, f"/documents/{doc_id}/content")
        self.assertTrue(local_path.endswith("sample.png"))

        mock_storage.put_bytes.assert_called_once()
        mock_meta_repo.save_document_metadata.assert_called_once()


if __name__ == "__main__":
    unittest.main()
