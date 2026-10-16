"""Three-Way Check Engine for P&ID Symbol and Asset Verification.

Implements the 3-Way Check decision architecture:
  Input Dimensions:
    1. Symbol probability (Visual detector confidence score)
    2. OCR Confidence (Text tag extraction confidence score)
    3. In asset register (Presence in refinery asset register / Neo4j graph)

  Decision Gates:
    - 3/3 Confirm (Green): All 3 checks pass -> Automated ingestion & confirmation.
    - 2/3 Human check (Yellow): 2 of 3 checks pass (e.g. non-ISA 5.1 symbol,
      missing from asset register, or ambiguous OCR) -> Localize with YOLO,
      crop symbol snippet, and present 2-way check diagram to human operator.
    - 1/3 Reject (Red): <= 1 check passes -> Spurious noise or visual artifact.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from ingestion.pid.isa_catalog import ISA51Catalog, ISACheckResult
from ingestion.pid.yolo_detector import LocalizedSymbol, YOLOSymbolDetector

logger = logging.getLogger(__name__)


@dataclass
class ThreeWayCheckResult:
    """Result of running the 3-Way Check on a P&ID symbol candidate."""

    tag: str
    symbol_type: str
    is_isa_standard: bool
    isa_category: str
    isa_details: str
    symbol_probability: float
    ocr_confidence: float
    in_asset_register: bool
    symbol_prob_passed: bool
    ocr_conf_passed: bool
    asset_reg_passed: bool
    passed_count: int
    decision: str  # "3/3_CONFIRM" | "2/3_HUMAN_CHECK" | "1/3_REJECT"
    decision_label: str  # "3/3 Confirm" | "2/3 Human check" | "1/3 Reject"
    decision_color: str  # "green" | "yellow" | "red"
    requires_human_review: bool
    two_way_breakdown: dict[str, Any]
    bbox: tuple[int, int, int, int] | None = None
    cropped_image_base64: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return asdict(self)


class ThreeWayCheckService:
    """Evaluates P&ID symbol candidates against the 3-Way Check architecture."""

    def __init__(
        self,
        yolo_detector: YOLOSymbolDetector | None = None,
        min_symbol_prob: float = 0.70,
        min_ocr_conf: float = 0.70,
    ) -> None:
        """Initialize the 3-Way Check Service.

        Args:
            yolo_detector: Optional YOLO symbol detector instance.
            min_symbol_prob: Threshold for visual symbol probability (default: 0.70).
            min_ocr_conf: Threshold for OCR tag confidence (default: 0.70).
        """
        self._detector = yolo_detector or YOLOSymbolDetector()
        self._min_symbol_prob = min_symbol_prob
        self._min_ocr_conf = min_ocr_conf

    def evaluate_symbol(
        self,
        tag: str,
        symbol_type: str,
        symbol_probability: float,
        ocr_confidence: float,
        in_asset_register: bool,
        image_bytes: bytes | None = None,
        candidate_bbox: tuple[int, int, int, int] | None = None,
    ) -> ThreeWayCheckResult:
        """Execute the 3-Way Check on a single symbol candidate.

        Args:
            tag: Instrument or equipment identifier (e.g. 'P-101', 'SP-99').
            symbol_type: Classified symbol type (e.g. 'centrifugal_pump', 'custom_valve').
            symbol_probability: Visual detection score (0.0 to 1.0).
            ocr_confidence: Tag text recognition confidence (0.0 to 1.0).
            in_asset_register: Whether tag exists in refinery asset register.
            image_bytes: Optional raw image bytes for YOLO cropping.
            candidate_bbox: Optional known bounding box coordinates.

        Returns:
            ThreeWayCheckResult with decision and cropped image preview if human check needed.
        """
        # 1. Evaluate ISA 5.1 refinery compliance
        isa_res: ISACheckResult = ISA51Catalog.is_isa_standard_symbol(symbol_type, tag=tag)

        # 2. Check each of the 3 dimensions
        symbol_prob_passed = symbol_probability >= self._min_symbol_prob
        ocr_conf_passed = ocr_confidence >= self._min_ocr_conf
        asset_reg_passed = bool(in_asset_register)

        checks = [
            ("Symbol probability", symbol_prob_passed, symbol_probability, self._min_symbol_prob),
            ("OCR Confidence", ocr_conf_passed, ocr_confidence, self._min_ocr_conf),
            ("In asset register", asset_reg_passed, 1.0 if in_asset_register else 0.0, 1.0),
        ]

        passed_list: list[str] = []
        failed_list: list[str] = []

        for name, passed, score, thresh in checks:
            if passed:
                passed_list.append(f"{name} ({score:.0%})")
            else:
                if name == "In asset register":
                    failed_list.append(f"{name} (Not Registered)")
                else:
                    failed_list.append(f"{name} ({score:.0%} < {thresh:.0%})")

        raw_passed_count = len(passed_list)

        # 3. Decision mapping matching SIH 2024 diagram:
        # If symbol is not part of ISA 5.1, the 3-way check cannot automatically confirm;
        # it is routed to 2/3 Human check for operator localization & verification.
        if raw_passed_count == 3:
            if isa_res.is_standard:
                decision = "3/3_CONFIRM"
                decision_label = "3/3 Confirm"
                decision_color = "green"
                requires_human = False
                passed_count = 3
            else:
                # 3 dimensions passed, but symbol is not part of ISA 5.1 of the refinery:
                # 3-way check fails automatic confirmation -> routes to 2/3 Human check!
                decision = "2/3_HUMAN_CHECK"
                decision_label = "2/3 Human check"
                decision_color = "yellow"
                requires_human = True
                passed_count = 2
                failed_list.append(f"ISA 5.1 Standard ({isa_res.details})")
        elif raw_passed_count == 2:
            decision = "2/3_HUMAN_CHECK"
            decision_label = "2/3 Human check"
            decision_color = "yellow"
            requires_human = True
            passed_count = 2
            if not isa_res.is_standard:
                failed_list.append(f"ISA 5.1 Standard ({isa_res.details})")
        else:
            decision = "1/3_REJECT"
            decision_label = "1/3 Reject"
            decision_color = "red"
            requires_human = False
            passed_count = raw_passed_count

        # Build 2-way / 3-way check diagram breakdown
        explanation = self._build_breakdown_explanation(
            tag=tag,
            symbol_type=symbol_type,
            decision=decision,
            passed_list=passed_list,
            failed_list=failed_list,
            is_isa_standard=isa_res.is_standard,
            isa_details=isa_res.details,
        )

        diagram_ascii = self._format_diagram_ascii(
            passed_count=passed_count,
            decision_label=decision_label,
            symbol_prob_passed=symbol_prob_passed,
            ocr_conf_passed=ocr_conf_passed,
            asset_reg_passed=asset_reg_passed,
        )

        two_way_breakdown = {
            "passed_checks": passed_list,
            "failed_checks": failed_list,
            "passed_count": passed_count,
            "summary": explanation,
            "diagram_ascii": diagram_ascii,
            "isa_compliance": {
                "is_standard": isa_res.is_standard,
                "category": isa_res.category,
                "details": isa_res.details,
            },
        }

        # 4. Crop localized symbol when human check is needed or when image provided
        cropped_base64: str | None = None
        bbox: tuple[int, int, int, int] | None = candidate_bbox

        if image_bytes:
            localized: LocalizedSymbol = self._detector.localize_and_crop(
                image_bytes=image_bytes,
                tag=tag,
                symbol_type=symbol_type,
                symbol_probability=symbol_probability,
                ocr_confidence=ocr_confidence,
                candidate_bbox=candidate_bbox,
            )
            bbox = localized.bbox
            cropped_base64 = localized.cropped_image_base64

        return ThreeWayCheckResult(
            tag=tag,
            symbol_type=symbol_type,
            is_isa_standard=isa_res.is_standard,
            isa_category=isa_res.category,
            isa_details=isa_res.details,
            symbol_probability=symbol_probability,
            ocr_confidence=ocr_confidence,
            in_asset_register=in_asset_register,
            symbol_prob_passed=symbol_prob_passed,
            ocr_conf_passed=ocr_conf_passed,
            asset_reg_passed=asset_reg_passed,
            passed_count=passed_count,
            decision=decision,
            decision_label=decision_label,
            decision_color=decision_color,
            requires_human_review=requires_human,
            two_way_breakdown=two_way_breakdown,
            bbox=bbox,
            cropped_image_base64=cropped_base64,
        )

    def _build_breakdown_explanation(
        self,
        tag: str,
        symbol_type: str,
        decision: str,
        passed_list: list[str],
        failed_list: list[str],
        is_isa_standard: bool,
        isa_details: str,
    ) -> str:
        """Construct a structured industrial audit explanation."""
        if decision == "3/3_CONFIRM":
            return (
                f"Tag '{tag}' passed all 3 verification checks: {', '.join(passed_list)}. "
                "Conforms to ISA 5.1 and verified in refinery asset register. Automatically confirmed."
            )
        elif decision == "2/3_HUMAN_CHECK":
            reason = (
                f"Symbol '{symbol_type}' for tag '{tag}' passed 2 of 3 checks ({', '.join(passed_list)}), "
                f"but failed 1 check ({', '.join(failed_list)}). "
            )
            if not is_isa_standard:
                reason += f"Non-ISA 5.1 refinery symbol detected ({isa_details}). "
            reason += "Region localized and cropped for human engineering review."
            return reason
        else:
            return (
                f"Tag '{tag}' ({symbol_type}) only passed {len(passed_list)} of 3 checks. "
                f"Failed: {', '.join(failed_list)}. Rejected as spurious visual artifact."
            )

    @staticmethod
    def _format_diagram_ascii(
        passed_count: int,
        decision_label: str,
        symbol_prob_passed: bool,
        ocr_conf_passed: bool,
        asset_reg_passed: bool,
    ) -> str:
        """Format 3-Way Check decision diamond in ASCII."""
        s_sym = "[PASS]" if symbol_prob_passed else "[FAIL]"
        s_ocr = "[PASS]" if ocr_conf_passed else "[FAIL]"
        s_ast = "[PASS]" if asset_reg_passed else "[FAIL]"

        return (
            "           ┌───────────────────────────────────────────────┐\n"
            "           │                  3-Way Check                  │\n"
            f"           │ Symbol prob {s_sym}   OCR Conf {s_ocr}   Asset Reg {s_ast} │\n"
            "           │        \\              |              /        │\n"
            "           │         ───────►   [ < > ]   ◄───────         │\n"
            "           │                     / | \\                     │\n"
            f"           │             DECISION: {decision_label:<16}        │\n"
            "           └───────────────────────────────────────────────┘"
        )
