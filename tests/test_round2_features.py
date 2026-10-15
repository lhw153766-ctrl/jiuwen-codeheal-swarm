"""Unit and integration tests for Round 2 enhancements:
1. Multi-fault independent distillation (no template mismatch / "张冠李戴")
2. Experience memory recall (trusted pattern hit boosts confidence to 0.95 & tags replay_knowledge)
3. Dual-mode graceful degradation & fallback (Live LLM failure falls back to FixPolicy)
4. Config llm property alias and SwarmLeader component builders
5. FixPolicy extended rules (KeyError, AttributeError, TypeError, SyntaxError)
6. Sandbox state checkpointing and syntax pre-check rollback
7. Multi-workflow dynamic routing by Intent
"""

from __future__ import annotations

from pathlib import Path
import pytest

from jiuwen_codeheal.config import CodeHealConfig, EngineMode
from jiuwen_codeheal.schemas import (
    ASTContext,
    FaultSignature,
    FaultType,
    HealingStatus,
    HealingTrajectory,
    LearnedPattern,
    PatchHunk,
    PatchProposal,
    PatchStrategy,
)
from jiuwen_codeheal.swarm_leader import (
    CodeInspectorTeammate,
    Intent,
    SwarmLeader,
)
from jiuwen_codeheal.tools.ast_inspector_tool import ASTInspector, FixPolicy
from jiuwen_codeheal.tools.sandbox_verifier_tool import (
    Sandbox,
    apply_patch,
    verify_patch,
)
from jiuwen_codeheal.tools.skill_evolver_tool import (
    SkillLibrary,
    distill,
    distill_pair,
    evolve,
    is_trusted,
    lookup_pattern,
)
from jiuwen_codeheal.workflows.heal_swarmflow import HealSwarmFlow


def test_config_llm_property_alias():
    cfg = CodeHealConfig()
    assert cfg.llm is cfg.client
    assert cfg.llm.model_name == "deepseek-chat"


def test_multi_fault_independent_distillation(tmp_path: Path):
    """Verify that multiple faults in one trajectory are distilled independently."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    sig1 = FaultSignature(
        fault_type=FaultType.INDEX_ERROR,
        file_path="src/calc.py",
        function_name="find_max",
        fingerprint="fp_find_max_001",
    )
    prop1 = PatchProposal(
        strategy=PatchStrategy.BOUNDARY_GUARD,
        hunks=[PatchHunk(file="src/calc.py", old="seq[i + 1]", new="seq[i]")],
    )

    sig2 = FaultSignature(
        fault_type=FaultType.VALUE_ERROR,
        file_path="src/calc.py",
        function_name="average",
        fingerprint="fp_average_002",
    )
    prop2 = PatchProposal(
        strategy=PatchStrategy.BOUNDARY_GUARD,
        hunks=[PatchHunk(file="src/calc.py", old="sum(v)/len(v)", new="if not v: return 0.0")],
    )

    traj = HealingTrajectory(
        run_id="run-multi-001",
        repo_path=str(tmp_path),
        status=HealingStatus.HEALED,
        resolved_faults=[sig1, sig2],
        patches=[prop1, prop2],
    )

    # Distill and evolve
    evolved = evolve(traj, skills_dir)
    assert evolved is not None
    assert len(traj.learned_patterns) == 2

    # Check pattern 1
    p1 = traj.learned_patterns[0]
    assert p1.fingerprint == "fp_find_max_001"
    assert p1.fix_template == "seq[i]"

    # Check pattern 2
    p2 = traj.learned_patterns[1]
    assert p2.fingerprint == "fp_average_002"
    assert p2.fix_template == "if not v: return 0.0"

    # Verify both are persisted in the JSON library
    lib = SkillLibrary(skills_dir)
    patterns = lib.load_patterns()
    assert len(patterns) == 2
    fps = {p.fingerprint for p in patterns}
    assert "fp_find_max_001" in fps
    assert "fp_average_002" in fps


def test_memory_recall_priority(tmp_path: Path):
    """Verify that a trusted pattern triggers memory recall with 0.95 confidence."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Pre-seed library with trusted pattern (occurrences=2, success=2)
    lib = SkillLibrary(skills_dir)
    p = LearnedPattern(
        fingerprint="fp_known_001",
        fault_type=FaultType.INDEX_ERROR,
        root_cause="Index bounds guard",
        strategy=PatchStrategy.BOUNDARY_GUARD,
        fix_template="def find_max(seq):\n    return max(seq)",
        occurrences=2,
        success_count=2,
    )
    lib.save_patterns([p])
    assert is_trusted(p)

    sig = FaultSignature(
        fault_type=FaultType.INDEX_ERROR,
        file_path="src/calc.py",
        function_name="find_max",
        fingerprint="fp_known_001",
    )

    # Inspect teammate with memory recall
    inspector = CodeInspectorTeammate(str(tmp_path), skills_dir=str(skills_dir))
    ctx, proposal, dt = inspector.inspect(sig, iteration=1)

    assert proposal.source == "replay_knowledge"
    assert proposal.confidence == 0.95
    assert "[Memory Hit: trusted pattern]" in proposal.summary


