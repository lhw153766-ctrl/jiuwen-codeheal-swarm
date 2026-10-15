"""Pydantic data models shared across the whole CodeHeal Swarm.

These models are the *contract* between the four phases:

* The **Log Triage** teammate produces :class:`FaultSignature`.
* The **Code Inspector** teammate enriches it with :class:`ASTContext`.
* The **Patch & Sandbox Verifier** teammate produces :class:`PatchProposal`
  and :class:`VerificationResult`.
* The **Skill Evolver** teammate persists :class:`HealingTrajectory` +
  :class:`LearnedPattern` into the skill memory.

Everything is a plain Pydantic ``BaseModel`` so it can be serialised to JSON,
travelled through openjiuwen workflow state, and asserted against in tests.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enumerations                                                                 #
# --------------------------------------------------------------------------- #


class FaultType(str, Enum):
    """Coarse classification of the CI failure root cause."""

    ASSERTION_ERROR = "assertion_error"
    VALUE_ERROR = "value_error"
    TYPE_ERROR = "type_error"
    KEY_ERROR = "key_error"
    INDEX_ERROR = "index_error"
    ATTRIBUTE_ERROR = "attribute_error"
    NAME_ERROR = "name_error"
    IMPORT_ERROR = "import_error"
    SYNTAX_ERROR = "syntax_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class PatchStrategy(str, Enum):
    """How the candidate fix was produced."""

    BOUNDARY_GUARD = "boundary_guard"          # off-by-one / empty-input guard
    NONE_CHECK = "none_check"                  # add None / missing-key guard
    TYPE_COERCION = "type_coercion"            # cast / normalize a value
    LOGIC_INVERSION = "logic_inversion"        # flip a comparison
    DEFAULT_ARGUMENT = "default_argument"      # supply a sensible default
    REPLAY_KNOWLEDGE = "replay_knowledge"      # learned from skill memory
    UNKNOWN = "unknown"


class HealingStatus(str, Enum):
    """Terminal outcome of the whole swarm run."""

    HEALED = "healed"
    FAILED_TO_HEAL = "failed_to_heal"
    SKIPPED = "skipped"
    ERROR = "error"


class Verdict(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


# --------------------------------------------------------------------------- #
# Phase 1 outputs - fault signature                                            #
# --------------------------------------------------------------------------- #


class StackFrame(BaseModel):
    """One frame of a Python traceback."""

    file: str
    line: int
    function: str
    code: str = ""


class FailedTest(BaseModel):
    """A single failing test case parsed from the log."""

    node_id: str
    test_file: str
    test_function: str
    message: str = ""


class FaultSignature(BaseModel):
    """Structured representation of a CI failure."""

    fault_type: FaultType = FaultType.UNKNOWN
    exception_type: Optional[str] = None
    message: str = ""
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    failed_tests: list[FailedTest] = Field(default_factory=list)
    stack_frames: list[StackFrame] = Field(default_factory=list)
    raw_log_excerpt: str = ""
    fingerprint: str = ""  # stable hash used for skill memory dedup

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# --------------------------------------------------------------------------- #
# Phase 2 outputs - AST context                                                #
# --------------------------------------------------------------------------- #


class FunctionContext(BaseModel):
    """The exact enclosing function / method AST node for the fault line."""

    name: str
    signature: str = ""
    lineno: int = 0
    end_lineno: int = 0
    source: str = ""
    is_method: bool = False
    class_name: Optional[str] = None


class ASTContext(BaseModel):
    """Precision-sliced source context handed to the patch phase."""

    target_file: str
    target_line: int
    function: Optional[FunctionContext] = None
    class_source: Optional[str] = None
    imports: list[str] = Field(default_factory=list)
    related_test_file: Optional[str] = None
    related_test_source: str = ""
    call_chain: list[str] = Field(default_factory=list)
    compressed_context: str = ""  # the final, budget-aware context blob

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# --------------------------------------------------------------------------- #
# Phase 3 outputs - patch + verification                                       #
# --------------------------------------------------------------------------- #


class PatchHunk(BaseModel):
    file: str
    old: str
    new: str
    rationale: str = ""


class PatchProposal(BaseModel):
    """A candidate fix generated for the fault."""

    strategy: PatchStrategy = PatchStrategy.UNKNOWN
    summary: str = ""
    hunks: list[PatchHunk] = Field(default_factory=list)
    unified_diff: str = ""
    confidence: float = 0.0
    iteration: int = 0
    source: str = "policy"  # "policy" | "llm" | "replay_knowledge"


class TestOutcome(BaseModel):
    """Outcome of a single test inside the sandbox."""

    node_id: str
    passed: bool
    message: str = ""
    duration: float = 0.0


class VerificationResult(BaseModel):
    """Result of applying a patch in the sandbox and re-running pytest."""

    verdict: Verdict = Verdict.ERROR
    sandbox_path: str = ""
    return_code: int = -1
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    newly_failing: list[str] = Field(default_factory=list)
    still_failing: list[str] = Field(default_factory=list)
    passed_tests: list[TestOutcome] = Field(default_factory=list)
    stdout_tail: str = ""
    stderr_tail: str = ""
    duration: float = 0.0
    patch_applied: bool = False

    @property
    def all_green(self) -> bool:
        return self.verdict == Verdict.PASSED and self.tests_failed == 0 and self.tests_total > 0

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# --------------------------------------------------------------------------- #
# Phase 4 outputs - skill memory                                               #
# --------------------------------------------------------------------------- #


class LearnedPattern(BaseModel):
    """A distilled ``error fingerprint -> root cause -> fix strategy`` rule."""

    fingerprint: str
    fault_type: FaultType
    root_cause: str
    strategy: PatchStrategy
    fix_template: str = ""
    occurrences: int = 1
    success_count: int = 0
    example_file: str = ""
    updated_at: float = Field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# --------------------------------------------------------------------------- #
# Trajectory / trace                                                           #
# --------------------------------------------------------------------------- #


class TraceStep(BaseModel):
    """One observable step in the swarm run (for the live trace report)."""

    phase: str
    title: str
    detail: str = ""
    ok: bool = True
    duration: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)


class HealingTrajectory(BaseModel):
    """Full audit trail of one healing run - the unit of observability."""

    run_id: str
    repo_path: str
    status: HealingStatus = HealingStatus.ERROR
    mode: str = "replay"
    iterations: int = 0
    fault: Optional[FaultSignature] = None
    ast_context: Optional[ASTContext] = None
    patches: list[PatchProposal] = Field(default_factory=list)
    verification: Optional[VerificationResult] = None
    learned_pattern: Optional[LearnedPattern] = None
    diff: str = ""
    trace: list[TraceStep] = Field(default_factory=list)
    started_at: float = Field(default_factory=time.time)
    finished_at: Optional[float] = None
    error: Optional[str] = None

    def add_trace(self, step: TraceStep) -> None:
        self.trace.append(step)

    def finish(self, status: HealingStatus) -> None:
        self.status = status
        self.finished_at = time.time()

    @property
    def duration(self) -> float:
        end = self.finished_at or time.time()
        return max(0.0, end - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
