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

## [2026-10-16 10:15:22] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-101522 · 4.12s · mode=replay

## [2026-10-16 10:15:22] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-101522 · 4.12s · mode=replay

## [2026-10-16 18:31:50] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-183150 · 4.66s · mode=replay

## [2026-10-16 18:31:50] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-183150 · 4.66s · mode=replay

## [2026-10-16 18:34:42] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-183442 · 1.22s · mode=replay

## [2026-10-16 18:34:42] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-183442 · 1.22s · mode=replay

## [2026-10-16 18:36:18] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 5 (success 5)
- **Run**: run-20261016-183618 · 1.09s · mode=replay

## [2026-10-16 18:36:18] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 5 (success 5)
- **Run**: run-20261016-183618 · 1.09s · mode=replay

## [2026-10-16 18:36:47] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 6 (success 6)
- **Run**: run-20261016-183647 · 1.34s · mode=replay

## [2026-10-16 18:36:47] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 6 (success 6)
- **Run**: run-20261016-183647 · 1.34s · mode=replay

## [2026-10-16 18:39:12] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 7 (success 7)
- **Run**: run-20261016-183912 · 1.10s · mode=replay

## [2026-10-16 18:39:12] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 7 (success 7)
- **Run**: run-20261016-183912 · 1.10s · mode=replay

## [2026-10-16 18:39:15] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 8 (success 8)
- **Run**: run-20261016-183915 · 4.56s · mode=replay

## [2026-10-16 18:39:15] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 8 (success 8)
- **Run**: run-20261016-183915 · 4.56s · mode=replay
