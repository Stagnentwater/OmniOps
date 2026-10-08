"""Comprehensive tests for Calculation Sandbox (V15-SANDBOX-001).

Test categories:
1. Code Validator — allowlist, blocklist, size limits
2. Mandatory Security Tests — all blocked constructs from spec
3. Subprocess Sandbox — execution, timeout, empty env
4. Calculation Detector — pattern matching
5. Calculation Models — data model correctness
6. Calculation Service — end-to-end pipeline
7. Calculation Correctness — real math calculations
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from calculation.validator import CodeValidator, ValidationResult, ALLOWED_MODULES
from calculation.detector import CalculationDetector
from calculation.models import (
    CalculationRequest,
    CalculationResult,
    CalculationAudit,
    create_audit,
)
from calculation.subprocess_sandbox import SubprocessSandboxProvider
from calculation.service import CalculationService


# =====================================================================
# 1. Code Validator Tests
# =====================================================================

class TestCodeValidatorAllowedCode(unittest.TestCase):
    """Test that valid code passes validation."""

    def setUp(self) -> None:
        self.validator = CodeValidator()

    def test_simple_arithmetic(self) -> None:
        result = self.validator.validate("result = 2 + 3")
        self.assertTrue(result.valid, result.reason)

    def test_math_import(self) -> None:
        code = "import math\nresult = math.sqrt(16)"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)

    def test_statistics_import(self) -> None:
        code = "import statistics\nresult = statistics.mean([1, 2, 3])"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)

    def test_decimal_import(self) -> None:
        code = "from decimal import Decimal\nresult = Decimal('1.1') + Decimal('2.2')"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)

    def test_fractions_import(self) -> None:
        code = "from fractions import Fraction\nresult = Fraction(1, 3)"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)

    def test_datetime_import(self) -> None:
        code = "import datetime\nresult = str(datetime.date.today())"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)

    def test_variable_assignment(self) -> None:
        code = "x = 10\ny = 20\nresult = x + y"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)

    def test_function_definition(self) -> None:
        code = "def add(a, b):\n    return a + b\nresult = add(3, 4)"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)

    def test_list_comprehension(self) -> None:
        code = "result = sum([x**2 for x in range(10)])"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)

    def test_conditional(self) -> None:
        code = "x = 5\nresult = 'high' if x > 3 else 'low'"
        result = self.validator.validate(code)
        self.assertTrue(result.valid, result.reason)


class TestCodeValidatorSizeLimits(unittest.TestCase):
    """Test code size enforcement."""

    def test_empty_code(self) -> None:
        result = CodeValidator().validate("")
        self.assertFalse(result.valid)
        self.assertIn("Empty", result.reason)

    def test_too_many_lines(self) -> None:
        code = "\n".join([f"x_{i} = {i}" for i in range(150)])
        result = CodeValidator().validate(code)
        self.assertFalse(result.valid)
        self.assertIn("line limit", result.reason)

    def test_too_many_bytes(self) -> None:
        code = "x = " + "1" * 15000
        result = CodeValidator().validate(code)
        self.assertFalse(result.valid)
        self.assertIn("byte limit", result.reason)

    def test_syntax_error(self) -> None:
        result = CodeValidator().validate("def foo(")
        self.assertFalse(result.valid)
        self.assertIn("Syntax error", result.reason)


# =====================================================================
# 2. MANDATORY Security Tests (from spec Section 28)
# =====================================================================

class TestMandatorySecurityBlocks(unittest.TestCase):
    """Mandatory security tests: sandbox code must NOT be able to use these."""

    def setUp(self) -> None:
        self.validator = CodeValidator()

    def test_block_import_os(self) -> None:
        result = self.validator.validate("import os")
        self.assertFalse(result.valid)
        self.assertIn("os", result.reason)

    def test_block_import_subprocess(self) -> None:
        result = self.validator.validate("import subprocess")
        self.assertFalse(result.valid)
        self.assertIn("subprocess", result.reason)

    def test_block_import_socket(self) -> None:
        result = self.validator.validate("import socket")
        self.assertFalse(result.valid)
        self.assertIn("socket", result.reason)

    def test_block_open_env(self) -> None:
        result = self.validator.validate('open(".env")')
        self.assertFalse(result.valid)
        self.assertIn("open", result.reason)

    def test_block_open_etc_passwd(self) -> None:
        result = self.validator.validate('open("/etc/passwd")')
        self.assertFalse(result.valid)
        self.assertIn("open", result.reason)

    def test_block_dunder_import(self) -> None:
        result = self.validator.validate('__import__("os")')
        self.assertFalse(result.valid)
        self.assertIn("__import__", result.reason)

    def test_block_eval(self) -> None:
        result = self.validator.validate('eval("1+1")')
        self.assertFalse(result.valid)
        self.assertIn("eval", result.reason)

    def test_block_exec(self) -> None:
        result = self.validator.validate('exec("print(1)")')
        self.assertFalse(result.valid)
        self.assertIn("exec", result.reason)

    def test_block_import_requests(self) -> None:
        result = self.validator.validate("import requests")
        self.assertFalse(result.valid)

    def test_block_import_ctypes(self) -> None:
        result = self.validator.validate("import ctypes")
        self.assertFalse(result.valid)

    def test_block_import_sys(self) -> None:
        result = self.validator.validate("import sys")
        self.assertFalse(result.valid)

    def test_block_import_io(self) -> None:
        result = self.validator.validate("import io")
        self.assertFalse(result.valid)

    def test_block_import_pathlib(self) -> None:
        result = self.validator.validate("import pathlib")
        self.assertFalse(result.valid)

    def test_block_import_shutil(self) -> None:
        result = self.validator.validate("import shutil")
        self.assertFalse(result.valid)

    def test_block_import_pickle(self) -> None:
        result = self.validator.validate("import pickle")
        self.assertFalse(result.valid)

    def test_block_import_multiprocessing(self) -> None:
        result = self.validator.validate("import multiprocessing")
        self.assertFalse(result.valid)

    def test_block_import_threading(self) -> None:
        result = self.validator.validate("import threading")
        self.assertFalse(result.valid)

    def test_block_import_asyncio(self) -> None:
        result = self.validator.validate("import asyncio")
        self.assertFalse(result.valid)

    def test_block_import_urllib(self) -> None:
        result = self.validator.validate("import urllib")
        self.assertFalse(result.valid)

    def test_block_import_marshal(self) -> None:
        result = self.validator.validate("import marshal")
        self.assertFalse(result.valid)

    def test_block_import_importlib(self) -> None:
        result = self.validator.validate("import importlib")
        self.assertFalse(result.valid)

    def test_block_getattr(self) -> None:
        result = self.validator.validate("getattr(object, 'name')")
        self.assertFalse(result.valid)

    def test_block_setattr(self) -> None:
        result = self.validator.validate("setattr(object, 'name', 1)")
        self.assertFalse(result.valid)

    def test_block_delattr(self) -> None:
        result = self.validator.validate("delattr(object, 'name')")
        self.assertFalse(result.valid)

    def test_block_globals(self) -> None:
        result = self.validator.validate("globals()")
        self.assertFalse(result.valid)

    def test_block_locals(self) -> None:
        result = self.validator.validate("locals()")
        self.assertFalse(result.valid)

    def test_block_compile(self) -> None:
        result = self.validator.validate("compile('1+1', '<string>', 'eval')")
        self.assertFalse(result.valid)

    def test_block_dunder_access(self) -> None:
        result = self.validator.validate("x.__class__")
        self.assertFalse(result.valid)
        self.assertIn("__class__", result.reason)

    def test_block_dunder_dict(self) -> None:
        result = self.validator.validate("x.__dict__")
        self.assertFalse(result.valid)

    def test_block_dunder_builtins(self) -> None:
        result = self.validator.validate("x.__builtins__")
        self.assertFalse(result.valid)

    def test_block_relative_import(self) -> None:
        result = self.validator.validate("from . import something")
        self.assertFalse(result.valid)
        self.assertIn("Relative", result.reason)

    def test_block_from_os_import(self) -> None:
        result = self.validator.validate("from os import getcwd")
        self.assertFalse(result.valid)

    def test_block_from_subprocess_import(self) -> None:
        result = self.validator.validate("from subprocess import run")
        self.assertFalse(result.valid)


# =====================================================================
# 3. Subprocess Sandbox Tests
# =====================================================================

class TestSubprocessSandbox(unittest.TestCase):
    """Test subprocess sandbox execution."""

    def setUp(self) -> None:
        self.sandbox = SubprocessSandboxProvider()

    def test_simple_calculation(self) -> None:
        result = self.sandbox.execute("result = 2 + 3", inputs={})
        self.assertTrue(result.success)
        self.assertEqual(result.result, "5")
        self.assertEqual(result.exit_code, 0)

    def test_with_inputs(self) -> None:
        result = self.sandbox.execute(
            "result = x * y",
            inputs={"x": 6, "y": 7},
        )
        self.assertTrue(result.success)
        self.assertEqual(result.result, "42")

    def test_float_calculation(self) -> None:
        result = self.sandbox.execute(
            "result = round((fahrenheit - 32) * 5 / 9, 2)",
            inputs={"fahrenheit": 350.0},
        )
        self.assertTrue(result.success)
        self.assertEqual(result.result, "176.67")

    def test_timeout(self) -> None:
        result = self.sandbox.execute(
            "import time\ntime.sleep(10)\nresult = 1",
            inputs={},
            timeout_seconds=1.0,
        )
        self.assertFalse(result.success)
        self.assertIn("timed out", result.error)

    def test_no_result_variable(self) -> None:
        result = self.sandbox.execute("x = 42", inputs={})
        self.assertFalse(result.success)
        self.assertNotEqual(result.exit_code, 0)

    def test_runtime_error(self) -> None:
        result = self.sandbox.execute("result = 1 / 0", inputs={})
        self.assertFalse(result.success)
        self.assertIn("ZeroDivision", result.error)

    def test_execution_time_recorded(self) -> None:
        result = self.sandbox.execute("result = 1 + 1", inputs={})
        self.assertGreater(result.execution_time_ms, 0.0)

    def test_provider_name(self) -> None:
        self.assertIn("Subprocess", self.sandbox.name())


# =====================================================================
# 4. Calculation Detector Tests
# =====================================================================

class TestCalculationDetector(unittest.TestCase):
    """Test calculation detection patterns."""

    def setUp(self) -> None:
        self.detector = CalculationDetector()

    def test_detect_calculate_keyword(self) -> None:
        r = self.detector.detect("Calculate the pressure drop")
        self.assertTrue(r.needs_calculation)

    def test_detect_convert_keyword(self) -> None:
        r = self.detector.detect("Convert 350°F to Celsius")
        self.assertTrue(r.needs_calculation)

    def test_detect_percentage(self) -> None:
        r = self.detector.detect("What is 20% higher than the flow rate?")
        self.assertTrue(r.needs_calculation)

    def test_detect_compute(self) -> None:
        r = self.detector.detect("Compute the remaining bearing life")
        self.assertTrue(r.needs_calculation)

    def test_detect_formula(self) -> None:
        r = self.detector.detect("Apply the formula for pressure drop")
        self.assertTrue(r.needs_calculation)

    def test_detect_sum_of(self) -> None:
        r = self.detector.detect("What is the sum of all readings?")
        self.assertTrue(r.needs_calculation)

    def test_no_calculation_retrieval(self) -> None:
        r = self.detector.detect("What pressure is reported in the document?")
        self.assertFalse(r.needs_calculation)

    def test_no_calculation_explanation(self) -> None:
        r = self.detector.detect("Explain why pressure increased")
        self.assertFalse(r.needs_calculation)

    def test_no_calculation_lookup(self) -> None:
        r = self.detector.detect("Show me the maintenance history for Pump P-301")
        self.assertFalse(r.needs_calculation)

    def test_empty_query(self) -> None:
        r = self.detector.detect("")
        self.assertFalse(r.needs_calculation)

    def test_detection_has_confidence(self) -> None:
        r = self.detector.detect("Calculate 2 + 2")
        self.assertGreater(r.confidence, 0.0)


# =====================================================================
# 5. Data Model Tests
# =====================================================================

class TestCalculationModels(unittest.TestCase):
    """Test calculation data models."""

    def test_request_frozen(self) -> None:
        req = CalculationRequest(
            query="test", inputs={}, units={}, generated_code="result = 1",
        )
        with self.assertRaises(AttributeError):
            req.query = "changed"  # type: ignore[misc]

    def test_result_frozen(self) -> None:
        res = CalculationResult(
            success=True, result="42", error="", exit_code=0, execution_time_ms=1.0,
        )
        with self.assertRaises(AttributeError):
            res.result = "changed"  # type: ignore[misc]

    def test_create_audit(self) -> None:
        req = CalculationRequest(
            query="test", inputs={"x": 1}, units={}, generated_code="result = x",
        )
        res = CalculationResult(
            success=True, result="1", error="", exit_code=0, execution_time_ms=5.0,
        )
        audit = create_audit(
            request=req,
            result=res,
            model_used="llama3.2",
            sandbox_provider="test",
            validation_passed=True,
        )
        self.assertIsInstance(audit, CalculationAudit)
        self.assertEqual(audit.query, "test")
        self.assertEqual(audit.result, "1")
        self.assertTrue(audit.validation_passed)
        self.assertIn("T", audit.timestamp)  # ISO format


# =====================================================================
# 6. Calculation Service Tests
# =====================================================================

class TestCalculationService(unittest.TestCase):
    """Test the calculation service pipeline."""

    def test_valid_code_executes(self) -> None:
        service = CalculationService()
        request = CalculationRequest(
            query="What is 2 + 3?",
            inputs={},
            units={},
            generated_code="result = 2 + 3",
        )
        result, audit = service.execute_calculation(request)
        self.assertTrue(result.success)
        self.assertEqual(result.result, "5")
        self.assertTrue(audit.validation_passed)

    def test_blocked_code_rejected(self) -> None:
        service = CalculationService()
        request = CalculationRequest(
            query="hack attempt",
            inputs={},
            units={},
            generated_code='import os\nresult = os.getcwd()',
        )
        result, audit = service.execute_calculation(request)
        self.assertFalse(result.success)
        self.assertFalse(audit.validation_passed)
        self.assertIn("validation failed", result.error)

    def test_runtime_error_handled(self) -> None:
        service = CalculationService()
        request = CalculationRequest(
            query="divide by zero",
            inputs={},
            units={},
            generated_code="result = 1 / 0",
        )
        result, audit = service.execute_calculation(request)
        self.assertFalse(result.success)
        self.assertTrue(audit.validation_passed)  # Code was valid Python
        self.assertIn("ZeroDivision", result.error)

    def test_audit_always_created(self) -> None:
        service = CalculationService()
        request = CalculationRequest(
            query="test", inputs={}, units={}, generated_code="result = 1",
        )
        _, audit = service.execute_calculation(request)
        self.assertIsNotNone(audit.timestamp)
        self.assertIsNotNone(audit.sandbox_provider)


# =====================================================================
# 7. Calculation Correctness Tests
# =====================================================================

class TestCalculationCorrectness(unittest.TestCase):
    """Verify actual calculations produce correct results."""

    def setUp(self) -> None:
        self.sandbox = SubprocessSandboxProvider()

    def test_fahrenheit_to_celsius(self) -> None:
        result = self.sandbox.execute(
            "result = round((fahrenheit - 32) * 5 / 9, 2)",
            inputs={"fahrenheit": 350.0},
        )
        self.assertTrue(result.success)
        self.assertEqual(float(result.result), 176.67)

    def test_percentage_increase(self) -> None:
        result = self.sandbox.execute(
            "result = round(value * (1 + percent / 100), 2)",
            inputs={"value": 100.0, "percent": 20.0},
        )
        self.assertTrue(result.success)
        self.assertEqual(float(result.result), 120.0)

    def test_pressure_drop_formula(self) -> None:
        code = """\
