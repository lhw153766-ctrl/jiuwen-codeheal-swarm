---
name: ci-fault-healing
description: 基于 openJiuwen 与 JiuwenSwarm 多智能体协同的仓库级 CI 故障自愈、AST 根因分析与沙箱回归验证 Skill。
version: 0.1.0
tags:
  - openjiuwen
  - jiuwenswarm
  - ci-healing
  - code-repair
  - regression-testing
  - self-evolution
inputs:
  log_text:
    type: string
    description: CI 管道报错文本、pytest 失败摘要或编译器错误日志
    required: false
  repo_root:
    type: string
    description: 待自愈目标仓库根目录路径
    required: true
  skills_dir:
    type: string
    description: 自愈经验库沉淀与知识检索路径
    required: false
outputs:
  status:
    type: string
    description: 终态状态 (healed | failed_to_heal | skipped)
  diff:
    type: string
    description: 验证通过的标准 Unified Diff 修复补丁
  learned_pattern:
    type: object
    description: 提炼的错误指纹与修复策略自演进模式
---

# CI Fault Self-Healing Skill (Jiuwen-CodeHeal Swarm)

## 1. 概述与定位
本 Skill 是 **Jiuwen-CodeHeal Swarm** 系统的核心能力定义，专为 GitHub / AtomGit 开源项目及企业 CI/CD 自动化自愈设计。
Skill 遵循 JiuwenSwarm 标准组件契约，编排 **Leader-Teammate** 多角色协作与 **Swarmflow 四阶段确定性流水线**：
1. **Log Triage Teammate**：故障感知与结构化日志解析，提炼跨环境错误指纹（Error Fingerprint）。
2. **Code Inspector Teammate**：基于 Python AST 的精准代码切片与上下文压缩，检索失败用例与调用链。
3. **Patch & Sandbox Verifier Teammate**：严格安全白名单沙箱隔离，应用补丁并运行真实 `pytest` 回归验证。
4. **Skill Evolve & Reporter Teammate**：自进化模式蒸馏，将成功经验写入 `learned_patterns.json` 与 `ci_healing_memory.md`。

## 2. 工具链契约 (Tool Components)
- `codeheal.log_parser`: 解析 pytest / flake8 / mypy 报错日志，生成 `FaultSignature`。
- `codeheal.ast_inspector`: 提取报错行所在的函数/类 AST 节点，生成 `ASTContext` 与 `PatchProposal`。
- `codeheal.sandbox_verifier`: 拦截越权路径访问，在临时工作区应用补丁并真实运行 `pytest`。
- `codeheal.skill_evolver`: 将成功自愈的经验沉淀为知识模板，实现越用越聪明的进化闭环。

## 3. 触发与执行方式
### 终端执行 (CLI)
```bash
# 一键端到端自愈内置 Demo
codeheal demo

# 自愈指定仓库与 CI 日志
codeheal heal --repo /path/to/repo --log /path/to/ci.log

# 仅执行故障感知与 AST 诊断
codeheal inspect --repo /path/to/repo --log /path/to/ci.log
```

### Python SDK / openJiuwen Workflow 编排
```python
from jiuwen_codeheal.config import CodeHealConfig
from jiuwen_codeheal.swarm_leader import SwarmLeader

config = CodeHealConfig.load()
leader = SwarmLeader(config)
trajectory = leader.heal(log_text=raw_ci_log, repo_root="./my_repo", skills_dir="./skills")
print(f"Status: {trajectory.status}, Diff:\n{trajectory.diff}")
```

## 4. 经验自演进规则
当任意 CI 故障被成功修复并通过沙箱 100% 回归测试后：
1. 系统根据 `(fault_type, file_path, function_name, exception_type)` 生成唯一 16 位 Hash 指纹。
2. 检索 `learned_patterns.json`，若存在相同指纹则更新成功计数与策略置信度；若为新型故障则追加新经验模板。
3. 追加格式化复盘日志到 `ci_healing_memory.md`，供后续 LLM 或 Replay 规则优先命中复用。
