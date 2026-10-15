"""Terminal front-end for the Jiuwen-CodeHeal Swarm.

Usage::

    python -m jiuwen_codeheal.cli --demo          # end-to-end heal of the demo repo
    python -m jiuwen_codeheal.cli --repo PATH --log LOG   # heal a real repo + log
    python -m jiuwen_codeheal.cli --self-test     # run the swarm's own test suite
    python -m jiuwen_codeheal.cli --inspect LOG   # triage + AST only, no patching

The CLI prints a colour-coded, four-phase report using :mod:`rich`. Every run
emits the *real* terminal output (no placeholders) that is also captured into
``docs/`` and ``README.md`` for the competition submission.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

from jiuwen_codeheal import __version__
from jiuwen_codeheal.config import CodeHealConfig
from jiuwen_codeheal.schemas import HealingTrajectory
from jiuwen_codeheal.swarm_leader import Intent, SwarmLeader
from jiuwen_codeheal.tools import skill_evolver_tool as skill_tool

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DEMO_REPO = _REPO_ROOT / "examples" / "buggy_repo_demo"
_DEFAULT_SKILLS = _REPO_ROOT / "skills"


def _rich():
    """Return rich modules, degrading gracefully if unavailable."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.tree import Tree
        return Console, Panel, Table, Tree
    except Exception:  # pragma: no cover - rich is a declared dependency
        return None, None, None, None


# --------------------------------------------------------------------------- #
# Demo log generation                                                          #
# --------------------------------------------------------------------------- #


def _capture_demo_log(repo: Path) -> str:
    """Run pytest in the demo repo to capture a *real* failing log for triage.

    This makes the demo honest: the log the swarm triages is the actual output of
    the actual broken repo, not a hand-written fixture.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-v", "--no-header", "--tb=short", "-p", "no:cacheprovider"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return (proc.stdout or "") + "\n" + (proc.stderr or "")
    except Exception as exc:  # pragma: no cover
        return f"<failed to capture demo log: {exc}>"


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #


def _print_banner(console, mode: str, repo: Path) -> None:
    if console is None:
        print(f"\n=== Jiuwen-CodeHeal Swarm v{__version__} · mode={mode} ===")
        print(f"repo: {repo}\n")
        return
    from rich.panel import Panel

    console.print(
        Panel.fit(
            f"[bold cyan]Jiuwen-CodeHeal Swarm[/bold cyan] v{__version__}\n"
            f"openJiuwen + JiuwenSwarm 多智能体协同 · 模式 [yellow]{mode}[/yellow]\n"
            f"仓库: [green]{repo}[/green]",
            border_style="cyan",
        )
    )


def _print_trace(console, traj: HealingTrajectory) -> None:
    if console is None:
        print("\n--- 阶段轨迹 ---")
        for s in traj.trace:
            mark = "[OK]" if s.ok else "[FAIL]"
            print(f"{mark} [{s.phase}] {s.title} ({s.duration:.2f}s) {s.detail}")
        return
    from rich.tree import Tree

    tree = Tree("[bold]可观测性 Trace[/bold]")
    for s in traj.trace:
        mark = "[green][OK][/green]" if s.ok else "[red][FAIL][/red]"
        node = tree.add(f"{mark} [bold]{s.title}[/bold] [dim]({s.phase}, {s.duration:.2f}s)[/dim]")
        node.add(s.detail or "(no detail)")
    console.print(tree)


def _print_result(console, traj: HealingTrajectory) -> None:
    healed = traj.status.value == "healed"
    diff_text = traj.diff or (traj.patches[-1].unified_diff if traj.patches else "")
    if console is None:
        print("\n--- 结果 ---")
        print(f"status: {traj.status.value} · 迭代 {traj.iterations} · 耗时 {traj.duration:.2f}s")
        v = traj.verification
        if v:
            print(f"测试: {v.tests_passed}/{v.tests_total} 通过 · 失败 {v.tests_failed}")
        if diff_text:
            print("\n最终补丁:\n" + diff_text)
        return
    from rich.panel import Panel
    from rich.syntax import Syntax

    color = "green" if healed else "red"
    title = "[SUCCESS] 自愈成功 · CI 由红变绿" if healed else f"[FAILED] {traj.status.value}"
    body = (
        f"迭代 {traj.iterations} 轮 · 耗时 {traj.duration:.2f}s\n"
        f"模式 {traj.mode}"
    )
    v = traj.verification
    if v:
        body += f"\n测试 {v.tests_passed}/{v.tests_total} 通过 · 失败 {v.tests_failed}"
    console.print(Panel.fit(body, title=f"[bold {color}]{title}[/bold {color}]", border_style=color))
    if diff_text:
        console.print(Syntax(diff_text, "diff", theme="ansi_dark", line_numbers=False))


# --------------------------------------------------------------------------- #
# Commands                                                                     #
# --------------------------------------------------------------------------- #


def cmd_demo(args: argparse.Namespace) -> int:
    Console, _, _, _ = _rich()
    console = Console() if Console else None
    repo = Path(args.repo).resolve() if getattr(args, "repo", None) else _DEFAULT_DEMO_REPO.resolve()
    skills = Path(args.skills).resolve() if getattr(args, "skills", None) else _DEFAULT_SKILLS.resolve()
    config = CodeHealConfig.load()
    _print_banner(console, config.mode.value, repo)

    # 1. Capture the real failing log from the broken demo repo.
    print(">> 采集 demo 仓库真实失败日志 (pytest) ...")
    log_text = _capture_demo_log(repo)

    # 2. Run the swarm.
    leader = SwarmLeader(config)
    traj = leader.heal(log_text, str(repo), str(skills))

    # 3. Report.
    _print_trace(console, traj)
    _print_result(console, traj)

    # 4. Persist the report.
    report = skill_tool.render_report(traj)
    out_dir = _REPO_ROOT / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_last_demo_report.md").write_text(report, encoding="utf-8")
    print(f"\n报告已写入: docs/_last_demo_report.md")

    return 0 if traj.status.value == "healed" else 1


def cmd_heal(args: argparse.Namespace) -> int:
    Console, _, _, _ = _rich()
    console = Console() if Console else None
    repo = Path(args.repo).resolve() if getattr(args, "repo", None) else Path(".").resolve()
    skills = Path(args.skills).resolve() if getattr(args, "skills", None) else _DEFAULT_SKILLS.resolve()
    log_file = getattr(args, "log", None)
    log_text = Path(log_file).read_text(encoding="utf-8") if log_file else sys.stdin.read()
    config = CodeHealConfig.load()
    _print_banner(console, config.mode.value, repo)
    leader = SwarmLeader(config)
    traj = leader.heal(log_text, str(repo), str(skills))
    _print_trace(console, traj)
    _print_result(console, traj)
    return 0 if traj.status.value == "healed" else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    Console, _, _, _ = _rich()
    console = Console() if Console else None
    repo = Path(args.repo).resolve() if getattr(args, "repo", None) else Path(".").resolve()
    log_file = getattr(args, "log", None)
    log_text = Path(log_file).read_text(encoding="utf-8") if log_file else sys.stdin.read()
    leader = SwarmLeader(CodeHealConfig.load())
    digest = leader.inspect(log_text, str(repo))
    import json

    print(json.dumps(digest, ensure_ascii=False, indent=2))
    return 0


def cmd_self_test(args: argparse.Namespace) -> int:
    """Run the swarm's own pytest suite (used by CI)."""
    cmd = [sys.executable, "-m", "pytest", "-v", str(_REPO_ROOT / "tests")]
    proc = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    return proc.returncode


