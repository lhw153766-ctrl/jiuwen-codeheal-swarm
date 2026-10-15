"""Unit tests for Skill Evolver Tool (Phase 4 - Skill Evolve & Reporter Teammate)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jiuwen_codeheal.schemas import (
    FailedTest,
    FaultSignature,
    FaultType,
    HealingStatus,
    HealingTrajectory,
    LearnedPattern,
    PatchHunk,
    PatchProposal,
    PatchStrategy,
    StackFrame,
    TraceStep,
    VerificationResult,
    Verdict,
)
from jiuwen_codeheal.tools.skill_evolver_tool import (
    SkillLibrary,
    distill,
    evolve,
    is_trusted,
    lookup_pattern,
    record_healing,
    render_report,
)


@pytest.fixture
def sample_fault() -> FaultSignature:
    return FaultSignature(
        fault_type=FaultType.ASSERTION_ERROR,
        exception_type="AssertionError",
        file_path="src/calc.py",
        line_number=42,
        function_name="compute_discount",
        message="assert compute_discount(100, 0.2) == 80.0",
        failed_tests=[
            FailedTest(
                node_id="tests/test_calc.py::test_discount",
                test_file="tests/test_calc.py",
                test_function="test_discount",
                message="AssertionError",
            )
        ],
        stack_frames=[
            StackFrame(
                file="src/calc.py",
                line=42,
                function="compute_discount",
                code="return price * rate",
            )
        ],
        fingerprint="fp_assert_compute_discount_42",
    )


@pytest.fixture
def sample_trajectory(sample_fault: FaultSignature) -> HealingTrajectory:
    traj = HealingTrajectory(
        run_id="run-test-001",
        repo_path="/tmp/mock_repo",
        mode="mock",
        status=HealingStatus.HEALED,
        fault=sample_fault,
        patches=[
            PatchProposal(
                strategy=PatchStrategy.BOUNDARY_GUARD,
                confidence=0.95,
                summary="Fix discount calculation arithmetic logic",
                hunks=[
                    PatchHunk(
                        file="src/calc.py",
                        old="return price * rate",
                        new="return price * (1.0 - rate)",
                        line_hint=42,
                    )
                ],
            )
        ],
        verification=VerificationResult(
            verdict=Verdict.PASSED,
            sandbox_path="/tmp/mock_sandbox",
            return_code=0,
            tests_total=5,
            tests_passed=5,
            tests_failed=0,
            duration=1.2,
            patch_applied=True,
        ),
        trace=[
            TraceStep(phase="Triage", title="Parsed log", detail="Found 1 fault", ok=True, duration=0.1),
            TraceStep(phase="Verify", title="Verified in sandbox", detail="All green", ok=True, duration=1.2),
        ],
    )
    return traj


def test_is_trusted():
    # Less than 2 occurrences -> not trusted regardless of ratio
    p1 = LearnedPattern(
        fingerprint="fp1",
        fault_type=FaultType.TYPE_ERROR,
        root_cause="NoneType check",
        strategy=PatchStrategy.NONE_CHECK,
        fix_template="if x is None: return",
        occurrences=1,
        success_count=1,
    )
    assert not is_trusted(p1)

    # 2 occurrences, 1 success -> 50% < 60% -> not trusted
    p2 = LearnedPattern(
        fingerprint="fp2",
        fault_type=FaultType.TYPE_ERROR,
        root_cause="NoneType check",
        strategy=PatchStrategy.NONE_CHECK,
        fix_template="if x is None: return",
        occurrences=2,
        success_count=1,
    )
    assert not is_trusted(p2)

    # 3 occurrences, 2 successes -> 66.7% >= 60% -> trusted
    p3 = LearnedPattern(
        fingerprint="fp3",
        fault_type=FaultType.TYPE_ERROR,
        root_cause="NoneType check",
        strategy=PatchStrategy.NONE_CHECK,
        fix_template="if x is None: return",
        occurrences=3,
        success_count=2,
    )
    assert is_trusted(p3)


def test_skill_library_crud(tmp_path: Path, sample_fault: FaultSignature, sample_trajectory: HealingTrajectory):
    skills_dir = tmp_path / "skills"
    lib = SkillLibrary(skills_dir)

    # Non-existent directory returns empty list
    assert lib.load_patterns() == []
    assert lib.find("non_existent") is None

    p = LearnedPattern(
        fingerprint=sample_fault.fingerprint,
        fault_type=sample_fault.fault_type,
        root_cause="Arithmetic logic flaw",
        strategy=PatchStrategy.BOUNDARY_GUARD,
        fix_template="return price * (1.0 - rate)",
        occurrences=1,
        success_count=1,
        example_file="src/calc.py",
    )
    lib.save_patterns([p])

    loaded = lib.load_patterns()
    assert len(loaded) == 1
    assert loaded[0].fingerprint == sample_fault.fingerprint
    assert loaded[0].strategy == PatchStrategy.BOUNDARY_GUARD

    found = lib.find(sample_fault.fingerprint)
    assert found is not None
    assert found.fingerprint == sample_fault.fingerprint

    # Append markdown entry
    lib.append_markdown(sample_trajectory, p)
    assert lib.md_path.is_file()
    md_content = lib.md_path.read_text(encoding="utf-8")
    assert "CI Healing Memory" in md_content
    assert sample_fault.fingerprint in md_content
    assert "HEALED" in md_content


def test_distill(sample_trajectory: HealingTrajectory):
    pattern = distill(sample_trajectory)
    assert pattern is not None
    assert pattern.fingerprint == sample_trajectory.fault.fingerprint
    assert pattern.fault_type == FaultType.ASSERTION_ERROR
    assert pattern.strategy == PatchStrategy.BOUNDARY_GUARD
    assert "return price * (1.0 - rate)" in pattern.fix_template
    assert pattern.occurrences == 1
    assert pattern.success_count == 1

    # Trajectory without fault returns None
    traj_no_fault = sample_trajectory.model_copy(update={"fault": None})
    assert distill(traj_no_fault) is None

    # Failed trajectory sets success_count to 0
    traj_failed = sample_trajectory.model_copy(update={"status": HealingStatus.FAILED_TO_HEAL})
    pattern_failed = distill(traj_failed)
    assert pattern_failed is not None
    assert pattern_failed.success_count == 0


def test_evolve_idempotence_and_accumulation(tmp_path: Path, sample_trajectory: HealingTrajectory):
    skills_dir = tmp_path / "skills"

    # First evolution creates the pattern
    p1 = evolve(sample_trajectory, skills_dir)
    assert p1 is not None
    assert p1.occurrences == 1
    assert p1.success_count == 1

    lib = SkillLibrary(skills_dir)
    patterns = lib.load_patterns()
    assert len(patterns) == 1
    assert patterns[0].occurrences == 1

    # Second evolution of the same fault updates the existing record
    p2 = evolve(sample_trajectory, skills_dir)
    assert p2 is not None
    assert p2.occurrences == 2
    assert p2.success_count == 2

    patterns_updated = lib.load_patterns()
    assert len(patterns_updated) == 1
    assert patterns_updated[0].occurrences == 2
    assert patterns_updated[0].success_count == 2
    assert is_trusted(patterns_updated[0])


def test_render_report(sample_trajectory: HealingTrajectory):
    pattern = distill(sample_trajectory)
    sample_trajectory.learned_pattern = pattern
    report = render_report(sample_trajectory)

    assert "# 自愈报告 · run-test-001" in report
    assert "## 1. 故障感知 (Log Triage)" in report
    assert "## 3. 补丁提案 (Patch & Sandbox Verifier)" in report
    assert "## 4. 沙箱回归验证" in report
    assert "## 5. Skill 自演进" in report
    assert "## 6. 可观测性 Trace" in report
    assert "fp_assert_compute_discount_42" in report


def test_functional_wrappers(tmp_path: Path, sample_trajectory: HealingTrajectory):
    skills_dir = str(tmp_path / "skills")

    # Before recording
    lookup_res = lookup_pattern("unknown_fp", skills_dir)
    assert lookup_res["found"] is False

    # Record healing
    traj_dict = sample_trajectory.model_dump()
    rec_res = record_healing(traj_dict, skills_dir)
    assert rec_res["pattern"] is not None
    assert rec_res["pattern"]["fingerprint"] == "fp_assert_compute_discount_42"

    # Lookup after recording
    lookup_res = lookup_pattern("fp_assert_compute_discount_42", skills_dir)
    assert lookup_res["found"] is True
    assert lookup_res["pattern"]["occurrences"] == 1