def test_dual_mode_graceful_degradation(tmp_path: Path):
    """Verify that Live LLM exceptions trigger graceful fallback to FixPolicy without crash."""
    config = CodeHealConfig(
        mode=EngineMode.LIVE,
        client={"api_key": "fake-key-triggers-fallback", "provider": "deepseek"},
    )
    assert config.is_live is True

    flow = HealSwarmFlow(config, repo_root=str(tmp_path), skills_dir=str(tmp_path / "skills"))
    sig = FaultSignature(
        fault_type=FaultType.VALUE_ERROR,
        file_path="calc.py",
        function_name="average",
        fingerprint="fp_live_test",
    )

    # Mock source file in tmp_path
    (tmp_path / "calc.py").write_text(
        "def average(values):\n    return sum(values) / len(values)\n", encoding="utf-8"
    )

    ctx, proposal, dt = flow.phase_inspect(sig, iteration=1)
    # Propose must succeed via fallback!
    assert proposal is not None
    assert proposal.strategy == PatchStrategy.BOUNDARY_GUARD
    assert getattr(flow, "_degradation_warning", None) is not None
    assert "Live LLM 异常" in flow._degradation_warning


def test_fix_policy_extended_rules(tmp_path: Path):
    """Test KeyError, AttributeError, TypeError, and SyntaxError policy rewrites."""
    policy = FixPolicy()

    # 1. KeyError
    src_key = "def get_val(d):\n    return d['name']\n"
    ctx_key = ASTContext(
        target_file="test.py", target_line=2,
        function=ASTInspector(".")._build_func_context(src_key) if hasattr(ASTInspector, "_build_func_context") else None
    )
    # Manually populate function context if needed
    from jiuwen_codeheal.schemas import FunctionContext
    ctx_key.function = FunctionContext(name="get_val", source=src_key, lineno=1, end_lineno=2)
    sig_key = FaultSignature(fault_type=FaultType.KEY_ERROR, file_path="test.py")
    prop_key = policy.propose(sig_key, ctx_key)
    assert prop_key.strategy == PatchStrategy.NONE_CHECK
    assert ".get(" in prop_key.hunks[0].new

    # 2. AttributeError (None guard)
    src_attr = "def get_attr(user):\n    return user.email\n"
    ctx_attr = ASTContext(target_file="test.py", target_line=2)
    ctx_attr.function = FunctionContext(name="get_attr", source=src_attr, lineno=1, end_lineno=2)
    sig_attr = FaultSignature(fault_type=FaultType.ATTRIBUTE_ERROR, file_path="test.py")
    prop_attr = policy.propose(sig_attr, ctx_attr)
    assert prop_attr.strategy == PatchStrategy.NONE_CHECK
    assert "if user is None:" in prop_attr.hunks[0].new

    # 3. TypeError (type coercion)
    src_type = "def concat(prefix, count):\n    return prefix + count\n"
    ctx_type = ASTContext(target_file="test.py", target_line=2)
    ctx_type.function = FunctionContext(name="concat", source=src_type, lineno=1, end_lineno=2)
    sig_type = FaultSignature(fault_type=FaultType.TYPE_ERROR, file_path="test.py", message="can only concatenate str (not 'int') to str")
    prop_type = policy.propose(sig_type, ctx_type)
    assert prop_type.strategy == PatchStrategy.TYPE_COERCION
    assert "str(" in prop_type.hunks[0].new

    # 4. SyntaxError (missing colon)
    src_syn = "def check(x)\n    return x > 0\n"
    ctx_syn = ASTContext(target_file="test.py", target_line=1)
    ctx_syn.function = FunctionContext(name="check", source=src_syn, lineno=1, end_lineno=2)
    sig_syn = FaultSignature(fault_type=FaultType.SYNTAX_ERROR, file_path="test.py")
    prop_syn = policy.propose(sig_syn, ctx_syn)
    assert "def check(x):" in prop_syn.hunks[0].new


