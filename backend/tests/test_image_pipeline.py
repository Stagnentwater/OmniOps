"""Unit tests for the Image Ingestion Pipeline (V15-IMG-001).

Tests cover:
- Vision data models (VisualEvidence, BoundingBox)
- DocumentContent backward compatibility
- Image parser routing and logic
- ModelRouter
- VisionProvider (mocked)
- Chat context injection (mocked)

Note: Tests that import modules with heavy transitive dependencies
(parser package, database modules) use sys.modules patching to
avoid requiring those dependencies in the test environment.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch
from dataclasses import FrozenInstanceError

from ingestion.vision_models import VisualEvidence, BoundingBox
from ingestion.models import DocumentContent
from services.model_router import ModelRouter


# ---------------------------------------------------------------------------
# Tests: Vision Data Models
# ---------------------------------------------------------------------------

class TestBoundingBox(unittest.TestCase):
    """Test BoundingBox frozen dataclass."""

    def test_creation(self) -> None:
        bb = BoundingBox(
            label="Pump P-301",
            x=100, y=200, width=50, height=30,
            confidence=0.9,
            entity_type="asset",
        )
        self.assertEqual(bb.label, "Pump P-301")
        self.assertEqual(bb.x, 100)
        self.assertEqual(bb.confidence, 0.9)

    def test_frozen(self) -> None:
        bb = BoundingBox(
            label="V-200", x=0, y=0, width=10, height=10,
            confidence=0.5, entity_type="component",
        )
        with self.assertRaises(FrozenInstanceError):
            bb.label = "changed"  # type: ignore[misc]


class TestVisualEvidence(unittest.TestCase):
    """Test VisualEvidence frozen dataclass."""

    def test_creation_minimal(self) -> None:
        ev = VisualEvidence(
            image_uri="file:///test.jpg",
            source_type="photograph",
            extracted_text="A centrifugal pump.",
            classification="PHOTOGRAPH",
            confidence=0.8,
        )
        self.assertEqual(ev.image_uri, "file:///test.jpg")
        self.assertEqual(ev.bounding_boxes, ())
        self.assertIsNone(ev.parent_page)

    def test_creation_with_bboxes(self) -> None:
        bb = BoundingBox(
            label="P-301", x=10, y=20, width=30, height=40,
            confidence=0.9, entity_type="asset",
        )
        ev = VisualEvidence(
            image_uri="file:///pid.png",
            source_type="pid",
            extracted_text="P&ID with pump P-301",
            classification="PID",
            confidence=0.85,
            bounding_boxes=(bb,),
            parent_page=3,
        )
        self.assertEqual(len(ev.bounding_boxes), 1)
        self.assertEqual(ev.parent_page, 3)

    def test_frozen(self) -> None:
        ev = VisualEvidence(
            image_uri="x", source_type="photograph",
            extracted_text="t", classification="PHOTOGRAPH",
            confidence=0.5,
        )
        with self.assertRaises(FrozenInstanceError):
            ev.confidence = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: DocumentContent backward compatibility
# ---------------------------------------------------------------------------

class TestDocumentContentBackwardCompat(unittest.TestCase):
    """Verify existing parsers still work with the new visual_evidence field."""

    def test_no_visual_evidence_default(self) -> None:
        """Existing code that doesn't pass visual_evidence should still work."""
        doc = DocumentContent(
            filename="test.pdf",
            text="Some text",
            pages=("page 1",),
            page_count=1,
            metadata={"source": "pdf"},
        )
        self.assertEqual(doc.visual_evidence, ())
        self.assertEqual(doc.filename, "test.pdf")

    def test_with_visual_evidence(self) -> None:
        ev = VisualEvidence(
            image_uri="file:///img.png",
            source_type="photograph",
            extracted_text="Equipment photo",
            classification="PHOTOGRAPH",
            confidence=0.8,
        )
        doc = DocumentContent(
            filename="photo.jpg",
            text="Equipment photo",
            pages=("Equipment photo",),
            page_count=1,
            metadata={"source_type": "image"},
            visual_evidence=(ev,),
        )
        self.assertEqual(len(doc.visual_evidence), 1)
        self.assertEqual(doc.visual_evidence[0].classification, "PHOTOGRAPH")


