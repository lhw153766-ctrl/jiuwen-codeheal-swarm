"""End-to-end tests for Jiuwen-CodeHeal Swarm and OpenJiuwen Workflow integration."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import pytest

from jiuwen_codeheal.config import CodeHealConfig
from jiuwen_codeheal.schemas import HealingStatus, PatchStrategy
from jiuwen_codeheal.swarm_leader import Intent, SwarmLeader
from jiuwen_codeheal.tools.skill_evolver_tool import SkillLibrary
from jiuwen_codeheal.workflows.heal_swarmflow import HealSwarmFlow, register_tools


@pytest.fixture
def repo_root() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / "examples" / "buggy_repo_demo"


def test_leader_intent_recognition():
    leader = SwarmLeader()
    assert leader.recognize_intent("修复当前 CI 故障") == Intent.HEAL_CI
    assert leader.recognize_intent("仅分析报错日志") == Intent.INSPECT_ONLY
    assert leader.recognize_intent("跑一下自测 demo") == Intent.SELF_TEST


def test_openjiuwen_workflow_graph_construction(repo_root: Path, tmp_path: Path):
    """Verify that the genuine openjiuwen Workflow graph builds and registers tools."""
    config = CodeHealConfig()
    flow = HealSwarmFlow(config, str(repo_root), str(tmp_path))
    wf = flow.build()
    assert wf is not None
    assert wf.card.name == "CodeHealSwarmFlow"
    assert "triage" in flow.tool_ids
    assert "inspect" in flow.tool_ids
    assert "verify" in flow.tool_ids
    assert "evolve" in flow.tool_ids


def test_e2e_swarm_healing_red_to_green(repo_root: Path, tmp_path: Path):
    """End-to-end test: verify buggy demo transitions from 4 failing tests to 6 passing tests."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    config = CodeHealConfig()
    leader = SwarmLeader(config)

    # Empty initial log triggers automatic sandbox test run to capture active failures
    traj = leader.heal(log_text="", repo_root=str(repo_root), skills_dir=str(skills_dir))

    assert traj.status == HealingStatus.HEALED
    assert traj.iterations >= 1
    assert traj.verification is not None
    assert traj.verification.all_green is True
    assert traj.verification.tests_total == 6
    assert traj.verification.tests_passed == 6
    assert traj.verification.tests_failed == 0

    # Diff should reflect fixes for both find_max and average
    assert traj.diff != ""
    assert "find_max" in traj.diff
    assert "if not values" in traj.diff

    # Verify skill evolution recorded pattern
    lib = SkillLibrary(skills_dir)
    patterns = lib.load_patterns()
    assert len(patterns) >= 1
    assert patterns[0].strategy == PatchStrategy.BOUNDARY_GUARD
    assert (skills_dir / "ci_healing_memory.md").is_file()
