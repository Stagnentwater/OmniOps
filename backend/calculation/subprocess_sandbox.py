"""Subprocess-based sandbox provider for prototype deployment.

Executes validated Python code in a subprocess with:
- Empty environment (no secrets leak)
- Timeout enforcement (subprocess killed after limit)
- Stdout/stderr capture with size limits
- No shell=True (no shell injection)

This is the prototype isolation mechanism. For production,
use DockerSandboxProvider with container-level isolation.

Security layers:
1. CodeValidator (AST allowlist) — already applied before this runs
2. Empty environment — no env vars accessible
3. Timeout — subprocess killed after 5 seconds
4. Stdout/stderr size limits — prevents output flooding
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from calculation.models import CalculationResult
from calculation.sandbox_provider import SandboxProvider

logger = logging.getLogger(__name__)

# Maximum output sizes
MAX_STDOUT_BYTES = 10_240  # 10 KB
MAX_STDERR_BYTES = 10_240  # 10 KB


class SubprocessSandboxProvider(SandboxProvider):
    """Execute code in a subprocess with timeout and empty environment.

    The subprocess:
    - Runs with an empty environment (only PYTHONPATH excluded)
    - Has a strict timeout (killed with SIGKILL on expiry)
    - Captures stdout/stderr with size limits
    - Uses a temporary file for the script (cleaned up after)
    - Does NOT use shell=True
    """

    def __init__(self, python_executable: str | None = None) -> None:
        self._python = python_executable or sys.executable

    def execute(
        self,
        code: str,
        inputs: dict,
        timeout_seconds: float = 5.0,
    ) -> CalculationResult:
        """Execute validated code in a subprocess."""
        # Build the wrapper script that injects inputs and captures result
        wrapper = self._build_wrapper(code, inputs)

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                [self._python, "-c", wrapper],
                capture_output=True,
                timeout=timeout_seconds,
                text=True,
                env={},  # Empty environment — no secrets
                cwd=tempfile.gettempdir(),
            )

            elapsed_ms = (time.monotonic() - t0) * 1000

            stdout = result.stdout[:MAX_STDOUT_BYTES] if result.stdout else ""
            stderr = result.stderr[:MAX_STDERR_BYTES] if result.stderr else ""

            # Sanitize stderr to remove internal paths
            stderr = self._sanitize_error(stderr)

            return CalculationResult(
                success=result.returncode == 0,
                result=stdout.strip(),
                error=stderr.strip(),
                exit_code=result.returncode,
                execution_time_ms=round(elapsed_ms, 2),
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.warning(
                "Sandbox execution timed out after %.0fms", elapsed_ms,
            )
            return CalculationResult(
                success=False,
                result="",
                error=f"Calculation timed out after {timeout_seconds}s",
                exit_code=-1,
                execution_time_ms=round(elapsed_ms, 2),
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.error("Sandbox execution error: %s", e)
            return CalculationResult(
                success=False,
                result="",
                error="Calculation execution failed",
                exit_code=-2,
                execution_time_ms=round(elapsed_ms, 2),
            )

    def name(self) -> str:
        return "SubprocessSandbox (prototype)"

    @staticmethod
    def _build_wrapper(code: str, inputs: dict) -> str:
        """Build a wrapper script that injects inputs and runs user code.

        The wrapper:
        1. Defines input variables in the local scope
        2. Executes the user code
        3. Prints the result (expected to be in a variable called 'result')
        """
        # Serialize inputs as Python literals
        input_lines = []
        for key, value in inputs.items():
            input_lines.append(f"{key} = {repr(value)}")

        inputs_block = "\n".join(input_lines)

        wrapper = textwrap.dedent(f"""\
import sys
# Inject structured inputs
{inputs_block}

# User code
{code}

# Output result
if 'result' in dir():
    print(result)
else:
    print("ERROR: No 'result' variable defined", file=sys.stderr)
    sys.exit(1)
""")
        return wrapper

    @staticmethod
    def _sanitize_error(stderr: str) -> str:
        """Remove internal paths and sensitive information from error output."""
        if not stderr:
            return ""

        # Remove absolute file paths
        lines = []
        for line in stderr.splitlines():
            # Remove lines containing internal paths
            if "File \"" in line and ("/app/" in line or "\\app\\" in line):
                line = line.split("File \"")[0] + 'File "<sandbox>"' + line.split('"', 2)[-1] if '"' in line.split("File \"", 1)[1] else line
            # Remove Python installation paths
            if "site-packages" in line:
                continue
            lines.append(line)

        return "\n".join(lines)
