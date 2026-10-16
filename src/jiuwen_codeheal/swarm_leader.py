"""Swarm Leader - the multi-agent controller that orchestrates the four Teammates.

The Leader embodies the JiuwenSwarm *Leader-Teammate* collaborative hierarchy:

1. **Intent recognition** - classify user directives (heal CI failure, inspect/triage, run self-test).
2. **Task decomposition** - break the goal into the four canonical phases and dispatch specialized Teammates:
   - :class:`LogTriageTeammate` (Phase 1): regex/syntax log parsing, stack frame isolation, fault fingerprinting.
   - :class:`CodeInspectorTeammate` (Phase 2): AST-based syntax tree slicing, call chain extraction, patch synthesis.
   - :class:`SandboxVerifierTeammate` (Phase 3): isolated temp worktree, security whitelist validation, pytest verification.
   - :class:`SkillEvolverTeammate` (Phase 4): experience distillation, dual-memory persistence, confidence gating.
3. **Dispatch & Orchestration** - drives :class:`HealSwarmFlow` (openJiuwen Workflow graph), executing
   the ReAct self-correction loop when sandbox tests indicate remaining failures.
4. **openJiuwen & JiuwenSwarm Native Alignment** - provides native builders for:
   - :class:`openjiuwen.core.workflow.Workflow`
   - :class:`openjiuwen.core.workflow.LLMComponent`
   - :class:`openjiuwen.core.application.workflow_agent.WorkflowAgent`
   - :class:`openjiuwen.core.runner.runner.Runner`
5. **Observability & Telemetry** - tracks detailed phase durations, pass/fail transitions, and emits
   structured run records suitable for CI summaries, dashboards, and automated PR reviews.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from jiuwen_codeheal.config import CodeHealConfig, EngineMode
from jiuwen_codeheal.schemas import (
    ASTContext,
    FaultSignature,
    FaultType,
    HealingStatus,
    HealingTrajectory,
    LearnedPattern,
    PatchProposal,
    TraceStep,
    VerificationResult,
    Verdict,
)
from jiuwen_codeheal.tools import (
    ast_inspector_tool as ast_tool,
    log_parser_tool as log_tool,
    sandbox_verifier_tool as sandbox_tool,
    skill_evolver_tool as skill_tool,
)
from jiuwen_codeheal.workflows.heal_swarmflow import HealSwarmFlow

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# User Intent Models                                                          #
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
    """Leader's execution plan for a user request."""

    intent: str
    repo_root: str
    skills_dir: str
    max_iterations: int
    reasons: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Specialized Teammate Roles (Leader-Teammate Multi-Agent Hierarchy)         #
# --------------------------------------------------------------------------- #


