"""Log Parser Tool (Phase 1 - Log Triage Teammate).

A deterministic, dependency-free parser that turns a raw CI build/test log into a
structured :class:`~jiuwen_codeheal.schemas.FaultSignature`.

It handles the formats emitted by the common Python CI toolchain:

* ``pytest`` short test summary + full tracebacks (``-v`` / ``--tb=long``),
* ``flake8`` lint reports (``path:line:col: CODE message``),
* ``mypy`` type-check reports (``path:line: error: message``),
* generic Python tracebacks (``Traceback (most recent call last)``).

The parser is regex + line-state-machine based; it never executes the code under
analysis, so it is safe to run against untrusted CI logs.
"""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Iterable, Optional

from jiuwen_codeheal.schemas import (
    FailedTest,
    FaultSignature,
    FaultType,
    StackFrame,
)

# --------------------------------------------------------------------------- #
# Regex library                                                                #
# --------------------------------------------------------------------------- #

# A pytest short-summary line, e.g.:
#   FAILED tests/test_demo.py::test_binary_search - AssertionError: assert 3 == 4
_PYTEST_SHORT = re.compile(
    r"^(?P<status>FAILED|ERROR)\s+"
    r"(?P<nodeid>[^:\s]+::[^\s]+)"
    r"(?:\s+-\s+(?P<exc>[A-Za-z_][A-Za-z0-9_.]*)(:\s*(?P<msg>.*))?)?\s*$"
)

# A generic "ExceptionType: message" line (also matches bare ExceptionType,
# and pytest traceback lines prefixed with "E   ").
_EXCEPTION_LINE = re.compile(
    r"^(?:E\s+)?(?P<exc>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Timeout|TimeoutError))"
    r"(?::\s*(?P<msg>.*))?$"
)

# File reference inside a traceback frame ("  File "x.py", line 12, in foo").
_FRAME = re.compile(
    r'^\s*File\s+"(?P<file>[^"]+)",\s*line\s+(?P<line>\d+),\s*in\s+(?P<func>.+?)\s*$'
)

# pytest short/long/default traceback headers:
# - "path/to/x.py:12: in func" (tb=short / tb=long)
# - "path/to/x.py:12: IndexError" (default tb failure line)
# - "path/to/x.py:12:" (default tb test site)
_PYTEST_HEADER = re.compile(
    r"^(?P<file>[\w./\\-]+\.py):(?P<line>\d+):(?:\s*(?:in\s+(?P<func>[^:\s]+)|(?P<exc>[A-Za-z_]\w*(?:Error|Exception))))?\s*$"
)

# Source-code line that follows a traceback frame ("    x = foo()").
_SOURCE_LINE = re.compile(r"^\s{4,}(?P<code>.+?)\s*$")

# flake8: path:line:col: CODE message
_FLAKE8 = re.compile(
    r"^(?P<file>[\w./\\-]+\.py):(?P<line>\d+):(?P<col>\d+):\s+"
    r"(?P<code>[EWFC]\d+)\s+(?P<msg>.*)$"
)

# mypy: path:line: error: message  (also path:line: note: ...)
_MYPY = re.compile(
    r"^(?P<file>[\w./\\-]+\.py):(?P<line>\d+):\s+(?P<sev>error|warning|note):\s+(?P<msg>.*)$"
)


_EXCEPTION_TO_FAULT: dict[str, FaultType] = {
    "AssertionError": FaultType.ASSERTION_ERROR,
    "ValueError": FaultType.VALUE_ERROR,
    "ZeroDivisionError": FaultType.VALUE_ERROR,
    "ArithmeticError": FaultType.VALUE_ERROR,
    "OverflowError": FaultType.VALUE_ERROR,
    "FloatingPointError": FaultType.VALUE_ERROR,
    "TypeError": FaultType.TYPE_ERROR,
    "KeyError": FaultType.KEY_ERROR,
    "IndexError": FaultType.INDEX_ERROR,
    "AttributeError": FaultType.ATTRIBUTE_ERROR,
    "NameError": FaultType.NAME_ERROR,
    "ImportError": FaultType.IMPORT_ERROR,
    "ModuleNotFoundError": FaultType.IMPORT_ERROR,
    "SyntaxError": FaultType.SYNTAX_ERROR,
    "TimeoutError": FaultType.TIMEOUT,
}


