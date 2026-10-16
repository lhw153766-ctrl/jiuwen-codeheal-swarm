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

## [2026-10-16 15:45:52] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-154552 · 5.04s · mode=replay

## [2026-10-16 15:45:52] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-154552 · 5.04s · mode=replay

## [2026-10-16 15:46:51] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-154651 · 1.27s · mode=replay

## [2026-10-16 15:46:51] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-154651 · 1.27s · mode=replay

## [2026-10-16 15:47:44] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-154744 · 1.16s · mode=replay

## [2026-10-16 15:47:44] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-154744 · 1.16s · mode=replay

## [2026-10-16 15:48:16] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-154816 · 1.25s · mode=replay

## [2026-10-16 15:48:16] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Run**: run-20261016-154816 · 1.25s · mode=replay

## [2026-10-16 15:49:30] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 9 (success 9)
- **Run**: run-20261016-154930 · 1.19s · mode=replay

## [2026-10-16 15:49:30] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 9 (success 9)
- **Run**: run-20261016-154930 · 1.19s · mode=replay

## [2026-10-16 15:50:57] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 10 (success 10)
- **Run**: run-20261016-155057 · 1.20s · mode=replay

## [2026-10-16 15:50:57] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 10 (success 10)
- **Run**: run-20261016-155057 · 1.20s · mode=replay

## [2026-10-16 15:51:26] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 11 (success 11)
- **Run**: run-20261016-155126 · 1.19s · mode=replay

## [2026-10-16 15:51:26] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 11 (success 11)
- **Run**: run-20261016-155126 · 1.19s · mode=replay

## [2026-10-16 15:53:22] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 12 (success 12)
- **Run**: run-20261016-155322 · 5.19s · mode=replay

## [2026-10-16 15:53:22] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 12 (success 12)
- **Run**: run-20261016-155322 · 5.19s · mode=replay

## [2026-10-16 15:53:48] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 13 (success 13)
- **Run**: run-20261016-155348 · 5.00s · mode=replay

## [2026-10-16 15:53:48] value_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

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
- **Occurrences**: 13 (success 13)
- **Run**: run-20261016-155348 · 5.00s · mode=replay