# ---------------------------------------------------------------------------
# Tests: Image Parser (isolated from parser package __init__)
# ---------------------------------------------------------------------------

class TestImageParserHelpers(unittest.TestCase):
    """Test image parser utility functions.

    Uses importlib to load image_parser directly, bypassing the parser
    package __init__.py which eagerly imports docx/pdf parsers.
    """

    @classmethod
    def setUpClass(cls) -> None:
        """Load image_parser module directly to avoid parser __init__.py."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "image_parser_direct",
            "parser/image_parser.py",
        )
        assert spec is not None and spec.loader is not None
        cls._module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls._module)

    def test_is_image_file_true(self) -> None:
        is_image_file = self._module.is_image_file
        self.assertTrue(is_image_file("pump.jpg"))
        self.assertTrue(is_image_file("diagram.PNG"))
        self.assertTrue(is_image_file("scan.tiff"))
        self.assertTrue(is_image_file("photo.jpeg"))
        self.assertTrue(is_image_file("test.tif"))

    def test_is_image_file_false(self) -> None:
        is_image_file = self._module.is_image_file
        self.assertFalse(is_image_file("document.pdf"))
        self.assertFalse(is_image_file("data.csv"))
        self.assertFalse(is_image_file("report.docx"))
        self.assertFalse(is_image_file("noextension"))

    def test_build_prompt_photograph(self) -> None:
        prompt = self._module._build_prompt("PHOTOGRAPH")
        self.assertIn("equipment", prompt.lower())
        self.assertIn("manufacturer", prompt.lower())

    def test_build_prompt_pid(self) -> None:
        prompt = self._module._build_prompt("PID")
        self.assertIn("p&id", prompt.lower())
        self.assertIn("equipment", prompt.lower())

    def test_build_prompt_scanned(self) -> None:
        prompt = self._module._build_prompt("SCANNED_DOCUMENT")
        self.assertIn("ocr", prompt.lower())

    def test_build_prompt_diagram(self) -> None:
        prompt = self._module._build_prompt("DIAGRAM")
        self.assertIn("diagram", prompt.lower())

    def test_build_prompt_screenshot(self) -> None:
        prompt = self._module._build_prompt("SCREENSHOT")
        self.assertIn("screenshot", prompt.lower())


class TestImageParserIntegration(unittest.TestCase):
    """Test parse_image with mocked VisionProvider.

    Uses importlib to load directly, bypassing parser __init__.py.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "image_parser_direct",
            "parser/image_parser.py",
        )
        assert spec is not None and spec.loader is not None
        cls._module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls._module)

    def test_parse_image_produces_document_content(self) -> None:
        from generation.vision_provider import VisionProvider, VisionResult

        mock_provider = MagicMock(spec=VisionProvider)
        mock_provider.classify_image.return_value = "PHOTOGRAPH"
        mock_provider.describe_image.return_value = VisionResult(
            text="A Grundfos centrifugal pump model CR-45",
            model="gemma3:4b",
            total_duration_ns=15_000_000_000,
            eval_count=42,
        )

        # Minimal bytes — we use a mock so actual image content doesn't matter
        fake_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100

        doc = self._module.parse_image(
            image_bytes=fake_bytes,
            filename="pump_photo.jpg",
            vision_provider=mock_provider,
            max_resolution=2048,
            storage_uri="file:///data/storage/pump_photo.jpg",
        )

        # Verify DocumentContent structure
        self.assertEqual(doc.filename, "pump_photo.jpg")
        self.assertIn("Grundfos", doc.text)
        self.assertEqual(doc.page_count, 1)
        self.assertEqual(doc.metadata["source_type"], "image")
        self.assertEqual(doc.metadata["image_classification"], "PHOTOGRAPH")

        # Verify VisualEvidence
        self.assertEqual(len(doc.visual_evidence), 1)
        ev = doc.visual_evidence[0]
        self.assertEqual(ev.classification, "PHOTOGRAPH")
        self.assertEqual(ev.source_type, "photograph")
        self.assertIn("Grundfos", ev.extracted_text)
        self.assertEqual(ev.image_uri, "file:///data/storage/pump_photo.jpg")

        # Verify VisionProvider was called correctly
        mock_provider.classify_image.assert_called_once()
        mock_provider.describe_image.assert_called_once()

    def test_parse_image_empty_response(self) -> None:
        from generation.vision_provider import VisionProvider, VisionResult

        mock_provider = MagicMock(spec=VisionProvider)
        mock_provider.classify_image.return_value = "DIAGRAM"
        mock_provider.describe_image.return_value = VisionResult(
            text="",
            model="gemma3:4b",
            total_duration_ns=5_000_000_000,
            eval_count=0,
        )

        doc = self._module.parse_image(
            image_bytes=b"\x00" * 50,
            filename="empty.png",
            vision_provider=mock_provider,
        )

        # Should have fallback text
        self.assertIn("empty.png", doc.text)
        self.assertEqual(doc.metadata["image_classification"], "DIAGRAM")