def _fault_for(exception_type: Optional[str]) -> FaultType:
    if not exception_type:
        return FaultType.UNKNOWN
    return _EXCEPTION_TO_FAULT.get(exception_type, FaultType.UNKNOWN)


def _make_fingerprint(
    fault_type: FaultType,
    file_path: Optional[str],
    function_name: Optional[str],
    exception_type: Optional[str],
) -> str:
    """Stable identity of a bug, independent of line numbers & messages.

    Two failures with the same (type, file, function, exception) collapse to one
    fingerprint, which is exactly what the Skill Evolver needs for dedup.
    """
    basis = "|".join(
        [
            fault_type.value,
            (file_path or "").replace("\\", "/"),
            function_name or "",
            exception_type or "",
        ]
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Parser                                                                       #
# --------------------------------------------------------------------------- #


class LogParser:
    """Stateful log parser. One instance per log."""

    def __init__(self, log_text: str, repo_root: Optional[str] = None) -> None:
        self.log_text = log_text or ""
        self.repo_root = repo_root
        self._lines = self.log_text.splitlines()

    # ------------------------------------------------------------------ #
    def parse(self) -> FaultSignature:
        """Parse the log into a :class:`FaultSignature`."""
        sig = FaultSignature()

        failed_tests = self._parse_pytest_summary()
        sig.failed_tests = failed_tests

        frames, exc_type, exc_msg, fault_line = self._parse_traceback()
        sig.stack_frames = frames
        if exc_type:
            sig.exception_type = exc_type
            sig.message = exc_msg
            sig.fault_type = _fault_for(exc_type)

        # flake8 / mypy reports override when present (lint failures have no tb).
        lint = self._parse_lint()
        if lint and not frames:
            file_path, line_no, msg, code = lint
            sig.file_path = file_path
            sig.line_number = line_no
            sig.message = f"[{code}] {msg}".strip()
            sig.fault_type = FaultType.SYNTAX_ERROR if code.startswith("E9") else FaultType.UNKNOWN
            sig.exception_type = code

        # Resolve the primary fault location: prefer the deepest (last) frame.
        if frames:
            deepest = frames[-1]
            sig.file_path = _relpath(deepest.file, self.repo_root)
            sig.line_number = deepest.line
            sig.function_name = deepest.function
            # If we could not read an exception from a frame, derive from tests.
            if sig.fault_type == FaultType.UNKNOWN and failed_tests:
                first = failed_tests[0]
                if first.message:
                    m = _EXCEPTION_LINE.match(first.message)
                    if m:
                        sig.exception_type = m.group("exc")
                        sig.message = m.group("msg") or first.message
                        sig.fault_type = _fault_for(m.group("exc"))
                # Fall back to the test's own file/line.
                sig.file_path = sig.file_path or first.test_file

        elif failed_tests and not sig.file_path:
            first = failed_tests[0]
            sig.file_path = first.test_file
            sig.function_name = first.test_function
            if first.message:
                m = _EXCEPTION_LINE.match(first.message)
                if m:
                    sig.exception_type = m.group("exc")
                    sig.message = m.group("msg") or first.message
                    sig.fault_type = _fault_for(m.group("exc"))

        # Best-effort line number from the short summary node id is not possible,
        # but we can pull the assertion source line from the captured tb excerpt.
        if sig.line_number is None and fault_line is not None:
            sig.line_number = fault_line

        sig.raw_log_excerpt = "\n".join(self._lines[:60])
        sig.fingerprint = _make_fingerprint(
            sig.fault_type, sig.file_path, sig.function_name, sig.exception_type
        )
        return sig

    # ------------------------------------------------------------------ #
    # Sub-parsers                                                        #
    # ------------------------------------------------------------------ #
    def _parse_pytest_summary(self) -> list[FailedTest]:
        out: list[FailedTest] = []
        for line in self._lines:
            m = _PYTEST_SHORT.match(line.strip())
            if not m:
                continue
            nodeid = m.group("nodeid")
            test_file, _, func = nodeid.partition("::")
            exc = m.group("exc")
            msg = m.group("msg") or ""
            message = f"{exc}: {msg}" if exc else msg
            out.append(
                FailedTest(
                    node_id=nodeid,
                    test_file=_relpath(test_file, self.repo_root),
                    test_function=func,
                    message=message,
                )
            )
        return out

    def _parse_traceback(self) -> tuple[list[StackFrame], Optional[str], str, Optional[int]]:
        frames: list[StackFrame] = []
        exc_type: Optional[str] = None
        exc_msg = ""
        fault_line: Optional[int] = None

        lines = self._lines
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            fm = _FRAME.match(line)
            if not fm:
                fm = _PYTEST_HEADER.match(line.strip())
            if fm:
                file = fm.group("file")
                lineno = int(fm.group("line"))
                func = (fm.groupdict().get("func") or "").strip()
                code = ""
                exc_in_frame = fm.groupdict().get("exc")
                # Look ahead for source line (skip caret lines like ^^^^^)
                j = i + 1
                while j < n and j <= i + 3:
                    cand = lines[j]
                    if _FRAME.match(cand) or _PYTEST_HEADER.match(cand.strip()) or _EXCEPTION_LINE.match(cand.strip()):
                        break
                    sm = _SOURCE_LINE.match(cand)
                    if sm and "^" not in cand:
                        code = sm.group("code")
                        break
                    j += 1
                frames.append(StackFrame(file=file, line=lineno, function=func, code=code))
                if exc_in_frame and not exc_type:
                    exc_type = exc_in_frame
                    fault_line = lineno
                    break
                i += 1
                continue

            em = _EXCEPTION_LINE.match(line.strip())
            if em and frames:
                exc_type = em.group("exc")
                exc_msg = (em.group("msg") or "").strip()
                fault_line = frames[-1].line
                break
            i += 1

        return frames, exc_type, exc_msg, fault_line

    def _parse_lint(self) -> Optional[tuple[str, int, str, str]]:
        for line in self._lines:
            fm = _FLAKE8.match(line.strip())
            if fm:
                return (
                    _relpath(fm.group("file"), self.repo_root),
                    int(fm.group("line")),
                    fm.group("msg").strip(),
                    fm.group("code"),
                )
            mm = _MYPY.match(line.strip())
            if mm and mm.group("sev") == "error":
                return (
                    _relpath(mm.group("file"), self.repo_root),
                    int(mm.group("line")),
                    mm.group("msg").strip(),
                    "mypy",
                )
        return None


# --------------------------------------------------------------------------- #
# Functional wrapper (exposed as an openjiuwen tool)                           #
# --------------------------------------------------------------------------- #


def _relpath(file: str, repo_root: Optional[str]) -> str:
    """Make a path repo-relative when possible (handles CI absolute paths)."""
    if not repo_root:
        return file
    try:
        rel = Path(file).resolve().relative_to(Path(repo_root).resolve())
        return str(rel).replace("\\", "/")
    except Exception:
        # Not under repo_root - keep basename + parent to stay stable.
        return file.replace("\\", "/")


def parse_ci_log(log_text: str, repo_root: Optional[str] = None) -> dict:
    """Parse a CI log and return a serialised :class:`FaultSignature`.

    This is the pure-Python entry point; the openjiuwen ``@tool`` wrapper lives
    in :mod:`jiuwen_codeheal.tools.register` so this module stays import-light.
    """
    signature = LogParser(log_text, repo_root=repo_root).parse()
    return signature.to_dict()


def compute_fingerprint(signature: FaultSignature) -> str:
    """Expose fingerprint computation for the Skill Evolver."""
    return signature.fingerprint


def validate_python_source(source: str) -> Optional[str]:
    """Return an error message if *source* is not valid Python, else ``None``."""
    try:
        ast.parse(source)
        return None
    except SyntaxError as exc:  # pragma: no cover - exercised via inspector
        return f"SyntaxError: {exc.msg} (line {exc.lineno})"