# --------------------------------------------------------------------------- #
# Entry point                                                                  #
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codeheal",
        description="Jiuwen-CodeHeal Swarm: 仓库级 CI 故障自愈与多智能体回归验证",
    )
    p.add_argument("--version", action="version", version=f"codeheal {__version__}")
    p.add_argument("--demo", action="store_true", help="一键端到端自愈 examples/buggy_repo_demo")
    p.add_argument("--repo", default=None, help="待修复仓库路径")
    p.add_argument("--skills", default=None, help="skills 目录路径")
    p.add_argument("--log", default=None, help="CI 失败日志文件")
    p.add_argument("--inspect", action="store_true", help="仅做故障感知 + AST 诊断 (不生成补丁)")
    p.add_argument("--self-test", action="store_true", help="运行 swarm 自带测试套件")

    sub = p.add_subparsers(dest="command")

    d = sub.add_parser("demo", help="一键端到端自愈 examples/buggy_repo_demo")
    d.add_argument("--repo", default=None, help="待修复仓库路径 (默认 examples/buggy_repo_demo)")
    d.add_argument("--skills", default=None, help="skills 目录路径")
    d.set_defaults(func=cmd_demo)

    h = sub.add_parser("heal", help="自愈指定仓库 (需 --log 或 stdin 提供 CI 日志)")
    h.add_argument("--repo", required=True)
    h.add_argument("--log", default=None, help="CI 失败日志文件")
    h.add_argument("--skills", default=None)
    h.set_defaults(func=cmd_heal)

    i = sub.add_parser("inspect", help="仅做故障感知 + AST 诊断 (不生成补丁)")
    i.add_argument("--repo", default=None)
    i.add_argument("--log", default=None)
    i.set_defaults(func=cmd_inspect)

    s = sub.add_parser("self-test", help="运行 swarm 自带测试套件")
    s.set_defaults(func=cmd_self_test)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "demo", False) or args.command == "demo":
        return cmd_demo(args)
    if getattr(args, "self_test", False) or args.command == "self-test":
        return cmd_self_test(args)
    if getattr(args, "inspect", False) or args.command == "inspect":
        return cmd_inspect(args)
    if args.command == "heal":
        return cmd_heal(args)
    if getattr(args, "repo", None) and getattr(args, "log", None):
        return cmd_heal(args)

    # Default behaviour: run the demo
    return cmd_demo(args)


if __name__ == "__main__":
    raise SystemExit(main())
