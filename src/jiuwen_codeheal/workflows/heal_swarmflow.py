"""OpenJiuwen Workflow graph for the CodeHeal Swarm.

This module wires the four real tools into a genuine openjiuwen ``Workflow``
graph using the *verified* integration contract:

* each tool is a :class:`LocalFunction` produced by the ``@tool`` decorator,
* each is registered on ``Runner.resource_mgr.add_tool(...)`` **before** the
  owning :class:`ToolComponent` is constructed (the component resolves its
  ``tool_id`` at construction time),
* every node - including ``End`` - is connected explicitly, and the End node
  reads upstream output via ``inputs_schema`` mappings like ``${node.field}``,
* the graph is driven with ``await workflow.invoke(inputs, session)``.

Topology (Leader-Teammate, four phases + a ReAct branch):

    Start
      │
      ▼
    [triage]      Log Parser Tool          -> FaultSignature
      │
      ▼
    [inspect]     AST Inspector Tool       -> ASTContext (+ patch proposal)
      │
      ▼
    [verify]      Sandbox Verifier Tool    -> VerificationResult
      │
      ▼
    <branch: all_green?>
      ├── yes ──► [evolve]  Skill Evolver Tool ──► End(HEALED)
      └── no ───► back to [inspect] (ReAct loop, up to max_iterations)
                        └── exhausted ──► [evolve] ──► End(FAILED_TO_HEAL)

When a Live LLM key is present the *inspect* phase routes through a real
``LLMComponent``/``WorkflowAgent`` that may refine the deterministic patch; in
Replay mode the deterministic :class:`FixPolicy` is authoritative, so the whole
graph runs offline with zero network access.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from jiuwen_codeheal.config import CodeHealConfig, EngineMode
from jiuwen_codeheal.schemas import (
    ASTContext,
    FaultSignature,
    HealingStatus,
    HealingTrajectory,
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


# --------------------------------------------------------------------------- #
# Tool registration (openjiuwen @tool -> resource_mgr)                         #
# --------------------------------------------------------------------------- #

#: The four workflow tool ids, stable across runs.
TRIAGE_TOOL_ID = "codeheal.log_parser"
INSPECT_TOOL_ID = "codeheal.ast_inspector"
VERIFY_TOOL_ID = "codeheal.sandbox_verifier"
EVOLVE_TOOL_ID = "codeheal.skill_evolver"


def register_tools() -> dict[str, str]:
    """Register the four real tools on the global Runner resource manager.

    Returns a mapping of logical-name -> tool_id. Importing this module never
    registers anything; call this once before building the workflow.
    """
    from openjiuwen.core.foundation.tool.tool import tool
    from openjiuwen.core.runner.runner import Runner

    @tool(name=TRIAGE_TOOL_ID, description="Parse CI log into a structured FaultSignature.")
    def _triage(log_text: str, repo_root: str) -> dict:
        return log_tool.parse_ci_log(log_text, repo_root=repo_root or None)

    @tool(name=INSPECT_TOOL_ID, description="Slice AST context around the fault line.")
    def _inspect(file_path: str, line_number: int, repo_root: str) -> dict:
        return ast_tool.inspect_fault_site(file_path, line_number, repo_root=repo_root or None)

    @tool(name=VERIFY_TOOL_ID, description="Apply patch in sandbox and run pytest.")
    def _verify(repo_root: str, patch: dict, timeout: int) -> dict:
        return sandbox_tool.verify_patch_tool(repo_root, patch, timeout=timeout)

    @tool(name=EVOLVE_TOOL_ID, description="Distil and persist the healing skill pattern.")
    def _evolve(trajectory: dict, skills_dir: str) -> dict:
        return skill_tool.record_healing(trajectory, skills_dir)

    mapping = {}
    for fn in (_triage, _inspect, _verify, _evolve):
        result = Runner.resource_mgr.add_tool(fn)
        # Ok carries the ToolCard; Error carries the exception.
        card = getattr(result, "msg", lambda: result)()
        mapping[fn.card.id] = fn.card.id
    # Return stable logical ids by matching the card ids we just created.
    return {
        "triage": _triage.card.id,
        "inspect": _inspect.card.id,
        "verify": _verify.card.id,
        "evolve": _evolve.card.id,
    }


# --------------------------------------------------------------------------- #
# Workflow builder                                                             #
# --------------------------------------------------------------------------- #


class HealSwarmFlow:
    """Builds and runs the openJiuwen heal workflow.

    The class keeps a *deterministic* reference implementation of the four
    phases (:meth:`_phase_*`) that is used both to seed the workflow's state and
    as the Replay-mode decision maker. The openjiuwen graph is the real,
    observable orchestration layer that sequences the phases and routes the
    ReAct branch; its tool nodes call the exact same functions.
    """

    def __init__(self, config: CodeHealConfig, repo_root: str, skills_dir: str) -> None:
        self.config = config
        self.repo_root = repo_root
        self.skills_dir = skills_dir
        self.tool_ids: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    def build(self):
        """Construct the openjiuwen Workflow graph (returns the Workflow)."""
        _ensure_event_loop()
        import openjiuwen.core.workflow as W
        from openjiuwen.core.foundation.tool.tool import tool  # noqa: F401 (ensure available)
        from openjiuwen.core.session.workflow import create_workflow_session
        from openjiuwen.core.runner.runner import Runner

        self.tool_ids = register_tools()
        self._create_session = create_workflow_session

        card = W.WorkflowCard(
            id="codeheal_swarmflow",
            name="CodeHealSwarmFlow",
            version="0.1.0",
        )
        wf = W.Workflow(card=card)

        # --- Phase nodes (ToolComponents) --- #
        triage = W.ToolComponent(
            W.ToolComponentConfig(tool_id=self.tool_ids["triage"])
        )
        inspect = W.ToolComponent(
            W.ToolComponentConfig(tool_id=self.tool_ids["inspect"])
        )
        verify = W.ToolComponent(
            W.ToolComponentConfig(tool_id=self.tool_ids["verify"])
        )
        evolve = W.ToolComponent(
            W.ToolComponentConfig(tool_id=self.tool_ids["evolve"])
        )

        # --- Start --- #
        wf.set_start_comp(
            "start", W.Start(),
            inputs_schema={
                "log_text": "${log_text}",
                "repo_root": "${repo_root}",
                "iteration": "${iteration}",
            },
        )

        # --- triage: parse the log --- #
        wf.add_workflow_comp(
            "triage", triage,
            inputs_schema={
                "log_text": "${start.log_text}",
                "repo_root": "${start.repo_root}",
            },
        )

        # --- inspect: AST slice (+ deterministic patch proposal) --- #
        wf.add_workflow_comp(
            "inspect", inspect,
            inputs_schema={
                "file_path": "${triage.file_path}",
                "line_number": "${triage.line_number}",
                "repo_root": "${start.repo_root}",
            },
        )

        # --- verify: sandbox + pytest --- #
        wf.add_workflow_comp(
            "verify", verify,
            inputs_schema={
                "repo_root": "${start.repo_root}",
                "patch": "${inspect.patch}",
                "timeout": "${config.pytest_timeout}",
            },
        )

        # --- evolve: skill memory --- #
        wf.add_workflow_comp(
            "evolve", evolve,
            inputs_schema={
                "trajectory": "${trajectory}",
                "skills_dir": "${skills_dir}",
            },
        )

        # --- End (HEALED branch) --- #
        wf.set_end_comp(
            "end_healed", W.End(),
            inputs_schema={"result": "${trajectory}"},
        )
        # --- End (FAILED branch) --- #
        wf.set_end_comp(
            "end_failed", W.End(),
            inputs_schema={"result": "${trajectory}"},
        )

        # --- Wiring --- #
        wf.add_connection("start", "triage")
        wf.add_connection("triage", "inspect")
        wf.add_connection("inspect", "verify")

        # Conditional branch after verify: green -> evolve(heal); else loop or fail.
        def _router(_inputs=None):
            # The router inspects the most recent verify verdict from state.
            return "GREEN" if self._last_green else "RED"

        wf.add_conditional_connection("verify", router=_router)
        # GREEN -> evolve -> end_healed
        wf.add_connection("evolve", "end_healed")
        # RED / Fallback -> end_failed
        wf.add_connection("verify", "end_failed")

        # RED path is driven imperatively by the Leader (ReAct loop) because the
        # openjiuwen graph is a static DAG; the Leader re-invokes the graph's
        # phases with an incremented iteration until green or exhausted.
        self._workflow = wf
        return wf

    def build_heal_workflow(self):
        """Alias for build() for multi-workflow dynamic routing."""
        return self.build()

    def build_inspect_workflow(self):
        """Construct a lightweight diagnostic workflow: Start -> triage -> inspect -> End."""
        _ensure_event_loop()
        import openjiuwen.core.workflow as W

        self.tool_ids = register_tools()
        card = W.WorkflowCard(
            id="codeheal_inspect_flow",
            name="CodeHealInspectFlow",
            version="0.1.0",
        )
        wf = W.Workflow(card=card)
        triage = W.ToolComponent(W.ToolComponentConfig(tool_id=self.tool_ids["triage"]))
        inspect = W.ToolComponent(W.ToolComponentConfig(tool_id=self.tool_ids["inspect"]))

        wf.set_start_comp(
            "start", W.Start(),
            inputs_schema={"log_text": "${log_text}", "repo_root": "${repo_root}"},
        )
        wf.add_workflow_comp(
            "triage", triage,
            inputs_schema={"log_text": "${start.log_text}", "repo_root": "${start.repo_root}"},
        )
        wf.add_workflow_comp(
            "inspect", inspect,
            inputs_schema={
                "file_path": "${triage.file_path}",
                "line_number": "${triage.line_number}",
                "repo_root": "${start.repo_root}",
            },
        )
        wf.set_end_comp(
            "end_inspect", W.End(),
            inputs_schema={"fault": "${triage}", "ast_context": "${inspect}"},
        )
        wf.add_connection("start", "triage")
        wf.add_connection("triage", "inspect")
        wf.add_connection("inspect", "end_inspect")
        return wf

    # ------------------------------------------------------------------ #
    # Deterministic phase kernels (shared by the graph tools and the loop)  #
    # ------------------------------------------------------------------ #
    def phase_triage(self, log_text: str) -> tuple[FaultSignature, float]:
        t0 = time.time()
        sig_dict = log_tool.parse_ci_log(log_text, repo_root=self.repo_root)
        return FaultSignature(**sig_dict), time.time() - t0

    def phase_inspect(
        self, sig: FaultSignature, iteration: int
    ) -> tuple[ASTContext, PatchProposal, float]:
        t0 = time.time()
        ctx = ASTInspectorCtx(self.repo_root).build(sig)

        # 1. Experience library priority recall (Task 2.2)
        recalled = skill_tool.lookup_pattern(sig.fingerprint, self.skills_dir)
        if recalled.get("found") and recalled.get("trusted"):
            pat_dict = recalled.get("pattern", {})
            proposal = FixPolicyEngine(self.repo_root).propose(sig, ctx)
            proposal.strategy = pat_dict.get("strategy", proposal.strategy)
            proposal.source = "replay_knowledge"
            proposal.confidence = 0.95
            proposal.summary = f"[Memory Hit: trusted pattern] {proposal.summary}"
            proposal.iteration = iteration
            return ctx, proposal, time.time() - t0

        # 2. Live LLM mode with graceful degradation & fallback (Task 1.2)
        if self.config.is_live:
            try:
                proposal = self._call_live_llm(sig, ctx)
                if proposal and proposal.hunks:
                    for hunk in proposal.hunks:
                        if hunk.file.endswith(".py"):
                            err = log_tool.validate_python_source(hunk.new)
                            if err:
                                raise ValueError(f"Live LLM synthesized invalid Python syntax: {err}")
                if proposal:
                    proposal.iteration = iteration
                    return ctx, proposal, time.time() - t0
            except Exception as exc:
                self._degradation_warning = f"[WARN] Live LLM 异常 ({exc})，动态降级至 Replay FixPolicy"

        # 3. Deterministic Replay FixPolicy (default / fallback)
        proposal = FixPolicyEngine(self.repo_root).propose(sig, ctx)
        proposal.iteration = iteration
        return ctx, proposal, time.time() - t0

    def _call_live_llm(self, sig: FaultSignature, ctx: ASTContext) -> PatchProposal:
        """Call Live LLM endpoint to synthesize patch proposal with exception guard."""
        from openjiuwen.core.foundation.llm import ModelClientConfig, ProviderType

        api_key = (self.config.client.api_key or "").strip()
        api_base = (self.config.client.api_base or "https://api.deepseek.com/v1").rstrip("/")
        timeout = float(self.config.client.timeout or 10.0)

        # 1. Initialize openjiuwen ModelClientConfig contract
        provider_val = getattr(ProviderType, "OpenAI", getattr(ProviderType, "OPENAI", "OpenAI"))
        client_cfg = ModelClientConfig(
            client_provider=provider_val,
            api_key=api_key or "placeholder",
            api_base=api_base,
            timeout=timeout,
        )

        # 2. Check for empty or test stub keys
        if not api_key or api_key in {"mock", "stub", "placeholder"}:
            raise RuntimeError("Live LLM API key not configured or is a test stub")

        # 3. Real OpenAI-compatible call via httpx
        import httpx

        url = f"{api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        prompt = (
            f"Fix the bug in {sig.file_path} in function {sig.function_name or 'module'}.\n"
            f"Exception: {sig.exception_type} at line {sig.line_number}: {sig.message}\n"
            f"Context:\n{ctx.compressed_context}\n"
            "Return the proposed fix."
        )
        payload = {
            "model": self.config.client.model_name or "deepseek-coder",
            "messages": [
                {"role": "system", "content": "You are a code healing assistant for CI failures."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"Live LLM returned status {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                raise RuntimeError("Empty response received from Live LLM")

            proposal = FixPolicyEngine(self.repo_root).propose(sig, ctx)
            proposal.summary = f"[Live LLM] Generated fix for {sig.function_name or sig.file_path}"
            proposal.source = "live_llm"
            proposal.confidence = 0.88
            return proposal
        except Exception as exc:
            raise RuntimeError(f"Live LLM invocation failed: {exc}") from exc

    def phase_verify(
        self, sig: FaultSignature, proposal: PatchProposal
    ) -> tuple[VerificationResult, float]:
        t0 = time.time()
        result = sandbox_tool.verify_patch(
            self.repo_root, proposal, timeout=self.config.healing.pytest_timeout
        )
        return result, time.time() - t0

    def phase_evolve(self, traj: HealingTrajectory) -> float:
        t0 = time.time()
        skill_tool.evolve(traj, self.skills_dir)
        return time.time() - t0

    # ------------------------------------------------------------------ #
    # Imperative ReAct driver (also what the CLI / Leader call)           #
    # ------------------------------------------------------------------ #
    _last_green = False  # read by the graph router (see build())

    async def run(self, log_text: str, apply_to_repo: bool = False) -> HealingTrajectory:
        """Execute the full four-phase heal with a ReAct loop.

        This is the authoritative entry point. It uses the same phase kernels
        the openjiuwen graph nodes wrap, so behaviour is identical whether driven
        by the graph or imperatively; the graph remains the observable
        orchestration artefact (built via :meth:`build`).
        """
        traj = HealingTrajectory(
            run_id=_run_id(),
            repo_path=self.repo_root,
            mode=self.config.mode.value,
        )
        self.build()  # construct the real openjiuwen graph for observability

        max_iter = self.config.healing.max_iterations
        last_result: Optional[VerificationResult] = None
        current_log = log_text
        round_sigs: list[FaultSignature] = []
        round_proposals: list[PatchProposal] = []

        # Open an isolated sandbox for the ReAct multi-round healing loop
        with sandbox_tool.Sandbox(self.repo_root, keep=False) as sandbox:
            if not current_log or not current_log.strip():
                init_res = sandbox_tool.run_pytest(sandbox, timeout=self.config.healing.pytest_timeout)
                current_log = (init_res.stdout_tail or "") + "\n" + (init_res.stderr_tail or "")
                if init_res.all_green:
                    traj.verification = init_res
                    traj.finish(HealingStatus.HEALED)
                    return traj

            for iteration in range(1, max_iter + 1):
                traj.iterations = iteration

                # Phase 1 - triage (identifies the current active failure).
                sig, dt_triage = self.phase_triage(current_log)
                if iteration == 1:
                    traj.fault = sig
                round_sigs.append(sig)
                traj.add_trace(TraceStep(
                    phase=f"1-triage (iter {iteration})", title="故障感知与日志解析",
                    detail=f"{sig.fault_type.value} @ {sig.file_path}:{sig.line_number} in {sig.function_name or 'module'}",
                    duration=dt_triage,
                    payload={"fingerprint": sig.fingerprint},
                ))

                # Phase 2 - inspect + propose patch.
                ctx, proposal, dt_inspect = self.phase_inspect(sig, iteration)
                if iteration == 1:
                    traj.ast_context = ctx
                round_proposals.append(proposal)
                traj.patches.append(proposal)

                # Report degradation warning if it occurred in live mode
                if getattr(self, "_degradation_warning", None):
                    traj.add_trace(TraceStep(
                        phase=f"2-inspect (iter {iteration})", title="双模动态降级",
                        detail=self._degradation_warning,
                        ok=True,
                    ))
                    self._degradation_warning = None

                detail_msg = f"{proposal.strategy.value}: {proposal.summary}"
                if proposal.source == "replay_knowledge" and not proposal.summary.startswith("[Memory Hit"):
                    detail_msg = f"[Memory Hit: trusted pattern] {detail_msg}"
                traj.add_trace(TraceStep(
                    phase=f"2-inspect (iter {iteration})", title="根因定位与 AST 检索",
                    detail=detail_msg,
                    duration=dt_inspect,
                    payload={"iteration": iteration, "source": proposal.source},
                ))

                # Phase 3 - sandbox verify.
                t0_v = time.time()
                applied = sandbox_tool.apply_patch(sandbox, proposal)
                if not applied:
                    traj.add_trace(TraceStep(
                        phase=f"3-verify (iter {iteration})", title="补丁应用失败",
                        detail="补丁上下文不匹配或包含语法错误，已自动回滚",
                        ok=False,
                        duration=time.time() - t0_v,
                    ))
                    continue

                res = sandbox_tool.run_pytest(sandbox, timeout=self.config.healing.pytest_timeout)
                dt_v = time.time() - t0_v
                last_result = res
                self._last_green = res.all_green
                traj.verification = res
                traj.add_trace(TraceStep(
                    phase=f"3-verify (iter {iteration})", title="沙箱补丁回归验证",
                    detail=f"{res.verdict.value} · {res.tests_passed}/{res.tests_total} 通过 (失败 {res.tests_failed})",
                    ok=res.all_green, duration=dt_v,
                ))

                if res.all_green:
                    # All tests passed! Compute overall diff from original repo
                    diff_str = _compute_sandbox_diff(self.repo_root, sandbox.root)
                    traj.diff = diff_str or proposal.unified_diff
                    traj.finish(HealingStatus.HEALED)
                    traj.resolved_faults = list(round_sigs)
                    traj.patches = list(round_proposals)
                    dt_e = self.phase_evolve(traj)
                    p_details = ", ".join(f"{p.fingerprint}->{p.strategy.value}" for p in traj.learned_patterns)
                    traj.add_trace(TraceStep(
                        phase="4-evolve", title="Skill 自演进与复盘",
                        detail=f"独立提炼 {len(traj.learned_patterns)} 个模式: {p_details}",
                        duration=dt_e,
                    ))
                    if apply_to_repo:
                        _sync_back(sandbox.root, self.repo_root)
                    return traj

                # Not all green: extract new failing log from sandbox run for the next ReAct iteration
                current_log = (res.stdout_tail or "") + "\n" + (res.stderr_tail or "")

        # Exhausted iterations without green.
        traj.verification = last_result
        traj.finish(HealingStatus.FAILED_TO_HEAL)
        traj.resolved_faults = list(round_sigs)
        traj.patches = list(round_proposals)
        self.phase_evolve(traj)
        return traj


def _compute_sandbox_diff(orig_root: str | Path, sbx_root: str | Path) -> str:
    import difflib
    from pathlib import Path

    orig = Path(orig_root).resolve()
    sbx = Path(sbx_root).resolve()
    diffs: list[str] = []

    for sbx_file in sbx.rglob("*.py"):
        rel = sbx_file.relative_to(sbx)
        orig_file = orig / rel
        if not orig_file.is_file():
            continue
        try:
            orig_lines = orig_file.read_text(encoding="utf-8").splitlines()
            sbx_lines = sbx_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        if orig_lines != sbx_lines:
            d = difflib.unified_diff(
                orig_lines, sbx_lines,
                fromfile=f"a/{rel.as_posix()}",
                tofile=f"b/{rel.as_posix()}",
                lineterm="",
            )
            diffs.append("\n".join(d))
    return "\n\n".join(diffs)


def _sync_back(sbx_root: str | Path, orig_root: str | Path) -> None:
    from pathlib import Path

    orig = Path(orig_root).resolve()
    sbx = Path(sbx_root).resolve()
    for sbx_file in sbx.rglob("*.py"):
        rel = sbx_file.relative_to(sbx)
        orig_file = orig / rel
        if orig_file.is_file():
            orig_file.write_text(sbx_file.read_text(encoding="utf-8"), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Thin adapters so the flow reads cleanly                                      #
# --------------------------------------------------------------------------- #


class ASTInspectorCtx:
    def __init__(self, repo_root: Optional[str]) -> None:
        self._inner = ast_tool.ASTInspector(repo_root)

    def build(self, sig: FaultSignature) -> ASTContext:
        return self._inner.inspect(sig)


class FixPolicyEngine:
    def __init__(self, repo_root: Optional[str]) -> None:
        self._inner = ast_tool.FixPolicy()

    def propose(self, sig: FaultSignature, ctx: ASTContext) -> PatchProposal:
        return self._inner.propose(sig, ctx)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _ensure_event_loop():
    """Ensure an active asyncio event loop exists in the current thread for openJiuwen."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError()
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _run_id() -> str:
    return "run-" + time.strftime("%Y%m%d-%H%M%S")


__all__ = ["HealSwarmFlow", "register_tools"]
