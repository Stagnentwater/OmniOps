"""Abstract SandboxProvider for isolated code execution.

The SandboxProvider is the abstraction that separates the calculation
service from the specific isolation mechanism. Implementations:
- SubprocessSandboxProvider (prototype — process-level isolation)
- DockerSandboxProvider (future — container-level isolation)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from calculation.models import CalculationResult


class SandboxProvider(ABC):
    """Abstract base for isolated Python code execution."""

    @abstractmethod
    def execute(
        self,
        code: str,
        inputs: dict,
        timeout_seconds: float = 5.0,
    ) -> CalculationResult:
        """Execute validated Python code in an isolated environment.

        Args:
            code: Pre-validated Python code (already passed CodeValidator).
            inputs: Structured input variables available to the code.
            timeout_seconds: Maximum execution time.

        Returns:
            CalculationResult with success/failure, output, and timing.
        """

    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this provider."""
