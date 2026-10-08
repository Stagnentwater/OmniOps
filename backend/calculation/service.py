"""Calculation Service — orchestrates the sandbox pipeline.

Coordinates: Detection → Validation → Execution → Audit.

The service never generates code itself (that's the LLM's job via
the query orchestrator). It receives pre-generated code, validates it,
executes it in the sandbox, and returns audited results.

Failure handling:
- Validation failure → returns error result, never executes
- Execution failure → returns error result, logs audit
- Any failure → NEVER blocks the query pipeline
"""

from __future__ import annotations

import logging
from typing import Any

from calculation.models import (
    CalculationAudit,
    CalculationRequest,
    CalculationResult,
    create_audit,
)
from calculation.validator import CodeValidator, ValidationResult
from calculation.sandbox_provider import SandboxProvider
from calculation.subprocess_sandbox import SubprocessSandboxProvider

logger = logging.getLogger(__name__)


class CalculationService:
    """Orchestrates code validation, sandbox execution, and audit logging.

    Does NOT generate code. Receives pre-generated code from the caller.
    """

    def __init__(
        self,
        sandbox: SandboxProvider | None = None,
        validator: CodeValidator | None = None,
        timeout_seconds: float = 5.0,
        model_name: str = "unknown",
    ) -> None:
        self._sandbox = sandbox or SubprocessSandboxProvider()
        self._validator = validator or CodeValidator()
        self._timeout = timeout_seconds
        self._model_name = model_name

    def execute_calculation(
        self,
        request: CalculationRequest,
    ) -> tuple[CalculationResult, CalculationAudit]:
        """Validate and execute a calculation request.

        Args:
            request: The structured calculation request with code and inputs.

        Returns:
            A tuple of (CalculationResult, CalculationAudit).
            The result is always returned — never raises.
        """
        # 1. Validate code
        validation = self._validator.validate(request.generated_code)

        if not validation.valid:
            logger.warning(
                "Code validation failed: %s", validation.reason,
            )
            result = CalculationResult(
                success=False,
                result="",
                error=f"Code validation failed: {validation.reason}",
                exit_code=-3,
                execution_time_ms=0.0,
            )
            audit = create_audit(
                request=request,
                result=result,
                model_used=self._model_name,
                sandbox_provider=self._sandbox.name(),
                validation_passed=False,
            )
            self._log_audit(audit)
            return result, audit

        # 2. Execute in sandbox
        logger.info("Executing calculation in sandbox (%s)...", self._sandbox.name())
        result = self._sandbox.execute(
            code=request.generated_code,
            inputs=request.inputs,
            timeout_seconds=self._timeout,
        )

        # 3. Create audit record
        audit = create_audit(
            request=request,
            result=result,
            model_used=self._model_name,
            sandbox_provider=self._sandbox.name(),
            validation_passed=True,
        )
        self._log_audit(audit)

        if result.success:
            logger.info(
                "Calculation succeeded in %.0fms: %s",
                result.execution_time_ms,
                result.result[:100],
            )
        else:
            logger.warning(
                "Calculation failed (exit=%d, %.0fms): %s",
                result.exit_code,
                result.execution_time_ms,
                result.error[:200],
            )

        return result, audit

    @staticmethod
    def _log_audit(audit: CalculationAudit) -> None:
        """Log the audit record as structured data."""
        logger.info(
            "CALCULATION_AUDIT: timestamp=%s model=%s sandbox=%s "
            "validation=%s exit_code=%d time_ms=%.0f",
            audit.timestamp,
            audit.model_used,
            audit.sandbox_provider,
            audit.validation_passed,
            audit.exit_code,
            audit.execution_time_ms,
        )
