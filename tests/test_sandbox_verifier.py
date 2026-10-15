"""Unit tests for Sandbox Verifier Tool (Phase 3 - Patch & Sandbox Verifier Teammate)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jiuwen_codeheal.schemas import PatchHunk, PatchProposal, PatchStrategy, Verdict
from jiuwen_codeheal.tools.sandbox_verifier_tool import (
    Sandbox,
    SecurityError,
    apply_patch,
    check_whitelist,
    run_pytest,
    verify_patch,
)


@pytest.fixture
def dummy_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mini_repo"
    repo.mkdir()
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text(
        "import sys\nfrom calc import add\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    return repo


def test_sandbox_isolation(dummy_repo: Path):
    with Sandbox(str(dummy_repo), keep=False) as sb:
        assert sb.root is not None
        assert sb.root.is_dir()
        assert (sb.root / "calc.py").is_file()
        sb_path = sb.root
    # After exiting with keep=False, temporary sandbox should be deleted
    assert not sb_path.exists()


def test_sandbox_security_whitelist(dummy_repo: Path):
    with Sandbox(str(dummy_repo)) as sb:
        # Whitelisted internal file
        target = sb.resolve("calc.py")
        assert target.is_file()

        # Path traversal escape attempt must be rejected
        with pytest.raises(SecurityError):
            sb.resolve("../../etc/passwd")

        with pytest.raises(SecurityError):
            sb.resolve("C:/Windows/System32/cmd.exe")


def test_check_whitelist_tool(dummy_repo: Path):
    res_ok = check_whitelist(str(dummy_repo), "calc.py")
    assert res_ok["allowed"] is True

    res_bad = check_whitelist(str(dummy_repo), "../outside.py")
    assert res_bad["allowed"] is False
    assert "escapes the sandbox" in res_bad["reason"]


def test_apply_patch_atomic_rollback(dummy_repo: Path):
    with Sandbox(str(dummy_repo)) as sb:
        original = sb.abs_read("calc.py")
        bad_patch = PatchProposal(
            strategy=PatchStrategy.BOUNDARY_GUARD,
            hunks=[
                PatchHunk(file="calc.py", old="def non_existent():\n    pass", new=""),
            ],
        )
        applied = apply_patch(sb, bad_patch)
        assert applied is False
        # Content remains unchanged due to atomic rollback
        assert sb.abs_read("calc.py") == original


def test_verify_patch_runs_pytest(dummy_repo: Path):
    # Unpatched dummy_repo fails test_add (add(2, 3) == -1 != 5)
    fix_patch = PatchProposal(
        strategy=PatchStrategy.BOUNDARY_GUARD,
        hunks=[
            PatchHunk(
                file="calc.py",
                old="def add(a, b):\n    return a - b\n",
                new="def add(a, b):\n    return a + b\n",
            )
        ],
    )
    result = verify_patch(str(dummy_repo), fix_patch)
    assert result.patch_applied is True
    assert result.verdict == Verdict.PASSED
    assert result.all_green is True
    assert result.tests_passed >= 1
    assert result.tests_failed == 0
