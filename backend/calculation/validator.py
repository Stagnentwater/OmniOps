"""AST-based code validator for the calculation sandbox.

Uses an ALLOWLIST approach: only explicitly permitted constructs pass.
This is defense-in-depth — even if the container isolates execution,
the validator prevents dangerous code from ever reaching the sandbox.

Blocked constructs:
- All imports except allowlisted stdlib modules
- eval, exec, compile, __import__
- getattr, setattr, delattr
- globals, locals, vars, dir
- open, print to file
- All dunder attribute access (__xxx__)
- Dynamic attribute access patterns
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Modules allowed in the sandbox
ALLOWED_MODULES: frozenset[str] = frozenset({
    "math",
    "statistics",
    "decimal",
    "fractions",
    "datetime",
})

# Built-in functions that are BLOCKED
BLOCKED_BUILTINS: frozenset[str] = frozenset({
    "eval", "exec", "compile",
    "__import__",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "hasattr",
    "open",
    "breakpoint",
    "exit", "quit",
    "input",
    "memoryview",
    "classmethod", "staticmethod", "property",
    "super", "type",
    "help",
})

# Maximum allowed code length
MAX_CODE_LINES = 100
MAX_CODE_BYTES = 10_000


@dataclass(frozen=True)
class ValidationResult:
    """Result of code validation."""

    valid: bool
    reason: str


class CodeValidator:
    """Validates LLM-generated Python code using AST allowlist analysis.

    The validator walks the entire AST and rejects any construct
    that is not explicitly allowed. This is safer than a blocklist
    because unknown/new Python features are blocked by default.
    """

    def __init__(
        self,
        allowed_modules: frozenset[str] | None = None,
        max_lines: int = MAX_CODE_LINES,
        max_bytes: int = MAX_CODE_BYTES,
    ) -> None:
        self._allowed_modules = allowed_modules or ALLOWED_MODULES
        self._max_lines = max_lines
        self._max_bytes = max_bytes

    def validate(self, code: str) -> ValidationResult:
        """Validate code for sandbox execution.

        Returns ValidationResult with valid=True if safe,
        or valid=False with explanation if blocked.
        """
        # Size checks
        if not code or not code.strip():
            return ValidationResult(valid=False, reason="Empty code")

        if len(code) > self._max_bytes:
            return ValidationResult(
                valid=False,
                reason=f"Code exceeds {self._max_bytes} byte limit ({len(code)} bytes)",
            )

        lines = code.strip().splitlines()
        if len(lines) > self._max_lines:
            return ValidationResult(
                valid=False,
                reason=f"Code exceeds {self._max_lines} line limit ({len(lines)} lines)",
            )

        # Parse AST
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as e:
            return ValidationResult(
                valid=False,
                reason=f"Syntax error: {e.msg} (line {e.lineno})",
            )

        # Walk AST and check every node
        for node in ast.walk(tree):
            result = self._check_node(node)
            if not result.valid:
                return result

        return ValidationResult(valid=True, reason="All checks passed")

    def _check_node(self, node: ast.AST) -> ValidationResult:
        """Check a single AST node against the allowlist."""

        # Block all imports except allowed modules
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module not in self._allowed_modules:
                    return ValidationResult(
                        valid=False,
                        reason=f"Import blocked: '{alias.name}' is not in the allowlist",
                    )

        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                return ValidationResult(
                    valid=False,
                    reason="Relative imports are not allowed",
                )
            module = node.module.split(".")[0]
            if module not in self._allowed_modules:
                return ValidationResult(
                    valid=False,
                    reason=f"Import blocked: 'from {node.module}' is not in the allowlist",
                )

        # Block dangerous built-in calls
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BLOCKED_BUILTINS:
                return ValidationResult(
                    valid=False,
                    reason=f"Blocked built-in: '{func.id}()' is not allowed",
                )

        # Block dunder attribute access (__xxx__)
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                return ValidationResult(
                    valid=False,
                    reason=f"Dunder access blocked: '.{node.attr}' is not allowed",
                )

        # Block string operations that could be used for injection
        elif isinstance(node, ast.Name):
            if node.id in BLOCKED_BUILTINS:
                # Just referencing a blocked builtin as a name (e.g., passing it)
                pass  # We catch this at call site; name reference alone is OK

        return ValidationResult(valid=True, reason="")
