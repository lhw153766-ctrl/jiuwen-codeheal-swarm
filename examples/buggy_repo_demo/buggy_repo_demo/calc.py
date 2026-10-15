"""故意写错的示例模块（供 swarm 自愈）。

包含 2 个 Bug:
1. ``find_max`` - off-by-one 越界 (IndexError)
2. ``average``  - 空输入未守卫 (ZeroDivisionError / ValueError 家族)
"""

from __future__ import annotations

from typing import List, Sequence


def find_max(seq: Sequence[int]) -> int:
    """返回序列中的最大值。

    BUG: 循环访问 ``seq[i + 1]`` 而 ``i`` 取遍 ``range(len(seq))``，当
    ``i == len(seq) - 1`` 时 ``seq[i + 1]`` 越界，触发 ``IndexError``。
    正确写法应访问 ``seq[i]``，或用内置 ``max(seq)``。
    """
    best = seq[0]
    for i in range(len(seq)):  # BUG 1: seq[i + 1] 在末轮越界
        if seq[i + 1] > best:
            best = seq[i + 1]
    return best


def average(values: List[float]) -> float:
    """返回数值列表的平均值。

    BUG: 空列表未守卫，触发 ZeroDivisionError。
    """
    return sum(values) / len(values)  # BUG 2: 缺少空输入守卫