import math
# Darcy-Weisbach simplified
friction_factor = 0.02
velocity = flow_rate / (math.pi * (diameter/2)**2)
pressure_drop = friction_factor * (length / diameter) * (0.5 * density * velocity**2)
result = round(pressure_drop, 2)
"""
        result = self.sandbox.execute(code, inputs={
            "flow_rate": 0.05,
            "diameter": 0.1,
            "length": 50.0,
            "density": 1000.0,
        })
        self.assertTrue(result.success, result.error)
        self.assertGreater(float(result.result), 0.0)

    def test_statistical_mean(self) -> None:
        result = self.sandbox.execute(
            "import statistics\nresult = statistics.mean(values)",
            inputs={"values": [10, 20, 30, 40, 50]},
        )
        self.assertTrue(result.success)
        self.assertEqual(float(result.result), 30.0)

    def test_bearing_life_calculation(self) -> None:
        code = """\
# L10 bearing life formula (simplified)
# L10 = (C / P) ^ p * 10^6 / (60 * n)
C = dynamic_capacity  # Dynamic load rating (N)
P = equivalent_load    # Equivalent dynamic load (N)
n = rpm               # Rotational speed
p = 3                 # Ball bearing exponent
L10_revolutions = (C / P) ** p * 1e6
L10_hours = L10_revolutions / (60 * n)
result = round(L10_hours, 1)
"""
        result = self.sandbox.execute(code, inputs={
            "dynamic_capacity": 25000.0,
            "equivalent_load": 5000.0,
            "rpm": 1500.0,
        })
        self.assertTrue(result.success, result.error)
        self.assertGreater(float(result.result), 0.0)


if __name__ == "__main__":
    unittest.main()
