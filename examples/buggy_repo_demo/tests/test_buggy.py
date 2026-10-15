"""buggy_repo_demo 的测试 - 2 个用例故意失败，对应 calc.py 的 2 个 Bug。

* ``test_find_max``  - 期望 ``find_max([1, 5, 3, 9, 2]) == 9``，但因 off-by-one 越界而失败。
* ``test_average``   - 期望 ``average([]) == 0.0``，但因空输入未守卫而失败。

其余用例为正常回归测试，验证修复补丁不会破坏既有正确行为。
"""

from __future__ import annotations

import pytest

from buggy_repo_demo.calc import average, find_max


def test_find_max() -> None:
    # 触发 Bug 1: off-by-one 越界
    assert find_max([1, 5, 3, 9, 2]) == 9


def test_find_max_single() -> None:
    assert find_max([42]) == 42


def test_find_max_negative() -> None:
    assert find_max([-7, -1, -9]) == -1


def test_average_empty() -> None:
    # 触发 Bug 2: 空输入未守卫
    assert average([]) == 0.0


def test_average_normal() -> None:
    assert average([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_average_single() -> None:
    assert average([10.0]) == 10.0