class LogTriageTeammate:
    """Phase 1 Teammate: Responsible for CI failure log triage and fault fingerprinting."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root

    def triage(self, log_text: str) -> Tuple[FaultSignature, float]:
        """Parse raw CI logs into structured FaultSignature and record duration."""
        t0 = time.time()
        sig_dict = log_tool.parse_ci_log(log_text, repo_root=self.repo_root)
        sig = FaultSignature(**sig_dict)
        return sig, time.time() - t0


class CodeInspectorTeammate:
    """Phase 2 Teammate: AST syntactic slicing, context compression, and patch proposal."""

    def __init__(self, repo_root: str, skills_dir: Optional[str] = None) -> None:
        self.repo_root = repo_root
        self.skills_dir = skills_dir
        self._inspector = ast_tool.ASTInspector(repo_root)
        self._policy = ast_tool.FixPolicy()

    def inspect(self, sig: FaultSignature, iteration: int = 1) -> Tuple[ASTContext, PatchProposal, float]:
        """Extract AST context and synthesize fix hypothesis with memory recall."""
        t0 = time.time()
        ctx = self._inspector.inspect(sig)

        if self.skills_dir:
            recalled = skill_tool.lookup_pattern(sig.fingerprint, self.skills_dir)
            if recalled.get("found") and recalled.get("trusted"):
                pat_dict = recalled.get("pattern", {})
                proposal = self._policy.propose(sig, ctx)
                proposal.strategy = pat_dict.get("strategy", proposal.strategy)
                proposal.source = "replay_knowledge"
                proposal.confidence = 0.95
                proposal.summary = f"[Memory Hit: trusted pattern] {proposal.summary}"
                proposal.iteration = iteration
                return ctx, proposal, time.time() - t0

        proposal = self._policy.propose(sig, ctx)
        proposal.iteration = iteration
        return ctx, proposal, time.time() - t0


class SandboxVerifierTeammate:
    """Phase 3 Teammate: Sandboxed patch staging, whitelist validation, and pytest verification."""

    def __init__(self, repo_root: str, timeout: int = 120) -> None:
        self.repo_root = repo_root
        self.timeout = timeout

    def verify(self, proposal: PatchProposal) -> Tuple[VerificationResult, float]:
        """Execute isolated regression verification in a clean temporary worktree."""
        t0 = time.time()
        result = sandbox_tool.verify_patch(self.repo_root, proposal, timeout=self.timeout)
        return result, time.time() - t0

    def check_whitelist(self, rel_path: str) -> dict:
        """Validate that a target path is allowed under the sandbox security boundary."""
        return sandbox_tool.check_whitelist(self.repo_root, rel_path)


class SkillEvolverTeammate:
    """Phase 4 Teammate: Trajectory distillation, dual-memory persistence, and pattern recall."""

    def __init__(self, skills_dir: str) -> None:
        self.skills_dir = skills_dir
        self.library = skill_tool.SkillLibrary(skills_dir)

    def evolve(self, traj: HealingTrajectory) -> Tuple[Optional[LearnedPattern], float]:
        """Distill successful/failed trajectory into repository skill memory."""
        t0 = time.time()
        pattern = skill_tool.evolve(traj, self.skills_dir)
        return pattern, time.time() - t0

    def recall(self, fingerprint: str) -> dict:
        """Recall historical healing pattern for a fault fingerprint."""
        return skill_tool.lookup_pattern(fingerprint, self.skills_dir)


# --------------------------------------------------------------------------- #
# Swarm Leader Controller                                                     #
# --------------------------------------------------------------------------- #


class SwarmLeader:
    """Central orchestrator driving the 4 Teammates and openJiuwen Swarmflow."""

    def __init__(
        self,
        config: Optional[CodeHealConfig] = None,
        *,
        flow_factory: Optional[Callable[[CodeHealConfig, str, str], HealSwarmFlow]] = None,
    ) -> None:
        self.config = config or CodeHealConfig.load()
        self._flow_factory = flow_factory or (
            lambda cfg, repo, skills: HealSwarmFlow(cfg, repo_root=repo, skills_dir=skills)
        )

    # ------------------------------------------------------------------ #
    # Teammate Factory                                                   #
    # ------------------------------------------------------------------ #
    def create_teammates(
        self, repo_root: str, skills_dir: str
    ) -> Dict[str, Any]:
        """Instantiate the 4 specialized Teammate workers."""
        return {
            "triage": LogTriageTeammate(repo_root),
            "inspector": CodeInspectorTeammate(repo_root, skills_dir=skills_dir),
            "verifier": SandboxVerifierTeammate(repo_root, timeout=self.config.healing.pytest_timeout),
            "evolver": SkillEvolverTeammate(skills_dir),
        }

    # ------------------------------------------------------------------ #
    # openJiuwen Native Component Builders                               #
    # ------------------------------------------------------------------ #
    def build_workflow_agent(
        self, repo_root: str, skills_dir: str
    ) -> Optional[Any]:
        """Construct a native openJiuwen WorkflowAgent wrapping the CodeHeal workflow.

        Enables seamless integration with openJiuwen agent runtimes and multi-agent
        frameworks. Gracefully returns None if openjiuwen agent extensions are not
        active in the environment.
        """
        try:
            from openjiuwen.core.application.workflow_agent import (
                WorkflowAgent,
                WorkflowAgentConfig,
            )
            flow = self._flow_factory(self.config, repo_root, skills_dir)
            wf = flow.build()

            agent_config = WorkflowAgentConfig(
                id="jiuwen_codeheal_swarm_agent",
                version="0.1.0",
                description="CI Fault Self-Healing Leader-Teammate Workflow Agent",
                workflows=[wf],
                start_workflow=wf.card.id,
            )
            return WorkflowAgent(agent_config)
        except Exception as exc:
            logger.debug("WorkflowAgent initialization deferred: %s", exc)
            return None

    def build_llm_component(self) -> Optional[Any]:
        """Construct an openJiuwen LLMComponent when live API credentials are configured.

        Supports DeepSeek, OpenAI, and Huawei Cloud MaaS providers.
        """
        if self.config.mode != EngineMode.LIVE or not self.config.client.api_key:
            return None
        try:
            from openjiuwen.core.foundation.llm import ModelClientConfig, ProviderType
            from openjiuwen.core.workflow import LLMCompConfig, LLMComponent

            provider_val = getattr(ProviderType, "OpenAI", getattr(ProviderType, "OPENAI", "OpenAI"))
            client_cfg = ModelClientConfig(
                client_provider=provider_val,
                api_key=self.config.client.api_key,
                api_base=self.config.client.api_base,
            )
            comp_cfg = LLMCompConfig(
                model_client_config=client_cfg,
                model_id=self.config.client.model_name,
                system_prompt_template="You are an expert software engineer analyzing CI failures.",
                user_prompt_template="{prompt}",
            )
            return LLMComponent(comp_cfg)
        except Exception as exc:
            logger.debug("LLMComponent initialization deferred: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    # Intent recognition                                                 #
    # ------------------------------------------------------------------ #
    def recognize_intent(self, request: str, explicit: Optional[str] = None) -> str:
        """Classify user request text into canonical Intent constants."""
        if explicit:
            return explicit
        text = (request or "").lower()
        if any(k in text for k in _SELFTEST_KEYWORDS):
            return Intent.SELF_TEST
        if any(k in text for k in _INSPECT_KEYWORDS) and not any(k in text for k in _HEAL_KEYWORDS):
            return Intent.INSPECT_ONLY
        if any(k in text for k in _HEAL_KEYWORDS):
            return Intent.HEAL_CI
        # Default: treated as heal request.
        return Intent.HEAL_CI

    # ------------------------------------------------------------------ #
    # Task decomposition                                                 #
    # ------------------------------------------------------------------ #
    def plan(self, request: str, repo_root: str, skills_dir: str) -> Decision:
        """Decompose request into execution policy and iteration bounds."""
        intent = self.recognize_intent(request)
        reasons = [f"recognised intent: {intent}"]
        max_iter = self.config.healing.max_iterations
        if intent == Intent.SELF_TEST:
            reasons.append("self-test mode: cap iterations to 1 for a fast smoke run")
            max_iter = 1
        elif intent == Intent.INSPECT_ONLY:
            reasons.append("inspect-only mode: skip sandbox modification and verification")
            max_iter = 1
        return Decision(
            intent=intent,
            repo_root=repo_root,
            skills_dir=skills_dir,
            max_iterations=max_iter,
            reasons=reasons,
        )

    # ------------------------------------------------------------------ #
    # Dispatch & Orchestration                                           #
    # ------------------------------------------------------------------ #
    def heal(self, log_text: str, repo_root: str, skills_dir: str) -> HealingTrajectory:
        """Run the full four-phase self-healing flow and return the trajectory."""
        cfg = self.config.model_copy(deep=True)
        cfg.healing.max_iterations = self.config.healing.max_iterations
        flow = self._flow_factory(cfg, repo_root, skills_dir)
        traj = _run_sync(flow.run(log_text))
        return traj

    def inspect(self, log_text: str, repo_root: str) -> dict:
        """Run only Phase 1 + 2 (triage + AST inspect) and return a diagnostic digest."""
        flow = self._flow_factory(self.config, repo_root, ".")
        sig, dt = flow.phase_triage(log_text)
        ctx, proposal, dt2 = flow.phase_inspect(sig, 1)
        return {
            "fault": sig.to_dict(),
            "ast_context": ctx.to_dict(),
            "proposal": proposal.model_dump(),
            "durations": {"triage": dt, "inspect": dt2},
        }

    def build_workflow_by_intent(self, intent: str, repo_root: str, skills_dir: str = ".") -> Any:
        """Dynamically build and route to the corresponding workflow subgraph based on Intent."""
        flow = self._flow_factory(self.config, repo_root, skills_dir)
        if intent == Intent.INSPECT_ONLY:
            return flow.build_inspect_workflow()
        return flow.build_heal_workflow()

    def dispatch_workflow(
        self, intent: str, log_text: str, repo_root: str, skills_dir: str = "."
    ) -> Any:
        """Dynamically dispatch the request to the matching workflow execution route."""
        decision = self.plan(request=intent, repo_root=repo_root, skills_dir=skills_dir)
        if decision.intent == Intent.INSPECT_ONLY:
            return self.inspect(log_text, repo_root)
        return self.heal(log_text, repo_root, skills_dir)

    # ------------------------------------------------------------------ #
    # Observability & Metrics                                            #
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

    def summarize_metrics(self, traj: HealingTrajectory) -> dict:
        """Compute execution performance metrics from a trajectory."""
        total_time = traj.duration
        triage_time = sum(s.duration for s in traj.trace if "1-triage" in s.phase)
        inspect_time = sum(s.duration for s in traj.trace if "2-inspect" in s.phase)
        verify_time = sum(s.duration for s in traj.trace if "3-verify" in s.phase)
        evolve_time = sum(s.duration for s in traj.trace if "4-evolve" in s.phase)

        tests_passed = traj.verification.tests_passed if traj.verification else 0
        tests_total = traj.verification.tests_total if traj.verification else 0
        pass_rate = (tests_passed / tests_total) if tests_total > 0 else 0.0

        return {
            "healed": traj.status == HealingStatus.HEALED,
            "iterations": traj.iterations,
            "total_duration_s": round(total_time, 2),
            "phase_durations": {
                "triage_s": round(triage_time, 2),
                "inspect_s": round(inspect_time, 2),
                "verify_s": round(verify_time, 2),
                "evolve_s": round(evolve_time, 2),
            },
            "pass_rate": round(pass_rate, 4),
            "patches_attempted": len(traj.patches),
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
            return asyncio.new_event_loop().run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


__all__ = [
    "Decision",
    "Intent",
    "LogTriageTeammate",
    "CodeInspectorTeammate",
    "SandboxVerifierTeammate",
    "SkillEvolverTeammate",
    "SwarmLeader",
]
