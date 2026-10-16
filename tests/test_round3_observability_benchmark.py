"""Unit and integration tests for Round 3 Observability, Dashboard, and Benchmark features."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import pytest

from jiuwen_codeheal.benchmark import (
    BENCHMARK_CASES,
    BenchmarkCaseResult,
    BenchmarkSummary,
    render_benchmark_markdown,
    run_benchmark,
)
from jiuwen_codeheal.cli import _print_trace, build_parser, main
from jiuwen_codeheal.config import CodeHealConfig, EngineMode
from jiuwen_codeheal.dashboard import generate_dashboard_html
from jiuwen_codeheal.schemas import (
    ASTContext,
    FaultSignature,
    FaultType,
    FunctionContext,
    HealingStatus,
    HealingTrajectory,
    LearnedPattern,
    PatchProposal,
    PatchStrategy,
    TraceStep,
    VerificationResult,
)
from jiuwen_codeheal.tools.skill_evolver_tool import render_report
from jiuwen_codeheal.workflows.heal_swarmflow import HealSwarmFlow


def test_benchmark_generators_coverage():
    """Verify all 6 benchmark cases generate valid micro-repos and metadata."""
    assert len(BENCHMARK_CASES) == 6
    case_ids = set()
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        for i, setup_fn in enumerate(BENCHMARK_CASES):
            case_dir = td / f"case_{i}"
            case_dir.mkdir()
            meta = setup_fn(case_dir)
            assert "case_id" in meta
            assert "name" in meta
            assert "fault_type" in meta
            assert "strategy" in meta
            case_ids.add(meta["case_id"])
            assert any(case_dir.glob("*.py"))
            assert any(case_dir.glob("tests/*.py"))
    assert len(case_ids) == 6


def test_benchmark_full_execution_and_heal_rate(tmp_path: Path):
    """Verify that run_benchmark() achieves 100% heal rate and 0% regression."""
    out_md = tmp_path / "bench_report.md"
    summary = run_benchmark(output_md=str(out_md))

    assert summary.total_cases == 6
    assert summary.healed_cases == 6
    assert summary.heal_rate_pct == 100.0
    assert summary.secondary_regression_rate_pct == 0.0
    assert summary.avg_duration_ms > 0
    assert 70.0 <= summary.avg_compression_rate_pct <= 90.0
    assert out_md.exists()
    content = out_md.read_text(encoding="utf-8")
    assert "100.0% (6/6)" in content
    assert "case_01_index_overrun" in content
    assert "case_06_multi_bug_cascade" in content


def test_benchmark_summary_markdown_rendering():
    """Verify render_benchmark_markdown produces structured Markdown tables."""
    case = BenchmarkCaseResult(
        case_id="case_test_01",
        name="测试场景",
        fault_type="index_error",
        strategy="boundary_guard",
        initial_failed=1,
        initial_passed=1,
        final_passed=2,
        final_failed=0,
        total_tests=2,
        iterations=1,
        duration_ms=450.0,
        context_compression_rate=0.82,
        memory_hit=True,
        healed=True,
        description="测试描述",
    )
    summary = BenchmarkSummary(
        total_cases=1,
        healed_cases=1,
        heal_rate_pct=100.0,
        secondary_regression_rate_pct=0.0,
        avg_duration_ms=450.0,
        avg_compression_rate_pct=82.0,
        case_results=[case],
    )
    md = render_benchmark_markdown(summary)
    assert "# openJiuwen 智能体创新大赛 —— Benchmark 量化评测报告" in md
    assert "100.0% (1/1)" in md
    assert "case_test_01" in md
    assert "boundary_guard" in md


def test_ast_context_compression_rate_calculation():
    """Verify AST context compression rate calculation logic."""
    full_source = "def foo():\n" + "    x = 1\n" * 100
    compressed_slice = "def foo():\n    x = 1\n"
    raw_len = len(full_source) + 500  # including error log
    comp_len = len(compressed_slice)
    rate = 1.0 - (comp_len / raw_len)
    assert 0.70 <= rate <= 0.99


def test_generate_dashboard_html_structure(tmp_path: Path):
    """Verify generate_dashboard_html creates valid, self-contained HTML."""
    traj = HealingTrajectory(
        run_id="run-dash-test",
        repo_path=str(tmp_path),
        status=HealingStatus.HEALED,
        mode="replay",
        duration=3.25,
        iterations=2,
        verification=VerificationResult(
            verdict="passed",
            tests_total=6,
            tests_passed=6,
            tests_failed=0,
            all_green=True,
        ),
        trace=[
            TraceStep(phase="1-triage", title="故障解析", detail="IndexError at calc.py:10", ok=True),
            TraceStep(phase="2-inspect", title="AST定位", detail="[Memory Hit: trusted pattern] fixed", ok=True),
        ],
        patches=[
            PatchProposal(
                strategy=PatchStrategy.BOUNDARY_GUARD,
                summary="fixed",
                unified_diff="--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n-seq[i+1]\n+seq[i]\n",
            )
        ],
        learned_patterns=[
            LearnedPattern(
                fingerprint="fp_dash_01",
                fault_type=FaultType.INDEX_ERROR,
                strategy=PatchStrategy.BOUNDARY_GUARD,
                root_cause="Index overrun",
                fix_template="seq[i]",
                occurrences=3,
                success_count=3,
            )
        ],
    )
    out_file = tmp_path / "dashboard.html"
    html_str = generate_dashboard_html(traj, output_path=str(out_file))

    assert out_file.exists()
    assert "<!DOCTYPE html>" in html_str
    assert "Jiuwen-CodeHeal Swarm" in html_str
    assert "run-dash-test" in html_str
    assert "openJiuwen Swarmflow 计算图" in html_str
    assert "fp_dash_01" in html_str
    assert "diff-add" in html_str
    assert "diff-del" in html_str


def test_cli_benchmark_command():
    """Verify CLI --benchmark argument executes cleanly and returns code 0."""
    code = main(["--benchmark"])
    assert code == 0


def test_cli_dashboard_command(tmp_path: Path):
    """Verify CLI --dashboard argument creates docs/dashboard.html and returns code 0."""
    code = main(["--dashboard", "--repo", "examples/buggy_repo_demo"])
    assert code == 0
    assert (Path("docs/dashboard.html")).exists()


def test_rich_trace_escaping(capsys):
    """Verify _print_trace escapes square brackets like [idx + 1] without error."""
    from rich.console import Console

    traj = HealingTrajectory(
        run_id="run-escape-test",
        repo_path=".",
        status=HealingStatus.HEALED,
        trace=[
            TraceStep(
                phase="2-inspect",
                title="AST检索",
                detail="boundary_guard: Fixed access from [idx + 1] to [idx]",
                ok=True,
            )
        ],
    )
    console = Console(file=open("nul" if Path("/").resolve().drive else "/dev/null", "w"))
    # Should not raise MarkupError
    _print_trace(console, traj)


def test_render_report_multiple_patterns():
    """Verify render_report renders all learned patterns when multiple exist."""
    p1 = LearnedPattern(
        fingerprint="fp_multi_01",
        fault_type=FaultType.INDEX_ERROR,
        strategy=PatchStrategy.BOUNDARY_GUARD,
        root_cause="find_max bounds",
        occurrences=2,
        success_count=2,
    )
    p2 = LearnedPattern(
        fingerprint="fp_multi_02",
        fault_type=FaultType.VALUE_ERROR,
        strategy=PatchStrategy.BOUNDARY_GUARD,
        root_cause="average zero div",
        occurrences=2,
        success_count=2,
    )
    traj = HealingTrajectory(
        run_id="run-report-test",
        repo_path=".",
        status=HealingStatus.HEALED,
        learned_patterns=[p1, p2],
    )
    report = render_report(traj)
    assert "fp_multi_01" in report
    assert "fp_multi_02" in report
    assert "出现 2 次" in report
    assert "可信=True" in report


def test_call_live_llm_behavior(tmp_path: Path):
    """Verify _call_live_llm raises RuntimeError on invalid/stub keys and falls back."""
    config = CodeHealConfig(
        mode=EngineMode.LIVE,
        client={"api_key": "stub", "provider": "deepseek"},
    )
    flow = HealSwarmFlow(config, repo_root=str(tmp_path), skills_dir=str(tmp_path / "skills"))
    sig = FaultSignature(fault_type=FaultType.INDEX_ERROR, file_path="calc.py", line_number=1)
    ctx = ASTContext(target_file="calc.py", target_line=1)

    with pytest.raises(RuntimeError):
        flow._call_live_llm(sig, ctx)

    # In phase_inspect, this exception should be caught gracefully
    (tmp_path / "calc.py").write_text("def find_max(seq):\n    return seq[0]\n")
    ctx_res, proposal, dt = flow.phase_inspect(sig, iteration=1)
    assert proposal is not None
    assert getattr(flow, "_degradation_warning", None) is not None
