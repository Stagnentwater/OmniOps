"""Data models for the Calculation Sandbox pipeline.

Defines the structured contracts for calculation requests, results,
and audit records. All models are frozen dataclasses to guarantee
immutability and provenance integrity.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CalculationRequest:
    """Structured input to the sandbox.

    The sandbox receives ONLY query + inputs + generated_code.
    It never has access to documents, databases, or the LLM.
    """

    query: str
    inputs: dict[str, Any]
    units: dict[str, str]
    generated_code: str


@dataclass(frozen=True)
class CalculationResult:
    """Output from a sandbox execution."""

    success: bool
    result: str
    error: str
    exit_code: int
    execution_time_ms: float


@dataclass(frozen=True)
class CalculationAudit:
    """Full audit record for a single calculation execution.

    Never contains secrets, credentials, or internal paths.
    """

    query: str
    inputs: dict[str, Any]
    generated_code: str
    result: str
    error: str
    execution_time_ms: float
    exit_code: int
    timestamp: str
    model_used: str
    sandbox_provider: str
    validation_passed: bool


def create_audit(
    *,
    request: CalculationRequest,
    result: CalculationResult,
    model_used: str,
    sandbox_provider: str,
    validation_passed: bool,
) -> CalculationAudit:
    """Create an audit record from request + result."""
    return CalculationAudit(
        query=request.query,
        inputs=request.inputs,
        generated_code=request.generated_code,
        result=result.result,
        error=result.error,
        execution_time_ms=result.execution_time_ms,
        exit_code=result.exit_code,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        model_used=model_used,
        sandbox_provider=sandbox_provider,
        validation_passed=validation_passed,
    )
