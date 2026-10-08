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
from parser.image_parser import _build_prompt

logger = logging.getLogger(__name__)

# Common industrial equipment and instrument tag regex pattern
# Matches patterns like P-101, V-200, E-101A, TT-102, PT-401, FV-105, TK-01
TAG_PATTERN = re.compile(r"\b([A-Z]{1,4}-[0-9]{1,4}[A-Z]?)\b")


class AnalyzePIDResult(str):
    """String result that also preserves structured P&ID extraction metadata."""

    raw_text: str
    equipment: list[str]
    instruments: list[str]
    connections: list[str]
    confidence: float
    model: str

    def __new__(
        cls,
        content: str,
        raw_text: str = "",
        equipment: list[str] | None = None,
        instruments: list[str] | None = None,
        connections: list[str] | None = None,
        confidence: float = 0.85,
        model: str = "gemma3:4b",
    ) -> AnalyzePIDResult:
        obj = super().__new__(cls, content)
        obj.raw_text = raw_text
        obj.equipment = equipment or []
        obj.instruments = instruments or []
        obj.connections = connections or []
        obj.confidence = confidence
        obj.model = model
        return obj


class AnalyzePIDTool(Tool):
    """Agent tool for extracting structured equipment and connectivity from P&IDs."""

    def __init__(
        self,
        vision_provider: VisionProvider,
    ) -> None:
        """Initialize the AnalyzePID tool.

        Args:
            vision_provider: Configured VisionProvider instance.
        """
        self._vision_provider = vision_provider

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
