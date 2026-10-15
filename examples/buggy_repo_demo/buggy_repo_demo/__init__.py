"""buggy_repo_demo - 内置 2 个故意写错的算法/边界 Bug 的小型示例项目。

这些函数在 CI 中会导致 pytest 失败，是 Jiuwen-CodeHeal Swarm 的待修复目标：

* :func:`find_max`  - Bug 1 (IndexError / off-by-one): 循环上界写成 ``len(seq)``
  而不是 ``len(seq) - 1``，对非空列表会越界访问 ``seq[len(seq)]``。
* :func:`average`   - Bug 2 (ValueError / 空输入): 对空列表直接做 ``sum/len``，
  触发 ``ZeroDivisionError``。

对应的失败用例见 ``tests/test_buggy.py``。
"""

from __future__ import annotations

from typing import List, Sequence


def find_max(seq: Sequence[int]) -> int:
    """返回序列中的最大值。

    BUG: ``range(len(seq))`` 配合 ``seq[i]`` 在 ``i == len(seq)`` 时越界。
    正确写法应使用 ``range(len(seq) - 1)``，或改用内置 ``max(seq)``。
    """
    best = seq[0]
    # BUG 1: 上界应为 len(seq) - 1；这里多迭代一次导致 IndexError。
    for i in range(len(seq)):
        if seq[i] > best:
            best = seq[i]
    return best


def average(values: List[float]) -> float:
    """返回数值列表的平均值。

    BUG: 未对空列表做守卫，``sum([]) / len([])`` 抛出 ZeroDivisionError
    (ValueError 家族)。正确写法应先判空并返回默认值 0.0。
    """
    # BUG 2: 缺少空输入守卫。
    return sum(values) / len(values)
