"""Sandbox Verifier Tool (Phase 3 - Patch & Sandbox Verifier Teammate).

Responsibilities:

1. **Security**: enforce a strict *file-access whitelist*. The verifier may only
   touch files inside the isolated sandbox it creates. Any attempt to read,
   write, or apply a patch outside the whitelist raises :class:`SecurityError`.
   This aligns with JiuwenSwarm's Tool Permissions & Security model.

2. **Isolation**: copy the target repository into a fresh temporary workspace
   (a *sandbox*) so the original working tree is never mutated.

3. **Patch application**: apply a candidate :class:`PatchProposal` by replacing
   the enclosing function's source (AST-level, exact-string replace), with
   atomic rollback if anything fails.

4. **Regression verification**: actually run ``pytest`` inside the sandbox via
   :mod:`subprocess`, parse the JUnit-style summary, and decide whether the
   patch truly eliminated the bug *without* breaking existing tests.

The whole tool never imports the project under test and never trusts paths that
escape the sandbox root (defence against path-traversal in malicious patches).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from jiuwen_codeheal.schemas import (
    PatchProposal,
    TestOutcome,
    VerificationResult,
    Verdict,
)


class SecurityError(PermissionError):
    """Raised when a path or operation violates the sandbox whitelist."""


class Sandbox:
    """An isolated, whitelisted copy of a repository."""

    def __init__(self, repo_root: str, *, keep: bool = False) -> None:
        self.repo_root = str(Path(repo_root).resolve())
        self.keep = keep
        self.root: Optional[Path] = None
        self._tmp: Optional[str] = None

    # ------------------------------------------------------------------ #
    def __enter__(self) -> "Sandbox":
        self._tmp = tempfile.mkdtemp(prefix="codeheal_sbx_")
        self.root = Path(self._tmp) / "repo"
        # Copy the repo, excluding heavy / VCS / cache dirs.
        shutil.copytree(
            self.repo_root,
            self.root,
            ignore=shutil.ignore_patterns(
                ".git", "__pycache__", "*.pyc", ".pytest_cache", "*.egg-info",
                ".venv", "venv", ".mypy_cache", ".ruff_cache", ".tox", "build",
                "dist", "*.log",
            ),
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._tmp and not self.keep:
            shutil.rmtree(self._tmp, ignore_errors=True)
        self._tmp = None
        self.root = None

    # ------------------------------------------------------------------ #
    def resolve(self, rel_path: str) -> Path:
        """Resolve *rel_path* inside the sandbox, enforcing the whitelist.

        Raises :class:`SecurityError` if the path escapes the sandbox root.
        """
        if self.root is None:
            raise SecurityError("sandbox is not active")
        root_resolved = self.root.resolve()

        # Reject path syntax intended as absolute paths on any platform (e.g. C:\... or /...)
        raw_str = str(rel_path).strip()
        if bool(re.match(r"^[a-zA-Z]:", raw_str)) or raw_str.startswith(("/", "\\")):
            candidate = Path(raw_str).resolve()
            try:
                if os.path.commonpath([str(candidate), str(root_resolved)]) != str(root_resolved):
                    raise SecurityError(
                        f"path '{rel_path}' is outside sandbox root '{root_resolved}'"
                    )
                return candidate
            except (ValueError, SecurityError):
                raise SecurityError(
                    f"path '{rel_path}' is outside sandbox root '{root_resolved}'"
                )

        # Normalise and reject traversal.
        candidate = (self.root / rel_path).resolve()
        try:
            if os.path.commonpath([str(candidate), str(root_resolved)]) != str(root_resolved):
                raise SecurityError(
                    f"path '{rel_path}' escapes the sandbox whitelist "
                    f"(resolved to '{candidate}', root '{root_resolved}')"
                )
        except ValueError:
            raise SecurityError(
                f"path '{rel_path}' escapes the sandbox whitelist"
            )
        return candidate

    def abs_read(self, rel_path: str) -> str:
        return self.resolve(rel_path).read_text(encoding="utf-8")

    def abs_write(self, rel_path: str, content: str) -> None:
        target = self.resolve(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Patch application                                                            #
# --------------------------------------------------------------------------- #


def apply_patch(sandbox: Sandbox, patch: PatchProposal) -> bool:
    """Apply a patch inside the sandbox with atomic rollback.

    Strategy: for each hunk, replace the ``old`` source snippet with the ``new``
    one inside the target file. The replacement is exact-string based but
    constrained to the file's real content, and we verify the ``old`` snippet
    actually exists before touching the file. Any failure rolls the file back.

    Returns ``True`` if at least one hunk was applied and all applied cleanly.
    """
    if not patch.hunks:
        return False

    backups: dict[str, str] = {}
    applied = 0
    try:
        for hunk in patch.hunks:
            rel = hunk.file
            # Read current sandbox content (not the original proposal's).
            current = sandbox.abs_read(rel)
            if rel not in backups:
                backups[rel] = current

            old = hunk.old
            new = hunk.new
            if new == current:
                # Already patched (idempotent); still counts as applied.
                applied += 1
                continue
            if old not in current:
                raise ValueError(
                    f"hunk context for '{rel}' not found in sandbox source; "
                    f"the AST slice drifted. Refusing to apply."
                )
            updated = current.replace(old, new, 1)
            sandbox.abs_write(rel, updated)
            applied += 1
        return applied > 0
    except Exception:
        # Rollback every touched file.
        for rel, content in backups.items():
            try:
                sandbox.abs_write(rel, content)
            except Exception:
                pass
        return False


# --------------------------------------------------------------------------- #
# pytest execution                                                             #
# --------------------------------------------------------------------------- #


_PYTEST_SHORT = re.compile(r"^(?P<status>PASSED|FAILED|ERROR)\s+(?P<node>\S+)")
_SUMMARY = re.compile(r"(?P<passed>\d+) passed")
_SUMMARY_FAIL = re.compile(r"(?P<failed>\d+) failed")
_SUMMARY_ERR = re.compile(r"(?P<errors>\d+) error")


def run_pytest(
    sandbox: Sandbox,
    *,
    timeout: int = 120,
    extra_args: Optional[list[str]] = None,
) -> VerificationResult:
    """Run ``pytest`` inside the sandbox and return a structured result.

    Captures stdout/stderr, parses the summary line, and records per-test
    outcomes from the short test summary info block. Never raises on a test
    failure - a failing suite is a normal, returned outcome.
    """
    start = time.time()
    cmd = [sys.executable, "-m", "pytest", "-v", "--no-header", "--tb=short", "-p", "no:cacheprovider"]
    if extra_args:
        cmd += extra_args

    env = os.environ.copy()
    env["PYTHONPATH"] = str(sandbox.root) + os.pathsep + env.get("PYTHONPATH", "")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(sandbox.root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        returncode = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        return VerificationResult(
            verdict=Verdict.ERROR,
            sandbox_path=str(sandbox.root),
            return_code=-9,
            stdout_tail=_tail(exc.stdout or ""),
            stderr_tail=_tail(exc.stderr or "") + "\n[pytest timed out]",
            duration=time.time() - start,
        )
    except Exception as exc:  # pragma: no cover - subprocess rarely throws
        return VerificationResult(
            verdict=Verdict.ERROR,
            sandbox_path=str(sandbox.root),
            return_code=-1,
            stderr_tail=str(exc),
            duration=time.time() - start,
        )

    outcomes = _parse_test_outcomes(stdout)

    summary_passed = _first_int(_SUMMARY, stdout)
    summary_failed = _first_int(_SUMMARY_FAIL, stdout)
    summary_err = _first_int(_SUMMARY_ERR, stdout)

    # Prefer the summary counts (authoritative) but fall back to parsed nodes.
    total = summary_passed + summary_failed + summary_err
    if total > 0:
        passed = summary_passed
        failed = summary_failed + summary_err
    else:
        total = len(outcomes)
        passed = sum(1 for o in outcomes if o.passed)
        failed = sum(1 for o in outcomes if not o.passed)

    verdict = Verdict.PASSED if (returncode == 0 and failed == 0 and total > 0) else (
        Verdict.FAILED if total > 0 else Verdict.ERROR
    )

    return VerificationResult(
        verdict=verdict,
        sandbox_path=str(sandbox.root),
        return_code=returncode,
        tests_total=total,
        tests_passed=passed,
        tests_failed=failed,
        still_failing=[o.node_id for o in outcomes if not o.passed],
        passed_tests=outcomes,
        stdout_tail=_tail(stdout),
        stderr_tail=_tail(stderr),
        duration=time.time() - start,
        patch_applied=True,
    )


def _parse_test_outcomes(stdout: str) -> list[TestOutcome]:
    out: list[TestOutcome] = []
    for line in stdout.splitlines():
        m = _PYTEST_SHORT.match(line.strip())
        if not m:
            continue
        out.append(
            TestOutcome(
                node_id=m.group("node"),
                passed=(m.group("status") == "PASSED"),
            )
        )
    return out


def _first_int(pattern: re.Pattern[str], text: str) -> int:
    m = pattern.search(text)
    return int(m.group(1)) if m else 0


def _tail(text: str, lines: int = 60) -> str:
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


# --------------------------------------------------------------------------- #
# High-level orchestration                                                     #
# --------------------------------------------------------------------------- #


def verify_patch(
    repo_root: str,
    patch: PatchProposal,
    *,
    timeout: int = 120,
    keep_sandbox: bool = False,
    extra_args: Optional[list[str]] = None,
) -> VerificationResult:
    """One-call sandbox verification: copy repo -> apply patch -> run pytest."""
    with Sandbox(repo_root, keep=keep_sandbox) as sandbox:
        applied = apply_patch(sandbox, patch)
        if not applied:
            return VerificationResult(
                verdict=Verdict.ERROR,
                sandbox_path=str(sandbox.root or ""),
                return_code=-2,
                stderr_tail="patch application failed (context drift or empty hunks)",
                patch_applied=False,
            )
        result = run_pytest(sandbox, timeout=timeout, extra_args=extra_args)
        if keep_sandbox and sandbox.root:
            result.sandbox_path = str(sandbox.root)
        return result


def apply_and_verify(
    sandbox: Sandbox,
    patch: PatchProposal,
    *,
    timeout: int = 120,
    extra_args: Optional[list[str]] = None,
) -> VerificationResult:
    """Apply a candidate patch into an active sandbox and re-run pytest."""
    applied = apply_patch(sandbox, patch)
    if not applied:
        return VerificationResult(
            verdict=Verdict.ERROR,
            sandbox_path=str(sandbox.root or ""),
            return_code=-2,
            stderr_tail="patch application failed (context drift or empty hunks)",
            patch_applied=False,
        )
    return run_pytest(sandbox, timeout=timeout, extra_args=extra_args)


def baseline_tests_pass(repo_root: str, *, timeout: int = 120) -> bool:
    """Run the *unmodified* repo's tests. Returns True if the suite is green
    (used to confirm a demo repo is actually broken beforehand)."""
    with Sandbox(repo_root, keep=False) as sandbox:
        result = run_pytest(sandbox, timeout=timeout)
    return result.all_green


# --------------------------------------------------------------------------- #
# Functional wrappers (openjiuwen @tool targets)                               #
# --------------------------------------------------------------------------- #


def check_whitelist(repo_root: str, rel_path: str) -> dict:
    """Return whether *rel_path* is writable under *repo_root* (whitelist check)."""
    try:
        with Sandbox(repo_root) as sb:
            sb.resolve(rel_path)
        return {"allowed": True, "path": rel_path}
    except SecurityError as exc:
        return {"allowed": False, "reason": str(exc)}


def verify_patch_tool(repo_root: str, patch: dict, timeout: int = 120) -> dict:
    """Apply *patch* in a sandbox and run pytest, returning a serialisable result."""
    proposal = PatchProposal(**patch)
    result = verify_patch(repo_root, proposal, timeout=timeout)
    return result.to_dict()
