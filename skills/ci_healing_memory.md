# CI Healing Memory

Auto-evolved skill log for Jiuwen-CodeHeal Swarm. Each entry captures a distilled ``fingerprint -> root cause -> strategy`` rule discovered while healing real CI failures.


## [2026-10-15 13:27:36] index_error @ `tests/test_buggy.py` — ❌ FAILED_TO_HEAL

- **Fingerprint**: `91fb279fe36a86e8`
- **Root cause**: index_error in `tests/test_buggy.py` function `test_find_max` — list index out of range
- **Strategy**: `unknown`
- **Fix template**:

```python

```
- **Occurrences**: 1 (success 0)
- **Run**: run-20261015-132736 · 4.35s · mode=replay

## [2026-10-15 18:15:10] index_error @ `tests/test_buggy.py` — ❌ FAILED_TO_HEAL

- **Fingerprint**: `91fb279fe36a86e8`
- **Root cause**: index_error in `tests/test_buggy.py` function `test_find_max` — list index out of range
- **Strategy**: `unknown`
- **Fix template**:

```python

```
- **Occurrences**: 2 (success 0)
- **Run**: run-20261015-181510 · 3.21s · mode=replay

## [2026-10-15 18:15:41] index_error @ `tests/test_buggy.py` — ❌ FAILED_TO_HEAL

- **Fingerprint**: `91fb279fe36a86e8`
- **Root cause**: index_error in `tests/test_buggy.py` function `test_find_max` — list index out of range
- **Strategy**: `unknown`
- **Fix template**:

```python

```
- **Occurrences**: 2 (success 0)
- **Run**: run-20261015-181541 · 3.04s · mode=replay

## [2026-10-15 18:16:37] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `4747dcb7db75d17f`
- **Root cause**: index_error in `buggy_repo_demo/calc.py` function `find_max` — list index out of range
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
- **Run**: run-20261015-181637 · 4.03s · mode=replay

## [2026-10-15 18:19:32] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `4747dcb7db75d17f`
- **Root cause**: index_error in `buggy_repo_demo/calc.py` function `find_max` — list index out of range
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
- **Run**: run-20261015-181932 · 4.63s · mode=replay

## [2026-10-15 18:24:26] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `4747dcb7db75d17f`
- **Root cause**: index_error in `buggy_repo_demo/calc.py` function `find_max` — list index out of range
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
- **Run**: run-20261015-182426 · 4.13s · mode=replay

## [2026-10-15 22:47:43] index_error @ `buggy_repo_demo/calc.py` — ✅ HEALED

- **Fingerprint**: `4747dcb7db75d17f`
- **Root cause**: index_error in `buggy_repo_demo/calc.py` function `find_max` — list index out of range
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
- **Run**: run-20261015-224743 · 5.07s · mode=replay
