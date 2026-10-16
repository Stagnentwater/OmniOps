"""Comprehensive unit tests for the P&ID 3-Way Check and YOLO localization engine.

Tests:
1. ISA 5.1 refinery standard catalog validation (standard vs non-standard symbols/tags).
2. YOLO symbol detector and PIL-based localized cropping.
3. 3-Way Check decision gates:
   - 3/3 Confirm (Green): All dimensions pass.
   - 2/3 Human Check (Yellow): Non-ISA 5.1 symbol, missing from asset register, or low OCR.
   - 1/3 Reject (Red): Noise / artifact.
4. Integration with AnalyzePIDTool.
5. Operator symbol verification API.
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from PIL import Image

from agents.tools.analyze_pid import AnalyzePIDResult, AnalyzePIDTool
from generation.vision_provider import VisionProvider, VisionResult
from graph.query_service import GraphQueryService
from ingestion.pid.isa_catalog import ISA51Catalog, ISACheckResult
from ingestion.pid.three_way_check import ThreeWayCheckResult, ThreeWayCheckService
from ingestion.pid.yolo_detector import LocalizedSymbol, YOLOSymbolDetector


def _run_async(coro):
    return asyncio.run(coro)


class TestISA51Catalog(unittest.TestCase):
    """Tests for ISA 5.1 refinery compliance checks."""

    def test_standard_equipment_tags(self):
        standard_tags = ["P-101", "P-101A", "V-200", "E-101", "TK-05", "C-301"]
        for tag in standard_tags:
            res = ISA51Catalog.is_isa_standard_tag(tag)
            self.assertTrue(res.is_standard, f"Tag {tag} should be standard equipment")
            self.assertEqual(res.category, "EQUIPMENT")

    def test_standard_instrument_tags(self):
        standard_instruments = ["PT-101", "TT-200", "FT-301", "LT-401", "FV-105", "PSV-901"]
        for tag in standard_instruments:
            res = ISA51Catalog.is_isa_standard_tag(tag)
            self.assertTrue(res.is_standard, f"Tag {tag} should be standard ISA instrument")
            self.assertEqual(res.category, "INSTRUMENT")

    def test_non_standard_refinery_tags(self):
        non_standard = ["SP-99", "VEND-01", "HYD-V01", "CUSTOM-LOOP-1"]
        for tag in non_standard:
            res = ISA51Catalog.is_isa_standard_tag(tag)
            self.assertFalse(res.is_standard, f"Tag {tag} should be non-standard")
            self.assertEqual(res.recommended_action, "FLAG_FOR_HUMAN_CHECK")

    def test_standard_and_non_standard_symbols(self):
        # Standard symbols
        res_pump = ISA51Catalog.is_isa_standard_symbol("centrifugal_pump", tag="P-101")
        self.assertTrue(res_pump.is_standard)

        res_valve = ISA51Catalog.is_isa_standard_symbol("gate_valve")
        self.assertTrue(res_valve.is_standard)

        # Non-standard symbols
        res_custom = ISA51Catalog.is_isa_standard_symbol("custom_valve", tag="SP-99")
        self.assertFalse(res_custom.is_standard)
        self.assertEqual(res_custom.category, "NON_ISA_SYMBOL")

        res_pig = ISA51Catalog.is_isa_standard_symbol("pig_launcher")
        self.assertFalse(res_pig.is_standard)


class TestYOLOSymbolDetector(unittest.TestCase):
    """Tests for YOLO symbol localization and image cropping."""

    def setUp(self):
        # Generate a valid 400x400 RGB test image
        self.test_image = Image.new("RGB", (400, 400), color=(240, 240, 240))
        # Draw dummy shape in center
        for x in range(150, 250):
            for y in range(150, 250):
                self.test_image.putpixel((x, y), (50, 100, 200))
        buf = io.BytesIO()
        self.test_image.save(buf, format="PNG")
        self.image_bytes = buf.getvalue()

        self.detector = YOLOSymbolDetector()

    def test_crop_symbol_with_coordinates(self):
        cropped_bytes, data_url = self.detector.crop_symbol(
            image_bytes=self.image_bytes,
            bbox=(140, 140, 260, 260),
            padding=10,
        )
        self.assertTrue(len(cropped_bytes) > 0)
        self.assertTrue(data_url.startswith("data:image/png;base64,"))

        # Check cropped image dimensions
        cropped_img = Image.open(io.BytesIO(cropped_bytes))
        self.assertTrue(cropped_img.size[0] > 0)
        self.assertTrue(cropped_img.size[1] > 0)

    def test_localize_and_crop(self):
        localized = self.detector.localize_and_crop(
            image_bytes=self.image_bytes,
            tag="SP-99",
            symbol_type="custom_valve",
            symbol_probability=0.91,
            ocr_confidence=0.88,
        )
        self.assertEqual(localized.tag, "SP-99")
        self.assertEqual(localized.symbol_type, "custom_valve")
        self.assertIsNotNone(localized.bbox)
        self.assertTrue(localized.cropped_image_base64.startswith("data:image/png;base64,"))


class TestThreeWayCheckDecisionGates(unittest.TestCase):
    """Tests for 3/3 Confirm, 2/3 Human Check, and 1/3 Reject decision routing."""

    def setUp(self):
        # Prepare valid test image
        img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.image_bytes = buf.getvalue()

        self.service = ThreeWayCheckService(min_symbol_prob=0.70, min_ocr_conf=0.70)

    def test_three_of_three_confirm(self):
        """All 3 checks pass: high symbol probability, high OCR, in asset register, ISA compliant."""
        result = self.service.evaluate_symbol(
            tag="P-101",
            symbol_type="centrifugal_pump",
            symbol_probability=0.92,
            ocr_confidence=0.89,
            in_asset_register=True,
            image_bytes=self.image_bytes,
        )
        self.assertEqual(result.decision, "3/3_CONFIRM")
        self.assertEqual(result.decision_label, "3/3 Confirm")
        self.assertEqual(result.decision_color, "green")
        self.assertEqual(result.passed_count, 3)
        self.assertFalse(result.requires_human_review)

    def test_two_of_three_human_check_non_isa_symbol(self):
        """Non-ISA 5.1 symbol triggers 2/3 Human Check even with high OCR and high visual score."""
        result = self.service.evaluate_symbol(
            tag="SP-99",
            symbol_type="custom_valve",  # Non-ISA 5.1 symbol
            symbol_probability=0.95,
            ocr_confidence=0.90,
            in_asset_register=True,
            image_bytes=self.image_bytes,
        )
        self.assertEqual(result.decision, "2/3_HUMAN_CHECK")
        self.assertEqual(result.decision_label, "2/3 Human check")
        self.assertEqual(result.decision_color, "yellow")
        self.assertEqual(result.passed_count, 2)
        self.assertTrue(result.requires_human_review)
        self.assertIsNotNone(result.cropped_image_base64)
        self.assertIn("custom_valve", result.two_way_breakdown["summary"])

    def test_two_of_three_human_check_missing_asset_register(self):
        """Standard ISA symbol with high visual prob and high OCR, but missing from Asset Register."""
        result = self.service.evaluate_symbol(
            tag="V-999",
            symbol_type="vertical_vessel",
            symbol_probability=0.91,
            ocr_confidence=0.88,
            in_asset_register=False,  # Not in asset register
            image_bytes=self.image_bytes,
        )
        self.assertEqual(result.decision, "2/3_HUMAN_CHECK")
        self.assertEqual(result.passed_count, 2)
        self.assertTrue(result.requires_human_review)
        self.assertIn("In asset register (Not Registered)", result.two_way_breakdown["failed_checks"])

    def test_two_of_three_human_check_low_ocr_confidence(self):
        """Standard ISA symbol in asset register with high symbol prob, but ambiguous OCR."""
        result = self.service.evaluate_symbol(
            tag="PT-101",
            symbol_type="pressure_transmitter",
            symbol_probability=0.88,
            ocr_confidence=0.45,  # Low OCR (< 0.70)
            in_asset_register=True,
            image_bytes=self.image_bytes,
        )
        self.assertEqual(result.decision, "2/3_HUMAN_CHECK")
        self.assertEqual(result.passed_count, 2)
        self.assertTrue(result.requires_human_review)

    def test_one_of_three_reject_spurious_noise(self):
        """Only 1 or 0 checks pass: spurious artifact or noise."""
        result = self.service.evaluate_symbol(
            tag="UNKNOWN-0",
            symbol_type="unknown_symbol",
            symbol_probability=0.35,  # Low
            ocr_confidence=0.40,  # Low
            in_asset_register=False,  # Missing
            image_bytes=self.image_bytes,
        )
        self.assertEqual(result.decision, "1/3_REJECT")
        self.assertEqual(result.decision_label, "1/3 Reject")
        self.assertEqual(result.decision_color, "red")
        self.assertEqual(result.passed_count, 0)
        self.assertFalse(result.requires_human_review)


class TestAnalyzePIDToolIntegration(unittest.TestCase):
    """Tests for AnalyzePIDTool execution with 3-Way Check and cropping."""

    def setUp(self):
        self.mock_vision = MagicMock(spec=VisionProvider)
        self.mock_graph = MagicMock(spec=GraphQueryService)

        # Simulate Neo4j: P-101 exists in asset register, SP-99 does not
        def fake_search(query, limit=1):
            if "P-101" in query:
                return [{"canonical_name": "P-101", "type": "Asset"}]
            return []

        self.mock_graph.search_nodes.side_effect = fake_search

        self.tool = AnalyzePIDTool(
            vision_provider=self.mock_vision,
            graph_service=self.mock_graph,
        )

        # Temporary valid PNG
        img = Image.new("RGB", (300, 300), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        self.temp_file.write(buf.getvalue())
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_pid_tool_executes_three_way_check(self):
        pid_text = (
            "Equipment detected:\n"
            "- Pump P-101 (crude pump)\n"
            "- Specialty Valve SP-99 (proprietary refinery sampling assembly)\n"
            "Connections:\n"
            "- P-101 discharges to SP-99\n"
        )
        self.mock_vision.describe_image.return_value = VisionResult(
            text=pid_text,
            model="gemma3:4b",
            total_duration_ns=1_000_000_000,
            eval_count=60,
        )

        result = _run_async(self.tool.execute({"image_path": self.temp_file.name}))
        self.assertTrue(result.success)

        pid_res: AnalyzePIDResult = result.result
        self.assertTrue(len(pid_res.three_way_checks) >= 2)

        # Check P-101 check
        p101_check = next((c for c in pid_res.three_way_checks if c["tag"] == "P-101"), None)
        self.assertIsNotNone(p101_check)
        self.assertEqual(p101_check["decision"], "3/3_CONFIRM")
        self.assertTrue(p101_check["in_asset_register"])

        # Check SP-99 check (non-ISA 5.1 proprietary valve)
        sp99_check = next((c for c in pid_res.three_way_checks if c["tag"] == "SP-99"), None)
        self.assertIsNotNone(sp99_check)
        self.assertEqual(sp99_check["decision"], "2/3_HUMAN_CHECK")
        self.assertTrue(sp99_check["requires_human_review"])
        self.assertIsNotNone(sp99_check["cropped_image_base64"])
        self.assertTrue(sp99_check["cropped_image_base64"].startswith("data:image/png;base64,"))

        # Check human check counts
        self.assertEqual(pid_res.human_checks_required, 1)

        # Verify audit text in result content
        self.assertIn("P&ID 3-WAY VERIFICATION AUDIT", str(pid_res))
        self.assertIn("[2/3 Human check] Tag: 'SP-99'", str(pid_res))
        self.assertIn("Localized via YOLO", str(pid_res))


class TestPIDVerifySymbolApi(unittest.TestCase):
    """Tests for human operator symbol verification endpoint."""

    def setUp(self):
        from datetime import datetime, timezone
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.routes.query import router as query_router
        from database.user_repository import User
        from dependencies import get_current_user

        self.app = FastAPI()
        self.app.include_router(query_router, prefix="/api")

        self.mock_user = User(
            user_id="usr_op_99",
            email="lead.operator@refinery.com",
            password_hash="mock",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.app.dependency_overrides[get_current_user] = lambda: self.mock_user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_approve_and_register_symbol(self):
        resp = self.client.post(
            "/api/query/pid/verify-symbol",
            json={
                "tag": "SP-99",
                "action": "APPROVE_AND_REGISTER",
                "reclassified_type": "Specialty Sampling Valve",
                "notes": "Verified against refinery P&ID addendum Rev 4",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["tag"], "SP-99")
        self.assertEqual(data["action"], "APPROVE_AND_REGISTER")
        self.assertIn("confirmed by operator", data["message"])

    def test_reclassify_symbol(self):
        resp = self.client.post(
            "/api/query/pid/verify-symbol",
            json={
                "tag": "SP-99",
                "action": "RECLASSIFY",
                "reclassified_type": "Vendor Skid Tie-In",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("Vendor Skid Tie-In", data["message"])

    def test_reject_symbol_noise(self):
        resp = self.client.post(
            "/api/query/pid/verify-symbol",
            json={
                "tag": "ARTIFACT-X",
                "action": "REJECT",
                "notes": "Scanner smudge",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("rejected as spurious artifact", data["message"])


if __name__ == "__main__":
    unittest.main()

