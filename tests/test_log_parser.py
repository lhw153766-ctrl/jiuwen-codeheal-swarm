"""Unit tests for Log Parser Tool (Phase 1 - Log Triage Teammate)."""

from __future__ import annotations

import pytest

from jiuwen_codeheal.schemas import FaultType
from jiuwen_codeheal.tools.log_parser_tool import (
    LogParser,
    compute_fingerprint,
    parse_ci_log,
)


def test_parse_pytest_short_summary():
    log = """
============================= test session starts =============================
tests/test_math.py::test_add PASSED
tests/test_math.py::test_div FAILED
=========================== short test summary info ===========================
FAILED tests/test_math.py::test_div - ZeroDivisionError: division by zero
========================= 1 failed, 1 passed in 0.05s =========================
"""
    sig = LogParser(log).parse()
    assert len(sig.failed_tests) == 1
    assert sig.failed_tests[0].node_id == "tests/test_math.py::test_div"
    assert sig.failed_tests[0].test_file == "tests/test_math.py"
    assert sig.failed_tests[0].test_function == "test_div"
    assert "ZeroDivisionError" in sig.failed_tests[0].message
    assert sig.fault_type == FaultType.VALUE_ERROR
    assert sig.exception_type == "ZeroDivisionError"


def test_parse_pytest_tb_short():
    log = """
================================== FAILURES ===================================
________________________________ test_find_max ________________________________
tests/test_calc.py:18: in test_find_max
    assert find_max([1, 5, 3]) == 5
calc.py:22: in find_max
    if seq[i + 1] > best:
E   IndexError: list index out of range
=========================== short test summary info ===========================
FAILED tests/test_calc.py::test_find_max - IndexError: list index out of range
"""
    sig = LogParser(log).parse()
    assert sig.fault_type == FaultType.INDEX_ERROR
    assert sig.exception_type == "IndexError"
    assert sig.file_path == "calc.py"
    assert sig.line_number == 22
    assert sig.function_name == "find_max"
    assert len(sig.stack_frames) == 2


def test_parse_cpython_traceback():
    log = """
Traceback (most recent call last):
  File "app/service.py", line 45, in process_item
    val = data["missing_key"]
KeyError: 'missing_key'
"""
    sig = LogParser(log).parse()
    assert sig.fault_type == FaultType.KEY_ERROR
    assert sig.exception_type == "KeyError"
    assert sig.file_path == "app/service.py"
    assert sig.line_number == 45
    assert sig.function_name == "process_item"


def test_parse_flake8_report():
    log = """
src/core/parser.py:42:1: E999 SyntaxError: invalid syntax
src/core/parser.py:50:80: E501 line too long (82 > 79 characters)
"""
    sig = LogParser(log).parse()
    assert sig.fault_type == FaultType.SYNTAX_ERROR
    assert sig.file_path == "src/core/parser.py"
    assert sig.line_number == 42
    assert "[E999]" in sig.message


def test_parse_mypy_report():
    log = """
pkg/calc.py:12: error: Argument 1 to "sqrt" has incompatible type "str"; expected "float"
Found 1 error in 1 file (checked 3 source files)
"""
    sig = LogParser(log).parse()
    assert sig.file_path == "pkg/calc.py"
    assert sig.line_number == 12
    assert "incompatible type" in sig.message


def test_fingerprint_deterministic_stability():
    sig1_dict = parse_ci_log(
        "FAILED tests/test_foo.py::test_bar - IndexError: out of range\nFile 'calc.py', line 10, in find\nx = a[100]\nIndexError: out of range"
    )
    sig2_dict = parse_ci_log(
        "FAILED tests/test_foo.py::test_bar - IndexError: out of range\nFile 'calc.py', line 10, in find\nx = a[100]\nIndexError: out of range"
    )
    assert sig1_dict["fingerprint"] != ""
    assert sig1_dict["fingerprint"] == sig2_dict["fingerprint"]
