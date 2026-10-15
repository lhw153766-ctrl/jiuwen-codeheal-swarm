# CI Healing Memory

Auto-evolved skill log for Jiuwen-CodeHeal Swarm. Each entry captures a distilled ``fingerprint -> root cause -> strategy`` rule discovered while healing real CI failures.


## [2026-10-15 23:02:19] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `4747dcb7db75d17f`
- **Root cause**: index_error in `buggy_repo_demo/calc.py` function `find_max` — list index out of range
- **Strategy**: `boundary_guard`
- **Fix template**:

```python
def find_max(seq: Sequence[int]) -> int:
    """返回序列中的最大值。

    BUG: 循环访问 ``seq[i]`` 而 ``i`` 取遍 ``range(len(seq))``，当
    ``i == len(seq) - 1`` 时 ``seq[i]`` 越界，触发 ``IndexError``。
    正确写法应访问 ``seq[i]``，或用内置 ``max(seq)``。
    """
    best = seq[0]
    for i in range(len(seq)):  # BUG 1: seq[i] 在末轮越界
        if seq[i] > best:
            best = seq[i]
    return best
```
- **Occurrences**: 1 (success 1)
- **Run**: run-20261015-230219 · 4.65s · mode=replay

## [2026-10-15 23:02:19] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `fc077a19126271d9`
- **Root cause**: value_error in `buggy_repo_demo/calc.py` function `average` — division by zero
- **Strategy**: `boundary_guard`
- **Fix template**:

```python
def average(values: List[float]) -> float:
    """返回数值列表的平均值。

    BUG: 空列表未守卫，触发 ZeroDivisionError。
    """
    if not values:
        return 0.0
    return sum(values) / len(values)
```
- **Occurrences**: 1 (success 1)
- **Run**: run-20261015-230219 · 4.65s · mode=replay

## [2026-10-15 23:02:36] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `4747dcb7db75d17f`
- **Root cause**: index_error in `buggy_repo_demo/calc.py` function `find_max` — list index out of range
- **Strategy**: `boundary_guard`
- **Fix template**:

```python
def find_max(seq: Sequence[int]) -> int:
    """返回序列中的最大值。

    BUG: 循环访问 ``seq[i]`` 而 ``i`` 取遍 ``range(len(seq))``，当
    ``i == len(seq) - 1`` 时 ``seq[i]`` 越界，触发 ``IndexError``。
    正确写法应访问 ``seq[i]``，或用内置 ``max(seq)``。
    """
    best = seq[0]
    for i in range(len(seq)):  # BUG 1: seq[i] 在末轮越界
        if seq[i] > best:
            best = seq[i]
    return best
```
- **Occurrences**: 2 (success 2)
- **Run**: run-20261015-230236 · 4.84s · mode=replay

## [2026-10-15 23:02:36] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `fc077a19126271d9`
- **Root cause**: value_error in `buggy_repo_demo/calc.py` function `average` — division by zero
- **Strategy**: `boundary_guard`
- **Fix template**:

```python
def average(values: List[float]) -> float:
    """返回数值列表的平均值。

    BUG: 空列表未守卫，触发 ZeroDivisionError。
    """
    if not values:
        return 0.0
    return sum(values) / len(values)
```
- **Occurrences**: 2 (success 2)
- **Run**: run-20261015-230236 · 4.84s · mode=replay

## [2026-10-15 23:09:17] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `4747dcb7db75d17f`
- **Root cause**: index_error in `buggy_repo_demo/calc.py` function `find_max` — list index out of range
- **Strategy**: `boundary_guard`
- **Fix template**:

```python
def find_max(seq: Sequence[int]) -> int:
    """返回序列中的最大值。

    BUG: 循环访问 ``seq[i]`` 而 ``i`` 取遍 ``range(len(seq))``，当
    ``i == len(seq) - 1`` 时 ``seq[i]`` 越界，触发 ``IndexError``。
    正确写法应访问 ``seq[i]``，或用内置 ``max(seq)``。
    """
    best = seq[0]
    for i in range(len(seq)):  # BUG 1: seq[i] 在末轮越界
        if seq[i] > best:
            best = seq[i]
    return best
```
- **Occurrences**: 3 (success 3)
- **Run**: run-20261015-230917 · 4.80s · mode=replay

## [2026-10-15 23:09:17] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `fc077a19126271d9`
- **Root cause**: value_error in `buggy_repo_demo/calc.py` function `average` — division by zero
- **Strategy**: `boundary_guard`
- **Fix template**:

```python
def average(values: List[float]) -> float:
    """返回数值列表的平均值。

    BUG: 空列表未守卫，触发 ZeroDivisionError。
    """
    if not values:
        return 0.0
    return sum(values) / len(values)
```
- **Occurrences**: 3 (success 3)
- **Run**: run-20261015-230917 · 4.80s · mode=replay

## [2026-10-15 23:10:33] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `4747dcb7db75d17f`
- **Root cause**: index_error in `buggy_repo_demo/calc.py` function `find_max` — list index out of range
- **Strategy**: `boundary_guard`
- **Fix template**:

```python
def find_max(seq: Sequence[int]) -> int:
    """返回序列中的最大值。

    BUG: 循环访问 ``seq[i]`` 而 ``i`` 取遍 ``range(len(seq))``，当
    ``i == len(seq) - 1`` 时 ``seq[i]`` 越界，触发 ``IndexError``。
    正确写法应访问 ``seq[i]``，或用内置 ``max(seq)``。
    """
    best = seq[0]
    for i in range(len(seq)):  # BUG 1: seq[i] 在末轮越界
        if seq[i] > best:
            best = seq[i]
    return best
```
- **Occurrences**: 4 (success 4)
- **Run**: run-20261015-231033 · 4.77s · mode=replay

## [2026-10-15 23:10:33] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `fc077a19126271d9`
- **Root cause**: value_error in `buggy_repo_demo/calc.py` function `average` — division by zero
- **Strategy**: `boundary_guard`
- **Fix template**:

```python
def average(values: List[float]) -> float:
    """返回数值列表的平均值。

    BUG: 空列表未守卫，触发 ZeroDivisionError。
    """
    if not values:
        return 0.0
    return sum(values) / len(values)
```
- **Occurrences**: 4 (success 4)
- **Run**: run-20261015-231033 · 4.77s · mode=replay