# ---------------------------------------------------------------------------
# Tests: ModelRouter
# ---------------------------------------------------------------------------

class TestModelRouter(unittest.TestCase):
    """Test automatic model routing."""

    def setUp(self) -> None:
        self.router = ModelRouter(
            reasoning_model="llama3.2",
            vision_model="gemma3:4b",
        )

    def test_route_image_file(self) -> None:
        result = self.router.route_file("pump.jpg")
        self.assertEqual(result["pipeline"], "image")
        self.assertEqual(result["model"], "gemma3:4b")
        self.assertEqual(result["parser"], "image_parser")

    def test_route_png_file(self) -> None:
        result = self.router.route_file("diagram.png")
        self.assertEqual(result["pipeline"], "image")
        self.assertEqual(result["model"], "gemma3:4b")

    def test_route_tiff_file(self) -> None:
        result = self.router.route_file("scan.tiff")
        self.assertEqual(result["pipeline"], "image")

    def test_route_pdf_file(self) -> None:
        result = self.router.route_file("report.pdf")
        self.assertEqual(result["pipeline"], "document")
        self.assertEqual(result["model"], "llama3.2")
        self.assertEqual(result["parser"], "pdf_parser")

    def test_route_docx_file(self) -> None:
        result = self.router.route_file("manual.docx")
        self.assertEqual(result["pipeline"], "document")
        self.assertEqual(result["parser"], "docx_parser")

    def test_route_csv_file(self) -> None:
        result = self.router.route_file("data.csv")
        self.assertEqual(result["parser"], "csv_parser")

    def test_route_excel_file(self) -> None:
        result = self.router.route_file("data.xlsx")
        self.assertEqual(result["parser"], "excel_parser")

    def test_route_unknown_file(self) -> None:
        result = self.router.route_file("readme.txt")
        self.assertEqual(result["pipeline"], "unknown")

    def test_route_text_query(self) -> None:
        result = self.router.route_query(has_image=False)
        self.assertEqual(result["pipeline"], "text_query")
        self.assertEqual(result["model"], "llama3.2")

    def test_route_image_query(self) -> None:
        result = self.router.route_query(has_image=True)
        self.assertEqual(result["pipeline"], "vision_query")
        self.assertEqual(result["model"], "gemma3:4b")

    def test_select_model_vision_tasks(self) -> None:
        self.assertEqual(self.router.select_model("image_classify"), "gemma3:4b")
        self.assertEqual(self.router.select_model("image_vision"), "gemma3:4b")
        self.assertEqual(self.router.select_model("pid_verify"), "gemma3:4b")

    def test_select_model_text_tasks(self) -> None:
        self.assertEqual(self.router.select_model("text_query"), "llama3.2")
        self.assertEqual(self.router.select_model("reasoning"), "llama3.2")
        self.assertEqual(self.router.select_model("generation"), "llama3.2")

    def test_select_model_unknown_defaults_to_reasoning(self) -> None:
        self.assertEqual(self.router.select_model("unknown_task"), "llama3.2")


# ---------------------------------------------------------------------------
# Tests: VisionProvider
# ---------------------------------------------------------------------------

