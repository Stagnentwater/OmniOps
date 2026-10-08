"""Calculate tool for sandboxed numerical and engineering calculations.

Wraps CalculationService to provide the agent with a secure execution
environment for math, thermodynamics formulas, fluid dynamics equations,
and unit conversions. All code is statically validated by CodeValidator
and executed in SubprocessSandboxProvider with no network or OS access.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from agents.tool_interface import Tool, ToolDefinition, ToolResult
from calculation.models import CalculationAudit, CalculationRequest
from calculation.service import CalculationService

logger = logging.getLogger(__name__)


class CalculateToolResult(str):
    """String result that also preserves calculation metadata and audit trail."""

    raw_result: str
    exit_code: int
    execution_time_ms: float
    audit: CalculationAudit | None

    def __new__(
        cls,
        content: str,
        raw_result: str = "",
        exit_code: int = 0,
        execution_time_ms: float = 0.0,
        audit: CalculationAudit | None = None,
    ) -> CalculateToolResult:
        obj = super().__new__(cls, content)
        obj.raw_result = raw_result
        obj.exit_code = exit_code
        obj.execution_time_ms = execution_time_ms
        obj.audit = audit
        return obj


class CalculateTool(Tool):
    """Agent tool for deterministic sandboxed Python calculations."""

    def __init__(
        self,
        calculation_service: CalculationService,
    ) -> None:
        """Initialize the Calculate tool.

        Args:
            calculation_service: Configured CalculationService instance.
        """
        self._calculation_service = calculation_service

    @property
    def definition(self) -> ToolDefinition:
        """Return the tool schema for LLM tool selection."""
        return ToolDefinition(
            name="calculate",
            description=(
                "Executes deterministic mathematical equations, engineering formulas, "
                "unit conversions, or numerical computations in a secure isolated sandbox. "
                "Allowed modules: math, statistics, decimal, fractions, datetime. "
                "The code must assign its final result to a variable named 'result' "
                "(e.g., result = flow_rate * cp * delta_t). "
                "Alternatively, you can provide an 'expression' to evaluate directly. "
                "NEVER compute numbers in your head or guess values; always use this tool."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": (
                            "Python code to execute. Must define 'result' with the final calculated answer. "
                            "Example: 'import math\\nresult = math.sqrt(144) * 2'"
                        ),
                    },
                    "expression": {
                        "type": "string",
                        "description": (
                            "Alternative direct expression (e.g., '150 * 0.0689476' or '50 * 4.18 * 25'). "
                            "Will automatically be wrapped as 'result = <expression>'."
                        ),
                    },
                    "inputs": {
                        "type": "object",
                        "description": (
                            "Optional dictionary of variable names and numerical values "
                            "(e.g., {'mass_flow': 50.0, 'cp': 4.184, 'delta_t': 25.0})."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional description of what is being computed for auditing.",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Validate and execute calculation in the sandbox.

        Args:
            arguments: Dictionary with 'code' or 'expression', and optional 'inputs', 'query'.

        Returns:
            ToolResult containing computed output or error details.
        """
        if not isinstance(arguments, dict):
            return ToolResult(
                tool_name="calculate",
                success=False,
                result=None,
                error="Arguments must be a dictionary.",
            )

        code = arguments.get("code")
        expression = arguments.get("expression")
        inputs = arguments.get("inputs", {})
        query = arguments.get("query", "agent calculation")

        if not isinstance(inputs, dict):
            inputs = {}

        # Resolve code from code or expression
        final_code = ""
        if isinstance(code, str) and code.strip():
            raw_code = code.strip()
            # If the user code doesn't set 'result' and is a simple single-line expression, wrap it
            if not re.search(r"\bresult\s*=", raw_code) and "\n" not in raw_code:
                final_code = f"result = {raw_code}"
            else:
                final_code = raw_code
        elif isinstance(expression, str) and expression.strip():
            final_code = f"result = {expression.strip()}"
        else:
            return ToolResult(
                tool_name="calculate",
                success=False,
                result=None,
                error="Must provide either 'code' or 'expression' parameter.",
            )

        # Auto-import allowed standard modules if referenced without explicit import
        prefix_imports = []
        if "math." in final_code and "import math" not in final_code:
            prefix_imports.append("import math")
        if "statistics." in final_code and "import statistics" not in final_code:
            prefix_imports.append("import statistics")
        if "decimal." in final_code and "import decimal" not in final_code:
            prefix_imports.append("import decimal")
        if prefix_imports:
            final_code = "\n".join(prefix_imports) + "\n" + final_code

        request = CalculationRequest(
            query=str(query),
            inputs=inputs,
            units={},
            generated_code=final_code,
        )

        try:
            # execute_calculation is CPU/subprocess I/O, run in threadpool
            calc_result, audit = await asyncio.to_thread(
                self._calculation_service.execute_calculation,
                request,
            )

            if calc_result.success:
                formatted_message = f"Calculation result: {calc_result.result}"
                return ToolResult(
                    tool_name="calculate",
                    success=True,
                    result=CalculateToolResult(
                        formatted_message,
                        raw_result=calc_result.result,
                        exit_code=calc_result.exit_code,
                        execution_time_ms=calc_result.execution_time_ms,
                        audit=audit,
                    ),
                    execution_time_ms=calc_result.execution_time_ms,
                )
            else:
                return ToolResult(
                    tool_name="calculate",
                    success=False,
                    result=None,
                    error=calc_result.error or "Calculation returned non-zero exit code.",
                    execution_time_ms=calc_result.execution_time_ms,
                )

        except Exception as e:
            logger.error("CalculateTool unexpected error: %s", e, exc_info=True)
            return ToolResult(
                tool_name="calculate",
                success=False,
                result=None,
                error=f"Calculation service failure: {str(e)}",
            )
