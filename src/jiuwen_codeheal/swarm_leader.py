"""Swarm Leader - the controller that drives the four Teammates.

The Leader embodies the JiuwenSwarm *Leader-Teammate* collaboration model:

1. **Intent recognition** - classify what the user asked for (heal a CI failure,
   inspect a repo, run a self-test, etc.).
2. **Task decomposition** - break the request into the four canonical phases and
   decide which Teammates to dispatch.
3. **Dispatch & orchestration** - run the :class:`HealSwarmFlow` (the openjiuwen
   Workflow graph), collecting a :class:`HealingTrajectory` of observable steps.
4. **Observability** - every phase appends a :class:`TraceStep`; the Leader
   also emits a structured run record for dashboards / CI artefacts.

The Leader is deliberately thin: all real work lives in the tools and the
workflow graph. This keeps the controller auditable and lets the swarm be driven
either from the CLI, a test harness, or a live ``WorkflowAgent``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from jiuwen_codeheal.config import CodeHealConfig, EngineMode
from jiuwen_codeheal.schemas import (
    FaultType,
    HealingStatus,
    HealingTrajectory,
    TraceStep,
)
from jiuwen_codeheal.tools import (
    log_parser_tool as log_tool,
    sandbox_verifier_tool as sandbox_tool,
    skill_evolver_tool as skill_tool,
)
from jiuwen_codeheal.workflows.heal_swarmflow import HealSwarmFlow


# --------------------------------------------------------------------------- #
# Intent                                                                       #
# --------------------------------------------------------------------------- #


class Intent:
    """Recognised user intents."""

    HEAL_CI = "heal_ci"
    INSPECT_ONLY = "inspect_only"
    SELF_TEST = "self_test"
    UNKNOWN = "unknown"


_HEAL_KEYWORDS = ("heal", "fix", "自愈", "修复", "ci", "失败", "fail", "broken", "红")
_INSPECT_KEYWORDS = ("inspect", "triage", "解析", "诊断", "analyze", "analyse", "分析")
_SELFTEST_KEYWORDS = ("self-test", "selftest", "self_test", "demo", "自测", "冒烟")


@dataclass
class Decision:
    """Leader's plan for a request."""

    intent: str
    repo_root: str
    skills_dir: str
    max_iterations: int
    reasons: list[str] = field(default_factory=list)


class SwarmLeader:
    """Controller that recognises intent and dispatches Teammates."""

    def __init__(
        self,
        config: Optional[CodeHealConfig] = None,
        *,
        flow_factory: Optional[Callable[[CodeHealConfig, str, str], HealSwarmFlow]] = None,
    ) -> None:
        self.config = config or CodeHealConfig.load()
        self._flow_factory = flow_factory or (lambda cfg, repo, skills: HealSwarmFlow(
            cfg, repo_root=repo, skills_dir=skills
        ))

    # ------------------------------------------------------------------ #
    # Intent recognition                                                 #
    # ------------------------------------------------------------------ #
    def recognize_intent(self, request: str, explicit: Optional[str] = None) -> str:
        if explicit:
            return explicit
        text = (request or "").lower()
        if any(k in text for k in _SELFTEST_KEYWORDS):
            return Intent.SELF_TEST
        if any(k in text for k in _INSPECT_KEYWORDS) and not any(k in text for k in _HEAL_KEYWORDS):
            return Intent.INSPECT_ONLY
        if any(k in text for k in _HEAL_KEYWORDS):
            return Intent.HEAL_CI
        # Default: a bare repo path request is treated as a heal request.
        return Intent.HEAL_CI

    # ------------------------------------------------------------------ #
    # Task decomposition                                                 #
    # ------------------------------------------------------------------ #
    def plan(self, request: str, repo_root: str, skills_dir: str) -> Decision:
        intent = self.recognize_intent(request)
        reasons = [f"recognised intent: {intent}"]
        max_iter = self.config.healing.max_iterations
        if intent == Intent.SELF_TEST:
            reasons.append("self-test mode: cap iterations to 1 for a fast smoke run")
            max_iter = 1
        return Decision(
            intent=intent,
            repo_root=repo_root,
            skills_dir=skills_dir,
            max_iterations=max_iter,
            reasons=reasons,
        )

    # ------------------------------------------------------------------ #
    # Dispatch                                                           #
    # ------------------------------------------------------------------ #
    def heal(self, log_text: str, repo_root: str, skills_dir: str) -> HealingTrajectory:
        """Run the full four-phase heal and return the trajectory."""
        cfg = self.config.model_copy(deep=True)
        cfg.healing.max_iterations = self.config.healing.max_iterations
        flow = self._flow_factory(cfg, repo_root, skills_dir)
        traj = _run_sync(flow.run(log_text))
        return traj

    def inspect(self, log_text: str, repo_root: str) -> dict:
        """Run only Phase 1 + 2 (triage + AST inspect) and return a digest."""
        flow = self._flow_factory(self.config, repo_root, ".")
        sig, dt = flow.phase_triage(log_text)
        ctx, proposal, dt2 = flow.phase_inspect(sig, 1)
        return {
            "fault": sig.to_dict(),
            "ast_context": ctx.to_dict(),
            "proposal": proposal.model_dump(),
            "durations": {"triage": dt, "inspect": dt2},
        }

    # ------------------------------------------------------------------ #
    # Observability                                                      #
    # ------------------------------------------------------------------ #
    def run_record(self, traj: HealingTrajectory) -> dict:
        """Serialisable run record for dashboards / CI artefacts."""
        return {
            "run_id": traj.run_id,
            "status": traj.status.value,
            "mode": traj.mode,
            "repo": traj.repo_path,
            "iterations": traj.iterations,
            "duration_s": round(traj.duration, 3),
            "fingerprint": traj.fault.fingerprint if traj.fault else None,
            "fault_type": traj.fault.fault_type.value if traj.fault else None,
            "tests": traj.verification.to_dict() if traj.verification else None,
            "trace": [s.model_dump() for s in traj.trace],
        }


# --------------------------------------------------------------------------- #
# Async/sync bridge                                                            #
# --------------------------------------------------------------------------- #


def _run_sync(coro):
    """Run an async coroutine to completion from sync code.

    Prefers a fresh event loop; falls back to ``asyncio.run`` semantics. Kept
    explicit so the Leader stays importable in both sync tests and async hosts.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in an async context: run in a dedicated loop.
            return asyncio.new_event_loop().run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)
