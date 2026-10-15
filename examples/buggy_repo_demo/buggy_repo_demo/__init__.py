"""buggy_repo_demo - 内置 2 个故意写错的算法/边界 Bug 的小型示例项目。

这些函数在 CI 中会导致 pytest 失败，是 Jiuwen-CodeHeal Swarm 的待修复目标：
* :func:`find_max`  - Bug 1 (IndexError / off-by-one): 循环末轮越界。
* :func:`average`   - Bug 2 (ValueError / 空输入): 空列表触发 ZeroDivisionError。
"""

from __future__ import annotations

from buggy_repo_demo.calc import average, find_max

__all__ = ["average", "find_max"]