class TestVisionProviderClassification(unittest.TestCase):
    """Test VisionProvider.classify_image with mocked HTTP calls."""

    @patch("generation.vision_provider.urllib.request.urlopen")
    def test_classify_returns_valid_label(self, mock_urlopen) -> None:
        import json
        from generation.vision_provider import VisionProvider

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "PHOTOGRAPH"},
            "model": "gemma3:4b",
            "total_duration": 1000,
            "eval_count": 5,
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = VisionProvider(model="gemma3:4b")
        label = provider.classify_image(b"\x00" * 10)
        self.assertEqual(label, "PHOTOGRAPH")

    @patch("generation.vision_provider.urllib.request.urlopen")
    def test_classify_pid_label(self, mock_urlopen) -> None:
        import json
        from generation.vision_provider import VisionProvider

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "PID"},
            "model": "gemma3:4b",
            "total_duration": 1000,
            "eval_count": 3,
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = VisionProvider(model="gemma3:4b")
        label = provider.classify_image(b"\x00" * 10)
        self.assertEqual(label, "PID")

    @patch("generation.vision_provider.urllib.request.urlopen")
    def test_classify_unknown_defaults_to_photograph(self, mock_urlopen) -> None:
        import json
        from generation.vision_provider import VisionProvider

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "SOMETHING WEIRD"},
            "model": "gemma3:4b",
            "total_duration": 1000,
            "eval_count": 3,
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = VisionProvider(model="gemma3:4b")
        label = provider.classify_image(b"\x00" * 10)
        self.assertEqual(label, "PHOTOGRAPH")

    @patch("generation.vision_provider.urllib.request.urlopen")
    def test_describe_image_returns_vision_result(self, mock_urlopen) -> None:
        import json
        from generation.vision_provider import VisionProvider

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "This is a pump with serial ABC-123"},
            "model": "gemma3:4b",
            "total_duration": 20000000000,
            "eval_count": 30,
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = VisionProvider(model="gemma3:4b")
        result = provider.describe_image(b"\x00" * 10, prompt="Describe this image")
        self.assertIn("pump", result.text)
        self.assertEqual(result.model, "gemma3:4b")
        self.assertEqual(result.eval_count, 30)


# ---------------------------------------------------------------------------
# Tests: Chat Context Injection (with mocked psycopg)
# ---------------------------------------------------------------------------

class TestImageChatService(unittest.TestCase):
    """Test chat context injection with mocked database dependency."""

    def _get_inject_fn(self):
        """Import inject_image_context with mocked psycopg."""
        # Mock psycopg if not available
        if "psycopg" not in sys.modules:
            sys.modules["psycopg"] = MagicMock()
            sys.modules["psycopg.rows"] = MagicMock()
        from services.image_chat_service import inject_image_context
        return inject_image_context

    def test_inject_with_session(self) -> None:
        inject_image_context = self._get_inject_fn()

        mock_repo = MagicMock()
        mock_repo.add_message.return_value = "msg-123"

        result = inject_image_context(
            session_id="session-abc",
            filename="pump.jpg",
            classification="PHOTOGRAPH",
            extracted_text="A centrifugal pump",
            image_uri="file:///pump.jpg",
            chat_repository=mock_repo,
        )

        self.assertEqual(result, "msg-123")
        mock_repo.add_message.assert_called_once()

        # Verify the message content
        call_kwargs = mock_repo.add_message.call_args
        self.assertEqual(call_kwargs.kwargs["session_id"], "session-abc")
        self.assertEqual(call_kwargs.kwargs["role"], "system")
        self.assertIn("Image Analysis: pump.jpg", call_kwargs.kwargs["content"])
        self.assertIn("centrifugal pump", call_kwargs.kwargs["content"])
        self.assertIn("PHOTOGRAPH", call_kwargs.kwargs["content"])

    def test_inject_without_session(self) -> None:
        inject_image_context = self._get_inject_fn()

        result = inject_image_context(
            session_id="",
            filename="pump.jpg",
            classification="PHOTOGRAPH",
            extracted_text="A pump",
            image_uri="file:///pump.jpg",
        )

        self.assertIsNone(result)

    def test_inject_handles_repo_error(self) -> None:
        inject_image_context = self._get_inject_fn()

        mock_repo = MagicMock()
        mock_repo.add_message.side_effect = Exception("DB error")

        result = inject_image_context(
            session_id="session-abc",
            filename="pump.jpg",
            classification="PHOTOGRAPH",
            extracted_text="A pump",
            image_uri="file:///pump.jpg",
            chat_repository=mock_repo,
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

