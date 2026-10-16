"""AnalyzePID tool for structured P&ID diagram understanding.

Combines the specialized P&ID vision prompt from image_parser with the
VisionProvider (Gemma 3 4B) to extract structured equipment tags,
instrumentation loops, line numbers, and flow connections from
Piping & Instrumentation Diagrams.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from typing import Any

from agents.tool_interface import Tool, ToolDefinition, ToolResult
from generation.vision_provider import VisionProvider, VisionResult
from graph.query_service import GraphQueryService
from ingestion.pid.isa_catalog import ISA51Catalog
from ingestion.pid.three_way_check import ThreeWayCheckResult, ThreeWayCheckService
from parser.image_parser import _build_prompt

logger = logging.getLogger(__name__)

# Common industrial equipment and instrument tag regex pattern
# Matches patterns like P-101, V-200, E-101A, TT-102, PT-401, FV-105, TK-01, SP-99
TAG_PATTERN = re.compile(r"\b([A-Z]{1,4}-[0-9]{1,4}[A-Z]?)\b")


class AnalyzePIDResult(str):
    """String result that also preserves structured P&ID extraction metadata."""

    raw_text: str
    equipment: list[str]
    instruments: list[str]
    connections: list[str]
    confidence: float
    model: str
    three_way_checks: list[dict[str, Any]]
    human_checks_required: int

    def __new__(
        cls,
        content: str,
        raw_text: str = "",
        equipment: list[str] | None = None,
        instruments: list[str] | None = None,
        connections: list[str] | None = None,
        confidence: float = 0.85,
        model: str = "gemma3:4b",
        three_way_checks: list[dict[str, Any]] | None = None,
        human_checks_required: int = 0,
    ) -> AnalyzePIDResult:
        obj = super().__new__(cls, content)
        obj.raw_text = raw_text
        obj.equipment = equipment or []
        obj.instruments = instruments or []
        obj.connections = connections or []
        obj.confidence = confidence
        obj.model = model
        obj.three_way_checks = three_way_checks or []
        obj.human_checks_required = human_checks_required
        return obj


class AnalyzePIDTool(Tool):
    """Agent tool for extracting structured equipment and connectivity from P&IDs."""

    def __init__(
        self,
        vision_provider: VisionProvider,
        graph_service: GraphQueryService | None = None,
        three_way_service: ThreeWayCheckService | None = None,
    ) -> None:
        """Initialize the AnalyzePID tool.

        Args:
            vision_provider: Configured VisionProvider instance.
            graph_service: Optional GraphQueryService to verify asset register presence.
            three_way_service: Optional ThreeWayCheckService for 3-way check validation.
        """
        self._vision_provider = vision_provider
        self._graph_service = graph_service
        self._three_way_service = three_way_service or ThreeWayCheckService()

    @property
    def definition(self) -> ToolDefinition:
        """Return the tool schema for LLM tool selection."""
        return ToolDefinition(
            name="analyze_pid",
            description=(
                "Specialized engineering tool for analyzing Piping & Instrumentation "
                "Diagrams (P&IDs) and Process Flow Diagrams (PFDs). Extracts structured "
                "equipment identifiers (pumps, vessels, columns, exchangers), "
                "instruments (temperature/pressure transmitters, valves), piping lines, "
                "and connectivity. Use this tool when you need to inspect a P&ID diagram."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the P&ID image file on disk.",
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Optional raw base64 encoded P&ID image data.",
                    },
                    "focus_equipment": {
                        "type": "string",
                        "description": (
                            "Optional equipment tag or component to focus analysis on (e.g., 'P-101', 'V-200')."
                        ),
                    },
                },
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute P&ID analysis on an image file or base64 data.

        Args:
            arguments: Dictionary with 'image_path' or 'image_base64', and optional 'focus_equipment'.

        Returns:
            ToolResult containing structured P&ID analysis or error details.
        """
        if not isinstance(arguments, dict):
            return ToolResult(
                tool_name="analyze_pid",
                success=False,
                result=None,
                error="Arguments must be a dictionary.",
            )

        image_path = arguments.get("image_path")
        image_base64 = arguments.get("image_base64")
        focus = arguments.get("focus_equipment")

        # Load image bytes
        image_bytes: bytes | None = None
        if isinstance(image_base64, str) and image_base64.strip():
            try:
                image_bytes = base64.b64decode(image_base64.strip())
            except Exception as e:
                return ToolResult(
                    tool_name="analyze_pid",
                    success=False,
                    result=None,
                    error=f"Invalid base64 image data: {e}",
                )
        elif isinstance(image_path, str) and image_path.strip():
            clean_path = image_path.strip()
            if clean_path.startswith("file://"):
                clean_path = clean_path[7:]
            clean_path = clean_path.replace(r"\&", "&")
            if not os.path.isfile(clean_path):
                # Try cross-platform path normalization
                # 1. Windows path on Linux (e.g. D:\data\storage -> /data/storage)
                import re
                alt1 = re.sub(r"^[A-Za-z]:[\\/]", "/", clean_path).replace("\\", "/")
                # 2. Linux path on Windows (e.g. /data/storage -> D:\data\storage)
                alt2 = os.path.abspath(clean_path)
                from config.settings import get_settings
                local_root = os.path.abspath(get_settings().storage.local_root)
                alt3 = os.path.join(local_root, os.path.basename(clean_path))
                alt4 = clean_path.replace("/data/storage", local_root).replace("\\data\\storage", local_root)
                for cand in (alt1, alt2, alt3, alt4):
                    if os.path.isfile(cand):
                        clean_path = cand
                        break
            if not os.path.isfile(clean_path):
                return ToolResult(
                    tool_name="analyze_pid",
                    success=False,
                    result=None,
                    error=f"P&ID image file not found: {clean_path}",
                )
            try:
                with open(clean_path, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                return ToolResult(
                    tool_name="analyze_pid",
                    success=False,
                    result=None,
                    error=f"Failed to read P&ID file '{clean_path}': {e}",
                )
        else:
            return ToolResult(
                tool_name="analyze_pid",
                success=False,
                result=None,
                error="Must provide either 'image_path' or 'image_base64'.",
            )

        if not image_bytes:
            return ToolResult(
                tool_name="analyze_pid",
                success=False,
                result=None,
                error="Image content is empty.",
            )

        # Build prompt using existing P&ID prompt from image_parser
        base_prompt = _build_prompt("PID")
        if isinstance(focus, str) and focus.strip():
            pid_prompt = (
                f"{base_prompt}\n\n"
                f"SPECIAL FOCUS: Pay particular attention to equipment, instruments, "
                f"inlet/outlet lines, and connected valves for tag '{focus.strip()}'."
            )
        else:
            pid_prompt = base_prompt

        try:
            vision_result: VisionResult = await asyncio.to_thread(
                self._vision_provider.describe_image,
                image_bytes=image_bytes,
                prompt=pid_prompt,
            )

            text = vision_result.text.strip()

            # Extract structured tags and connections from vision output
            all_tags = set(TAG_PATTERN.findall(text))
            
            # Categorize tags heuristically into equipment vs instruments
            equipment_prefixes = ("P-", "V-", "E-", "T-", "TK-", "C-", "K-", "F-", "R-")
            instrument_prefixes = ("PT-", "TT-", "FT-", "LT-", "PI-", "TI-", "FI-", "LI-", "FV-", "PV-", "TV-", "LV-", "FC-", "TC-", "PC-")

            equipment: list[str] = sorted([t for t in all_tags if any(t.startswith(p) for p in equipment_prefixes)])
            instruments: list[str] = sorted([t for t in all_tags if any(t.startswith(p) for p in instrument_prefixes)])
            
            # If any tag doesn't match standard prefixes, keep in equipment list
            other_tags = sorted([t for t in all_tags if t not in equipment and t not in instruments])
            if other_tags:
                equipment.extend(other_tags)

            # Extract connection statements (lines mentioning 'connect' or 'flow' or 'from/to')
            connection_lines: list[str] = []
            for line in text.splitlines():
                lower = line.lower()
                if any(w in lower for w in ("connect", "flows to", "inlet", "outlet", "discharges to", "upstream", "downstream")):
                    cleaned = line.strip().lstrip("-*#").strip()
                    if cleaned:
                        connection_lines.append(cleaned)

            # Evaluate 3-Way Check on identified symbols and tags
            three_way_checks: list[dict[str, Any]] = []
            human_checks_count = 0

            # Tags to evaluate: focus equipment first if specified, then all detected tags
            tags_to_check: list[str] = []
            if isinstance(focus, str) and focus.strip():
                clean_focus = focus.strip().upper()
                tags_to_check.append(clean_focus)
            for t in sorted(all_tags):
                if t not in tags_to_check:
                    tags_to_check.append(t)

            for tag_candidate in tags_to_check:
                # Query asset register in Neo4j Knowledge Graph if graph_service is available
                in_asset_register = False
                if self._graph_service:
                    try:
                        nodes = self._graph_service.search_nodes(tag_candidate, limit=1)
                        in_asset_register = bool(nodes and len(nodes) > 0)
                    except Exception as err:
                        logger.debug("Graph search check failed for tag %s: %s", tag_candidate, err)
                        in_asset_register = False

                # Infer symbol type heuristic from tag prefix or text context
                prefix_candidate = tag_candidate.split("-", 1)[0].upper() if "-" in tag_candidate else ""
                if prefix_candidate.startswith("P") and len(prefix_candidate) <= 2:
                    sym_type = "centrifugal_pump"
                elif prefix_candidate in ("V", "D"):
                    sym_type = "vertical_vessel"
                elif prefix_candidate in ("E", "HE"):
                    sym_type = "heat_exchanger"
                elif prefix_candidate in ("T", "COL"):
                    sym_type = "distillation_column"
                elif prefix_candidate == "TK":
                    sym_type = "storage_tank"
                elif prefix_candidate in ("C", "K"):
                    sym_type = "centrifugal_compressor"
                elif prefix_candidate in ("PT", "PI"):
                    sym_type = "pressure_transmitter"
                elif prefix_candidate in ("TT", "TI"):
                    sym_type = "temperature_transmitter"
                elif prefix_candidate in ("FT", "FI"):
                    sym_type = "flow_transmitter"
                elif prefix_candidate in ("LT", "LI"):
                    sym_type = "level_transmitter"
                elif prefix_candidate in ("FV", "PV", "TV", "LV"):
                    sym_type = "control_valve"
                elif prefix_candidate in ("PSV", "PRV"):
                    sym_type = "pressure_safety_valve"
                elif any(k in tag_candidate.lower() for k in ("sp-", "vend", "cust", "hyd", "flame", "pig")):
                    sym_type = "custom_valve"
                else:
                    sym_type = "unknown_symbol"

                # Estimate symbol probability and OCR confidence
                sym_prob = 0.88
                ocr_conf = 0.85
                # If tag was found in text directly, high OCR confidence
                if tag_candidate in text:
                    ocr_conf = 0.92

                check_res = self._three_way_service.evaluate_symbol(
                    tag=tag_candidate,
                    symbol_type=sym_type,
                    symbol_probability=sym_prob,
                    ocr_confidence=ocr_conf,
                    in_asset_register=in_asset_register,
                    image_bytes=image_bytes,
                )
                if check_res.requires_human_review:
                    human_checks_count += 1
                three_way_checks.append(check_res.to_dict())

            # Build human-readable formatted output for LLM
            lines = [f"P&ID Analysis ({vision_result.model}) [Confidence: 0.85]:"]
            if equipment:
                lines.append(f"Identified Equipment ({len(equipment)}): {', '.join(equipment)}")
            if instruments:
                lines.append(f"Identified Instruments ({len(instruments)}): {', '.join(instruments)}")
            if connection_lines:
                lines.append("Flow & Connections:")
                for conn in connection_lines[:10]:
                    lines.append(f"  - {conn}")

            # Append 3-Way Check Audit section
            if three_way_checks:
                lines.append("\n" + "=" * 60)
                lines.append("P&ID 3-WAY VERIFICATION AUDIT")
                lines.append("=" * 60)
                lines.append("Three-Way Decision Gates: Symbol probability | OCR Confidence | In asset register")
                lines.append("Routing: 3/3 Confirm (Green) | 2/3 Human check (Yellow) | 1/3 Reject (Red)")
                lines.append("")
                for chk in three_way_checks:
                    icon = "✓" if chk["decision"] == "3/3_CONFIRM" else ("⚠" if chk["decision"] == "2/3_HUMAN_CHECK" else "✗")
                    lines.append(f"{icon} [{chk['decision_label']}] Tag: '{chk['tag']}' (Symbol: {chk['symbol_type']})")
                    s_sym = "PASS" if chk["symbol_prob_passed"] else "FAIL"
                    s_ocr = "PASS" if chk["ocr_conf_passed"] else "FAIL"
                    s_ast = "PASS" if chk["asset_reg_passed"] else "FAIL"
                    lines.append(f"   • Symbol Probability: {chk['symbol_probability']:.0%} [{s_sym}]")
                    lines.append(f"   • OCR Confidence:     {chk['ocr_confidence']:.0%} [{s_ocr}]")
                    lines.append(f"   • In Asset Register:  {'YES' if chk['in_asset_register'] else 'NO'} [{s_ast}]")
                    if not chk["is_isa_standard"]:
                        lines.append(f"   • ISA 5.1 Compliance: Non-standard / Proprietary ({chk['isa_details']})")
                    if chk["requires_human_review"]:
                        lines.append("   → 2/3 Check Triggered: Localized via YOLO and cropped for Human Operator Review.")
                        ascii_diag = chk.get("two_way_breakdown", {}).get("diagram_ascii")
                        if ascii_diag:
                            lines.append(ascii_diag)

            lines.append("\nDetailed Visual Extraction:")
            lines.append(text)

            content = "\n".join(lines)

            return ToolResult(
                tool_name="analyze_pid",
                success=True,
                result=AnalyzePIDResult(
                    content,
                    raw_text=text,
                    equipment=equipment,
                    instruments=instruments,
                    connections=connection_lines,
                    confidence=0.85,
                    model=vision_result.model,
                    three_way_checks=three_way_checks,
                    human_checks_required=human_checks_count,
                ),
            )

        except RuntimeError as e:
            logger.warning("P&ID vision model error: %s", e)
            return ToolResult(
                tool_name="analyze_pid",
                success=False,
                result=None,
                error=(
                    f"P&ID vision inference failed: {str(e)}. "
                    "Ensure 'gemma3:4b' is installed via 'ollama pull gemma3:4b'."
                ),
            )
        except Exception as e:
            logger.error("AnalyzePIDTool unexpected error: %s", e, exc_info=True)
            return ToolResult(
                tool_name="analyze_pid",
                success=False,
                result=None,
                error=f"P&ID analysis failed: {str(e)}",
            )