def test_sandbox_checkpoint_and_syntax_rollback(tmp_path: Path):
    """Test state checkpointing and instant rollback when patch introduces a SyntaxError."""
    repo = tmp_path / "sandbox_repo"
    repo.mkdir()
    (repo / "module.py").write_text("def valid_code():\n    return 42\n", encoding="utf-8")

    with Sandbox(str(repo)) as sb:
        # Checkpoint capture
        cp = sb.save_checkpoint()
        assert "module.py" in cp
        assert "def valid_code():" in cp["module.py"]

        # Attempt to apply a patch that introduces a SyntaxError
        bad_syntax_patch = PatchProposal(
            strategy=PatchStrategy.BOUNDARY_GUARD,
            hunks=[
                PatchHunk(
                    file="module.py",
                    old="def valid_code():\n    return 42\n",
                    new="def valid_code(:\n    return broken syntax!!\n",
                )
            ],
        )

        # apply_patch must reject and atomically rollback
        applied = apply_patch(sb, bad_syntax_patch)
        assert applied is False

        # File must remain original and syntactically valid
        content = sb.abs_read("module.py")
        assert content == "def valid_code():\n    return 42\n"


def test_multi_workflow_routing_and_dispatch(tmp_path: Path):
    """Test multi-workflow dynamic routing and graph topology."""
    config = CodeHealConfig()
    leader = SwarmLeader(config)

    # 1. Inspect Workflow (Diagnostic DAG)
    inspect_wf = leader.build_workflow_by_intent(Intent.INSPECT_ONLY, str(tmp_path), str(tmp_path / "skills"))
    assert inspect_wf is not None
    assert inspect_wf.card.name == "CodeHealInspectFlow"

    # 2. Heal Workflow (Full DAG)
    heal_wf = leader.build_workflow_by_intent(Intent.HEAL_CI, str(tmp_path), str(tmp_path / "skills"))
    assert heal_wf is not None
    assert heal_wf.card.name == "CodeHealSwarmFlow"

    # 3. Dynamic Dispatcher
    dummy_log = "ValueError: math domain error"
    (tmp_path / "calc.py").write_text("def f(): pass\n", encoding="utf-8")
    inspect_res = leader.dispatch_workflow(Intent.INSPECT_ONLY, dummy_log, str(tmp_path))
    assert "fault" in inspect_res
    assert "ast_context" in inspect_res


def test_skill_distill_pair_direct():
    """Verify distill_pair function directly for healed and unhealed states."""
    sig = FaultSignature(
        fault_type=FaultType.INDEX_ERROR,
        file_path="src/main.py",
        function_name="process",
        fingerprint="fp_pair_test",
    )
    prop = PatchProposal(
        strategy=PatchStrategy.BOUNDARY_GUARD,
        hunks=[PatchHunk(file="src/main.py", old="a[i]", new="a[i-1]")],
    )
    pat_healed = distill_pair(sig, prop, healed=True)
    assert pat_healed.fingerprint == "fp_pair_test"
    assert pat_healed.strategy == PatchStrategy.BOUNDARY_GUARD
    assert pat_healed.success_count == 1
    assert pat_healed.occurrences == 1

    pat_failed = distill_pair(sig, prop, healed=False)
    assert pat_failed.success_count == 0


def test_fix_policy_unknown_fallback():
    """Verify that unsupported fault types return UNKNOWN strategy honestly."""
    policy = FixPolicy()
    from jiuwen_codeheal.schemas import FunctionContext
    ctx = ASTContext(target_file="test.py", target_line=1)
    ctx.function = FunctionContext(name="fn", source="def fn(): pass\n", lineno=1, end_lineno=1)
    sig = FaultSignature(fault_type=FaultType.UNKNOWN, file_path="test.py")
    prop = policy.propose(sig, ctx)
    assert prop.strategy == PatchStrategy.UNKNOWN
    assert prop.confidence < 0.5
