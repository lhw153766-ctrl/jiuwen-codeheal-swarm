"""Unit tests for AST Inspector Tool (Phase 2 - Code Inspector Teammate)."""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest

from jiuwen_codeheal.schemas import (
    ASTContext,
    FaultSignature,
    FaultType,
    PatchStrategy,
)
from jiuwen_codeheal.tools.ast_inspector_tool import (
    ASTInspector,
    FixPolicy,
    compress_context,
    inspect_fault_site,
    propose_fix,
)


@pytest.fixture
def sample_module(tmp_path: Path) -> Path:
    code = '''"""Sample module for AST testing."""
import os
from typing import List


class DataProcessor:
    def process_records(self, items: List[str]) -> int:
        count = len(items)
        return count


def calculate_mean(values: List[float]) -> float:
    """Compute arithmetic mean."""
    total = sum(values)
    return total / len(values)


def find_first(items: List[int]) -> int:
    for i in range(len(items)):
        if items[i + 1] > 0:
            return items[i + 1]
    return 0
'''
    mod_file = tmp_path / "sample.py"
    mod_file.write_text(code, encoding="utf-8")
    return mod_file


def test_inspect_function_node(sample_module: Path):
    inspector = ASTInspector(repo_root=str(sample_module.parent))
    sig = FaultSignature(
        fault_type=FaultType.VALUE_ERROR,
        file_path=str(sample_module),
        line_number=15,
        function_name="calculate_mean",
    )
    ctx = inspector.inspect(sig)
    assert ctx.function is not None
    assert ctx.function.name == "calculate_mean"
    assert "def calculate_mean(values)" in ctx.function.signature
    assert ctx.function.lineno == 12
    assert not ctx.function.is_method
    assert "sum" in ctx.call_chain
    assert "calculate_mean" in ctx.compressed_context


def test_inspect_method_node(sample_module: Path):
    inspector = ASTInspector(repo_root=str(sample_module.parent))
    sig = FaultSignature(
        fault_type=FaultType.ATTRIBUTE_ERROR,
        file_path=str(sample_module),
        line_number=8,
        function_name="process_records",
    )
    ctx = inspector.inspect(sig)
    assert ctx.function is not None
    assert ctx.function.name == "process_records"
    assert ctx.function.is_method
    assert ctx.function.class_name == "DataProcessor"


def test_fix_policy_index_overrun(sample_module: Path):
    inspector = ASTInspector(repo_root=str(sample_module.parent))
    sig = FaultSignature(
        fault_type=FaultType.INDEX_ERROR,
        exception_type="IndexError",
        file_path=str(sample_module),
        line_number=21,
        function_name="find_first",
    )
    ctx = inspector.inspect(sig)
    proposal = FixPolicy().propose(sig, ctx)
    assert proposal.strategy == PatchStrategy.BOUNDARY_GUARD
    assert proposal.confidence >= 0.7
    assert len(proposal.hunks) == 1
    assert "items[i]" in proposal.hunks[0].new
    assert "items[i + 1]" in proposal.hunks[0].old


def test_fix_policy_empty_input_guard(sample_module: Path):
    inspector = ASTInspector(repo_root=str(sample_module.parent))
    sig = FaultSignature(
        fault_type=FaultType.VALUE_ERROR,
        exception_type="ZeroDivisionError",
        file_path=str(sample_module),
        line_number=15,
        function_name="calculate_mean",
    )
    ctx = inspector.inspect(sig)
    proposal = FixPolicy().propose(sig, ctx)
    assert proposal.strategy == PatchStrategy.BOUNDARY_GUARD
    assert "if not values:" in proposal.hunks[0].new
    assert "return 0.0" in proposal.hunks[0].new


def test_context_compression():
    ctx = ASTContext(
        target_file="test.py",
        target_line=10,
        compressed_context="A" * 1000,
    )
    truncated = compress_context(ctx.to_dict(), max_chars=100)
    assert len(truncated) < 200
    assert "truncated" in truncated
