"""Skill Evolver Tool (Phase 4 - Skill Evolve & Reporter Teammate).

Implements JiuwenSwarm's **Skill Self-Evolution** idea: after a successful
heal, distill the run into a reusable rule ``error fingerprint -> root cause
-> fix strategy`` and persist it into the repository's skill memory so the
system gets smarter over time.

Two artefacts are maintained, both human- and machine-readable:

* ``skills/ci_healing_memory.md``   - narrative, append-only Markdown log.
* ``skills/learned_patterns.json``  - structured, deduplicated JSON library.

The evolver is idempotent: a pattern with a known fingerprint is *updated*
(incrementing occurrence / success counters) rather than duplicated, and a
minimum confidence threshold gates whether a learned pattern is trusted enough
to auto-apply in future runs (see :mod:`heal_swarmflow`).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from jiuwen_codeheal.schemas import (
    FaultSignature,
    FaultType,
    HealingTrajectory,
    LearnedPattern,
    PatchStrategy,
)


# --------------------------------------------------------------------------- #
# Confidence gate                                                              #
# --------------------------------------------------------------------------- #

#: A learned pattern must reach this success ratio before the replay policy will
#: auto-apply it without human review. Occurrences are folded in so a single
#: lucky hit cannot poison the library.
MIN_AUTO_CONFIDENCE = 0.6
MIN_OCCURRENCES = 2


def is_trusted(pattern: LearnedPattern) -> bool:
    """Whether *pattern* is confident + frequent enough to auto-apply."""
    if pattern.occurrences < MIN_OCCURRENCES:
        return False
    ratio = pattern.success_count / max(1, pattern.occurrences)
    return ratio >= MIN_AUTO_CONFIDENCE


# --------------------------------------------------------------------------- #
# Library I/O                                                                  #
# --------------------------------------------------------------------------- #


class SkillLibrary:
    """Read/write the skill memory for a repository."""

    def __init__(self, skills_dir: str | Path) -> None:
        self.dir = Path(skills_dir)
        self.json_path = self.dir / "learned_patterns.json"
        self.md_path = self.dir / "ci_healing_memory.md"

    # ------------------------------------------------------------------ #
    def load_patterns(self) -> list[LearnedPattern]:
        if not self.json_path.is_file():
            return []
        try:
            raw = json.loads(self.json_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        out: list[LearnedPattern] = []
        for item in raw if isinstance(raw, list) else raw.get("patterns", []):
            try:
                out.append(LearnedPattern(**item))
            except Exception:
                continue
        return out

    def save_patterns(self, patterns: list[LearnedPattern]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "0.1.0",
            "updated_at": time.time(),
            "count": len(patterns),
            "patterns": [p.to_dict() for p in patterns],
        }
        self.json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------ #
    def append_markdown(self, traj: HealingTrajectory, pattern: LearnedPattern) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.md_path.is_file():
            self.md_path.write_text(
                "# CI Healing Memory\n\n"
                "Auto-evolved skill log for Jiuwen-CodeHeal Swarm. Each entry "
                "captures a distilled ``fingerprint -> root cause -> strategy`` "
                "rule discovered while healing real CI failures.\n\n",
                encoding="utf-8",
            )
        dur = traj.duration
        verdict = "✅ HEALED" if traj.status.value == "healed" else "❌ " + traj.status.value.upper()
        entry = (
            f"\n## [{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(traj.started_at))}] "
            f"{pattern.fault_type.value} @ `{pattern.example_file or 'n/a'}` — {verdict}\n\n"
            f"- **Fingerprint**: `{pattern.fingerprint}`\n"
            f"- **Root cause**: {pattern.root_cause}\n"
            f"- **Strategy**: `{pattern.strategy.value}`\n"
            f"- **Fix template**:\n\n```python\n{pattern.fix_template.strip()}\n```\n"
            f"- **Occurrences**: {pattern.occurrences} (success {pattern.success_count})\n"
            f"- **Run**: {traj.run_id} · {dur:.2f}s · mode={traj.mode}\n"
        )
        with self.md_path.open("a", encoding="utf-8") as fh:
            fh.write(entry)

    # ------------------------------------------------------------------ #
    def find(self, fingerprint: str) -> Optional[LearnedPattern]:
        for p in self.load_patterns():
            if p.fingerprint == fingerprint:
                return p
        return None


# --------------------------------------------------------------------------- #
# Distillation                                                                 #
# --------------------------------------------------------------------------- #


def distill_pair(
    sig: FaultSignature, proposal: PatchProposal, healed: bool = True
) -> LearnedPattern:
    """Distil a specific (FaultSignature, PatchProposal) pair into a LearnedPattern."""
    template = ""
    if proposal.hunks:
        template = proposal.hunks[0].new
    elif proposal.unified_diff:
        template = proposal.unified_diff

    return LearnedPattern(
        fingerprint=sig.fingerprint,
        fault_type=sig.fault_type,
        root_cause=_root_cause_text(sig),
        strategy=proposal.strategy,
        fix_template=template,
        occurrences=1,
        success_count=1 if healed else 0,
        example_file=sig.file_path or "",
        updated_at=time.time(),
    )


def distill(traj: HealingTrajectory) -> Optional[LearnedPattern]:
    """Turn a completed trajectory into a :class:`LearnedPattern`.

    Only successfully healed runs produce a trusted pattern; failed runs are
    still recorded (with success_count unchanged) so we avoid re-trying dead
    strategies, but they are flagged as not-yet-trusted.
    """
    sig = traj.fault
    if sig is None:
        return None

    healed = traj.status.value == "healed"

    # Match patch corresponding to sig's file / fault if multiple patches exist
    matching_patch = None
    if sig.file_path:
        for p in reversed(traj.patches):
            if any(h.file == sig.file_path for h in p.hunks):
                matching_patch = p
                break
    if matching_patch is None and traj.patches:
        matching_patch = traj.patches[0]

    strategy = matching_patch.strategy if matching_patch else _dominant_strategy(traj)
    fix_template = ""
    if matching_patch and matching_patch.hunks:
        fix_template = matching_patch.hunks[0].new
    elif matching_patch and matching_patch.unified_diff:
        fix_template = matching_patch.unified_diff
    else:
        fix_template = _fix_template(traj)

    pattern = LearnedPattern(
        fingerprint=sig.fingerprint,
        fault_type=sig.fault_type,
        root_cause=_root_cause_text(sig),
        strategy=strategy,
        fix_template=fix_template,
        occurrences=1,
        success_count=1 if healed else 0,
        example_file=sig.file_path or "",
        updated_at=time.time(),
    )
    return pattern


def _dominant_strategy(traj: HealingTrajectory) -> PatchStrategy:
    for p in reversed(traj.patches):
        if p.strategy != PatchStrategy.UNKNOWN:
            return p.strategy
    return PatchStrategy.UNKNOWN


def _fix_template(traj: HealingTrajectory) -> str:
    for p in reversed(traj.patches):
        if p.hunks:
            return p.hunks[0].new
        if p.unified_diff:
            return p.unified_diff
    return ""


def _root_cause_text(sig: FaultSignature) -> str:
    parts = [f"{sig.fault_type.value}"]
    if sig.file_path:
        parts.append(f"in `{sig.file_path}`")
    if sig.function_name:
        parts.append(f"function `{sig.function_name}`")
    if sig.message:
        parts.append(f"— {sig.message.splitlines()[0][:120]}")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# High-level evolve entry point                                                #
# --------------------------------------------------------------------------- #


def evolve(traj: HealingTrajectory, skills_dir: str | Path) -> Optional[LearnedPattern]:
    """Distil *traj*, merge into the library, and persist both artefacts.

    When *traj* contains multiple resolved faults in `traj.resolved_faults` paired
    with `traj.patches`, each pair is independently distilled and merged into the
    skill library, populating `traj.learned_patterns`.
    """
    healed = traj.status.value == "healed"
    lib = SkillLibrary(skills_dir)
    patterns = lib.load_patterns()

    # Multi-fault independent distillation
    if traj.resolved_faults and len(traj.resolved_faults) == len(traj.patches):
        evolved_list: list[LearnedPattern] = []
        for sig, prop in zip(traj.resolved_faults, traj.patches):
            pat = distill_pair(sig, prop, healed=healed)
            matched = False
            for p in patterns:
                if p.fingerprint == pat.fingerprint:
                    p.occurrences += 1
                    p.success_count += pat.success_count
                    p.root_cause = pat.root_cause
                    p.strategy = pat.strategy
                    p.fix_template = pat.fix_template or p.fix_template
                    p.example_file = pat.example_file or p.example_file
                    p.updated_at = time.time()
                    lib.append_markdown(traj, p)
                    evolved_list.append(p)
                    matched = True
                    break
            if not matched:
                patterns.append(pat)
                lib.append_markdown(traj, pat)
                evolved_list.append(pat)
        lib.save_patterns(patterns)
        traj.learned_patterns = evolved_list
        if evolved_list:
            traj.learned_pattern = evolved_list[-1]
            return evolved_list[-1]
        return None

    # Single-fault standard distillation
    pattern = distill(traj)
    if pattern is None:
        return None

    for p in patterns:
        if p.fingerprint == pattern.fingerprint:
            p.occurrences += 1
            p.success_count += pattern.success_count
            p.root_cause = pattern.root_cause
            p.strategy = pattern.strategy
            p.fix_template = pattern.fix_template or p.fix_template
            p.example_file = pattern.example_file or p.example_file
            p.updated_at = time.time()
            lib.save_patterns(patterns)
            lib.append_markdown(traj, p)
            traj.learned_patterns = [p]
            traj.learned_pattern = p
            return p

    patterns.append(pattern)
    lib.save_patterns(patterns)
    lib.append_markdown(traj, pattern)
    traj.learned_patterns = [pattern]
    traj.learned_pattern = pattern
    return pattern


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #


def render_report(traj: HealingTrajectory) -> str:
    """Render the structured Markdown healing report."""
    sig = traj.fault
    lines: list[str] = []
    lines.append(f"# 自愈报告 · {traj.run_id}\n")
    lines.append(f"- **状态**: `{traj.status.value}`")
    lines.append(f"- **模式**: {traj.mode}")
    lines.append(f"- **耗时**: {traj.duration:.2f}s · 迭代 {traj.iterations} 轮")
    lines.append(f"- **仓库**: `{traj.repo_path}`\n")

    if sig:
        lines.append("## 1. 故障感知 (Log Triage)")
        lines.append(f"- 类型: `{sig.fault_type.value}` · 异常: `{sig.exception_type}`")
        lines.append(f"- 位置: `{sig.file_path}:{sig.line_number}` in `{sig.function_name}`")
        lines.append(f"- 失败用例: {len(sig.failed_tests)} 个 · 堆栈帧: {len(sig.stack_frames)}")
        lines.append(f"- 指纹: `{sig.fingerprint}`\n")

    if traj.ast_context and traj.ast_context.function:
        f = traj.ast_context.function
        lines.append("## 2. 根因定位 (AST Inspector)")
        lines.append(f"- 精确定位函数: `{f.signature}` ({f.lineno}-{f.end_lineno})")
        lines.append(f"- 调用链: {' -> '.join(traj.ast_context.call_chain[:8])}")
        lines.append(f"- 上下文压缩: 仅注入 {len(traj.ast_context.compressed_context)} 字符，避免整文件塞入\n")

    if traj.patches:
        lines.append("## 3. 补丁提案 (Patch & Sandbox Verifier)")
        for i, p in enumerate(traj.patches, 1):
            lines.append(f"### 提案 {i} · 策略 `{p.strategy.value}` · 置信度 {p.confidence:.2f}")
            lines.append(f"- {p.summary}")
            if p.unified_diff:
                lines.append("\n```diff\n" + p.unified_diff + "\n```\n")

    v = traj.verification
    if v:
        lines.append("## 4. 沙箱回归验证")
        lines.append(f"- 判定: `{v.verdict.value}` · returncode={v.return_code}")
        lines.append(f"- 测试: {v.tests_passed}/{v.tests_total} 通过 · 失败 {v.tests_failed}")
        if v.still_failing:
            lines.append(f"- 仍失败: {', '.join(v.still_failing[:5])}")
        lines.append(f"- 沙箱: `{v.sandbox_path}`\n")

    patterns_to_show = traj.learned_patterns or ([traj.learned_pattern] if traj.learned_pattern else [])
    if patterns_to_show:
        lines.append("## 5. Skill 自演进")
        for lp in patterns_to_show:
            trusted_str = "可信=True" if is_trusted(lp) else "可信=False"
            lines.append(f"- 提炼模式: `{lp.fingerprint}` -> `{lp.strategy.value}`")
            lines.append(f"  - 出现 {lp.occurrences} 次 · 成功 {lp.success_count} 次 · {trusted_str}")
            if lp.root_cause:
                lines.append(f"  - 根因: {lp.root_cause}")
        lines.append("- 已沉淀到 `skills/ci_healing_memory.md` 与 `skills/learned_patterns.json`\n")

    lines.append("## 6. 可观测性 Trace")
    for step in traj.trace:
        mark = "✓" if step.ok else "✗"
        lines.append(f"- {mark} [{step.phase}] {step.title} ({step.duration:.2f}s) {step.detail}")

    return "\n".join(lines)


def git_diff(traj: HealingTrajectory) -> str:
    """Return the final unified diff (best-effort, from the applied patch)."""
    return traj.diff or (traj.patches[-1].unified_diff if traj.patches else "")


# --------------------------------------------------------------------------- #
# Functional wrappers (openjiuwen @tool targets)                               #
# --------------------------------------------------------------------------- #


def lookup_pattern(fingerprint: str, skills_dir: str) -> dict:
    """Look up a learned pattern by fingerprint (used by the replay policy)."""
    lib = SkillLibrary(skills_dir)
    p = lib.find(fingerprint)
    if p is None:
        return {"found": False}
    return {"found": True, "trusted": is_trusted(p), "pattern": p.to_dict()}


def record_healing(trajectory: dict, skills_dir: str) -> dict:
    """Persist a trajectory into the skill library and return the pattern."""
    traj = HealingTrajectory(**trajectory)
    pattern = evolve(traj, skills_dir)
    return {"pattern": pattern.to_dict() if pattern else None}
