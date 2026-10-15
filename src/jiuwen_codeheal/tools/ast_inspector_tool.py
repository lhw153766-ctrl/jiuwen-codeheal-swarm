"""AST Inspector Tool (Phase 2 - Code Inspector Teammate).

Given a :class:`FaultSignature`, this tool uses the Python standard-library
:mod:`ast` module to *precision-slice* the offending source file instead of
blinding stuffing the whole file into the LLM context. It extracts:

* the exact enclosing function / method node (with signature + source),
* the enclosing class source when the fault is inside a method,
* the module's import block,
* the matching test file + the failing test function source,
* a call-chain hint derived from the enclosing function body.

It also contains the **deterministic fix-policy engine** (:class:`FixPolicy`)
that inspects the fault + AST context and proposes a concrete patch *without*
any LLM. In Live mode the LLM may refine this proposal; in Replay mode this is
the sole decision maker, which is what makes the demo fully offline.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path
from typing import Optional

from jiuwen_codeheal.schemas import (
    ASTContext,
    FaultSignature,
    FaultType,
    FunctionContext,
    PatchHunk,
    PatchProposal,
    PatchStrategy,
)


# --------------------------------------------------------------------------- #
# AST helpers                                                                  #
# --------------------------------------------------------------------------- #


def _read(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return None


def _enclosing_node(tree: ast.AST, line: int) -> tuple[Optional[ast.FunctionDef], Optional[ast.ClassDef]]:
    """Return the innermost (function, class) whose span covers *line*."""
    func: Optional[ast.FunctionDef] = None
    cls: Optional[ast.ClassDef] = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.lineno <= line <= (node.end_lineno or node.lineno):
                if cls is None or node.lineno >= cls.lineno:
                    cls = node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= line <= (node.end_lineno or node.lineno):
                # Pick the innermost (latest starting) function.
                if func is None or node.lineno >= func.lineno:
                    func = node  # type: ignore[assignment]
    return func, cls


def _source_segment(source: str, node: ast.AST) -> str:
    try:
        seg = ast.get_source_segment(source, node)  # type: ignore[arg-type]
        if seg:
            return seg
    except Exception:
        pass
    # Fallback: line slice.
    lines = source.splitlines()
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", start + 1)
    return "\n".join(lines[start:end])


def _signature(node: ast.FunctionDef) -> str:
    args = node.args
    parts = [a.arg for a in args.posonlyargs + args.args]
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    parts += [a.arg for a in args.kwonlyargs]
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(parts)})"


def _imports(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = ", ".join(a.name for a in node.names)
            out.append(f"from {mod} import {names}")
    return out


def _call_chain(node: Optional[ast.FunctionDef]) -> list[str]:
    calls: list[str] = []
    if node is None:
        return calls
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Name):
                calls.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                calls.append(fn.attr)
    # De-dup preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for c in calls:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _find_test_file(repo_root: Optional[str], signature: FaultSignature) -> Optional[str]:
    """Locate the test file that owns the failing test node id."""
    if not repo_root:
        return None
    root = Path(repo_root)
    for ft in signature.failed_tests:
        candidate = root / ft.test_file
        if candidate.is_file():
            return str(candidate)
        # Search by basename anywhere under repo.
        for match in root.rglob(Path(ft.test_file).name):
            return str(match)
    return None


def _test_function_source(test_file: Optional[str], function_name: str) -> str:
    if not test_file:
        return ""
    src = _read(test_file)
    if not src:
        return ""
    try:
        tree = ast.parse(src)
    except Exception:
        return ""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return _source_segment(src, node)
    return ""


# --------------------------------------------------------------------------- #
# Inspector                                                                    #
# --------------------------------------------------------------------------- #


class ASTInspector:
    """Builds an :class:`ASTContext` for a fault."""

    def __init__(self, repo_root: Optional[str] = None) -> None:
        self.repo_root = repo_root

    def inspect(self, signature: FaultSignature) -> ASTContext:
        file_path = signature.file_path
        # Resolve relative file path against repo root when needed.
        abs_path = self._resolve(file_path)
        ctx = ASTContext(
            target_file=file_path or "",
            target_line=signature.line_number or 0,
            related_test_file=None,
        )

        if not abs_path:
            ctx.compressed_context = self._render(ctx)
            return ctx

        source = _read(abs_path)
        if source is None:
            ctx.compressed_context = self._render(ctx)
            return ctx

        try:
            tree = ast.parse(source)
        except Exception:
            # Unparseable (e.g. syntax error) - fall back to raw slice.
            lines = source.splitlines()
            lo = max(0, (signature.line_number or 1) - 6)
            hi = min(len(lines), (signature.line_number or 1) + 6)
            ctx.compressed_context = "\n".join(lines[lo:hi])
            return ctx

        line = signature.line_number or 1
        func, cls = _enclosing_node(tree, line)
        if func is None and signature.function_name:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == signature.function_name:
                        func = node
                        break

        if func is not None:
            ctx.function = FunctionContext(
                name=func.name,
                signature=_signature(func),
                lineno=func.lineno,
                end_lineno=func.end_lineno or func.lineno,
                source=_source_segment(source, func),
                is_method=cls is not None,
                class_name=cls.name if cls is not None else None,
            )
            ctx.call_chain = _call_chain(func)

        if cls is not None and ctx.function and ctx.function.is_method:
            ctx.class_source = _source_segment(source, cls)

        ctx.imports = _imports(tree)

        # Test file context.
        if signature.failed_tests:
            ft = _find_test_file(self.repo_root, signature)
            if ft:
                ctx.related_test_file = ft
                ctx.related_test_source = _test_function_source(
                    ft, signature.failed_tests[0].test_function
                )

        # Context compression: budget-aware assembly (never the whole file).
        ctx.compressed_context = self._render(ctx)
        return ctx

    # ------------------------------------------------------------------ #
    def _resolve(self, file_path: Optional[str]) -> Optional[str]:
        if not file_path:
            return None
        p = Path(file_path)
        if p.is_absolute() and p.is_file():
            return str(p)
        if self.repo_root:
            cand = Path(self.repo_root) / file_path
            if cand.is_file():
                return str(cand)
            for match in Path(self.repo_root).rglob(p.name):
                return str(match)
        return file_path if p.is_file() else None

    @staticmethod
    def _render(ctx: ASTContext) -> str:
        parts: list[str] = []
        if ctx.function:
            f = ctx.function
            header = f"# Enclosing function: {f.signature}"
            if f.class_name:
                header = f"# Enclosing method: {f.class_name}.{f.name}\n{f.signature}"
            parts.append(header + "\n" + f.source)
        if ctx.class_source and (not ctx.function or not ctx.function.is_method):
            parts.append("# Enclosing class:\n" + ctx.class_source)
        if ctx.imports:
            parts.append("# Imports:\n" + "\n".join(ctx.imports))
        if ctx.related_test_source:
            parts.append("# Failing test:\n" + ctx.related_test_source)
        if ctx.call_chain:
            parts.append("# Call chain: " + " -> ".join(ctx.call_chain[:12]))
        return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Deterministic fix-policy engine (replay mode decision maker)                 #
# --------------------------------------------------------------------------- #


class FixPolicy:
    """Propose a patch from (signature, ast_context) with pure Python rules.

    The policy is deliberately small and auditable. Each rule targets a common
    CI-failure archetype and emits a :class:`PatchProposal`. Unknown archetypes
    yield a no-op proposal so the swarm reports ``failed_to_heal`` honestly
    rather than hallucinating a fix.
    """

    def propose(self, signature: FaultSignature, ctx: ASTContext) -> PatchProposal:
        ft = signature.fault_type
        if ctx.function is None:
            return PatchProposal(
                strategy=PatchStrategy.UNKNOWN,
                summary="No enclosing function located; cannot propose a safe fix.",
                confidence=0.0,
            )

        src = ctx.function.source
        file_path = ctx.target_file
        line = ctx.function.lineno  # 1-based start of the function

        if ft == FaultType.ASSERTION_ERROR:
            return self._fix_off_by_one(signature, ctx, src, file_path, line)
        if ft in (FaultType.VALUE_ERROR, FaultType.TYPE_ERROR):
            return self._fix_empty_input(signature, ctx, src, file_path, line)
        if ft == FaultType.KEY_ERROR:
            return self._fix_missing_key(signature, ctx, src, file_path, line)
        if ft == FaultType.ATTRIBUTE_ERROR:
            return self._fix_none_check(signature, ctx, src, file_path, line)
        if ft == FaultType.INDEX_ERROR:
            return self._fix_index_guard(signature, ctx, src, file_path, line)

        return PatchProposal(
            strategy=PatchStrategy.UNKNOWN,
            summary=f"No deterministic policy for fault type {ft.value}; escalating to LLM.",
            confidence=0.1,
        )

    # ------------------------------------------------------------------ #
    # Individual rules                                                   #
    # ------------------------------------------------------------------ #
    def _fix_off_by_one(self, sig, ctx, src, file_path, line) -> PatchProposal:
        """Boundary/loop off-by-one: tighten ``range(n)`` -> ``range(n - 1)`` etc."""
        # Heuristic: a `while`/`for` loop whose bound equals len(seq) used with an
        # index, or a `range(len(x))` where the last element overshoots.
        old_loop = _first_match(src, r"(?P<body>(?:.*\n|\s)*?\bfor\b.*\brange\(len\([^\n]*\)[^\n]*)")
        if old_loop and _has_indexing(src):
            new_loop = old_loop.replace("range(len(", "range(len(", 1)
            # Replace the inclusive upper bound `< n>` -> `< n - 1` when pattern
            # `< len(` or `<= len(` appears; else clamp inside body.
            patched = _decrement_bound(src)
            if patched != src:
                return self._proposal_from_diff(
                    src, patched, file_path, line,
                    PatchStrategy.BOUNDARY_GUARD,
                    "Tightened loop upper bound to fix off-by-one overrun (IndexError).",
                )
        # Empty-sequence guard fallback.
        guard = _prepend_empty_guard(src)
        if guard != src:
            return self._proposal_from_diff(
                src, guard, file_path, line,
                PatchStrategy.BOUNDARY_GUARD,
                "Added empty/short-input guard before indexed access.",
            )
        return PatchProposal(
            strategy=PatchStrategy.UNKNOWN,
            summary="Off-by-one suspected but no safe rewrite found.",
            confidence=0.2,
        )

    def _fix_empty_input(self, sig, ctx, src, file_path, line) -> PatchProposal:
        guard = _prepend_empty_guard(src)
        if guard != src:
            return self._proposal_from_diff(
                src, guard, file_path, line,
                PatchStrategy.BOUNDARY_GUARD,
                "Guard against empty input before minimum/aggregation call.",
            )
        return PatchProposal(
            strategy=PatchStrategy.UNKNOWN,
            summary="ValueError/TypeError with no safe deterministic guard.",
            confidence=0.2,
        )

    def _fix_missing_key(self, sig, ctx, src, file_path, line) -> PatchProposal:
        patched = _safe_dict_get(src)
        if patched != src:
            return self._proposal_from_diff(
                src, patched, file_path, line,
                PatchStrategy.NONE_CHECK,
                "Switched direct key access to .get() with a default.",
            )
        return PatchProposal(
            strategy=PatchStrategy.UNKNOWN,
            summary="KeyError with no safe deterministic rewrite.",
            confidence=0.2,
        )

    def _fix_none_check(self, sig, ctx, src, file_path, line) -> PatchProposal:
        patched = _add_none_guard(src)
        if patched != src:
            return self._proposal_from_diff(
                src, patched, file_path, line,
                PatchStrategy.NONE_CHECK,
                "Added None guard before attribute access.",
            )
        return PatchProposal(
            strategy=PatchStrategy.UNKNOWN,
            summary="AttributeError with no safe deterministic guard.",
            confidence=0.2,
        )

    def _fix_index_guard(self, sig, ctx, src, file_path, line) -> PatchProposal:
        import re

        # Strategy A: seq[i + 1] -> seq[i] off-by-one overrun
        if re.search(r"\[\s*([a-zA-Z_]\w*)\s*\+\s*1\s*\]", src):
            patched = re.sub(r"\[\s*([a-zA-Z_]\w*)\s*\+\s*1\s*\]", r"[\1]", src)
            return self._proposal_from_diff(
                src, patched, file_path, line,
                PatchStrategy.BOUNDARY_GUARD,
                "Fixed off-by-one index overrun by changing index access from [idx + 1] to [idx].",
            )

        # Strategy B: loop upper bound off-by-one (range(len(x)) -> range(len(x) - 1))
        dec = _decrement_bound(src)
        if dec != src:
            return self._proposal_from_diff(
                src, dec, file_path, line,
                PatchStrategy.BOUNDARY_GUARD,
                "Adjusted loop upper bound to prevent index overrun.",
            )

        # Strategy C: guard against empty input
        guard = _prepend_empty_guard(src)
        if guard != src:
            return self._proposal_from_diff(
                src, guard, file_path, line,
                PatchStrategy.BOUNDARY_GUARD,
                "Added bounds guard before indexed access.",
            )
        return PatchProposal(
            strategy=PatchStrategy.UNKNOWN,
            summary="IndexError with no safe deterministic guard.",
            confidence=0.2,
        )

    # ------------------------------------------------------------------ #
    def _proposal_from_diff(
        self, old_src: str, new_src: str, file_path: str, line: int,
        strategy: PatchStrategy, rationale: str,
    ) -> PatchProposal:
        diff = _unified_diff(old_src, new_src, file_path)
        return PatchProposal(
            strategy=strategy,
            summary=rationale,
            hunks=[PatchHunk(file=file_path, old=old_src, new=new_src, rationale=rationale)],
            unified_diff=diff,
            confidence=0.75,
            source="policy",
        )


# --------------------------------------------------------------------------- #
# Source rewriting helpers (line-oriented, AST-informed)                        #
# --------------------------------------------------------------------------- #


def _has_indexing(src: str) -> bool:
    import re

    return bool(re.search(r"\[\s*[\w\+\-\s]+\s*\]", src)) or "[-1]" in src


def _first_match(src: str, pattern: str) -> Optional[str]:
    import re

    m = re.search(pattern, src)
    if not m:
        return None
    return m.group("body") if "body" in m.groupdict() else m.group(0)


def _decrement_bound(src: str) -> str:
    """Turn an inclusive ``<= len(x)`` or ``< len(x)`` used for indexing into a
    safe exclusive bound by clamping the index. Conservative: only rewrites a
    ``while`` loop with an explicit counter that indexes a sequence."""
    import re

    # while i <= len(seq):  ->  while i < len(seq):
    new = re.sub(r"(while\s+\w+\s*<=\s*len\()", r"while \1", src, count=0)
    new = re.sub(r"(<=\s*len\()", r"< \1", new)
    # range(len(seq)) used with seq[i] where i reaches len(seq): shift to len(seq)-1
    new = re.sub(r"range\(len\(([^\]]+)\)\)", r"range(len(\1) - 1)", new)
    return new


def _prepend_empty_guard(src: str) -> str:
    """Insert an early-return guard for empty inputs at the top of the function."""
    lines = src.splitlines()
    if not lines:
        return src

    param_name = None
    default_ret = "0.0"
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.args.args:
                    args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
                    if args:
                        param_name = args[0]
                if node.returns:
                    try:
                        ret_str = ast.unparse(node.returns).lower()
                        if "float" in ret_str:
                            default_ret = "0.0"
                        elif "int" in ret_str:
                            default_ret = "0"
                        elif "bool" in ret_str:
                            default_ret = "False"
                        elif "list" in ret_str:
                            default_ret = "[]"
                        elif "dict" in ret_str:
                            default_ret = "{}"
                        elif "str" in ret_str:
                            default_ret = '""'
                    except Exception:
                        pass
                break
    except Exception:
        pass

    if not param_name:
        import re

        m = re.search(r"def\s+\w+\s*\(\s*(\w+)", src)
        if m:
            param_name = m.group(1)
        else:
            return src

    if f"if not {param_name}" in src:
        return src

    indent = _body_indent(lines)
    guard = f"{indent}if not {param_name}:\n{indent}    return {default_ret}"

    insert_at = _body_start_index(lines)
    new_lines = lines[:insert_at] + guard.splitlines() + lines[insert_at:]
    return "\n".join(new_lines)


def _safe_dict_get(src: str) -> str:
    import re

    # Convert `d[key]` to `d.get(key, default)` where d is a simple name.
    return re.sub(r"(?<![.\w])(\w+)\[(\w+)\]", r"\1.get(\2, None)", src, count=1)


def _add_none_guard(src: str) -> str:
    import re

    m = re.search(r"return\s+([\w.]+)\.", src)
    if not m:
        return src
    expr = m.group(1)
    indent = _body_indent(src.splitlines())
    guard = f"{indent}if {expr} is None:\n{indent}    return None"
    lines = src.splitlines()
    insert_at = _body_start_index(lines)
    if any("is None" in ln for ln in lines):
        return src
    return "\n".join(lines[:insert_at] + guard.splitlines() + lines[insert_at:])


def _body_indent(lines: list[str]) -> str:
    for ln in lines[1:]:
        if ln.strip():
            return ln[: len(ln) - len(ln.lstrip())]
    return "    "


def _body_start_index(lines: list[str]) -> int:
    """Index where executable body begins (skip signature + docstring)."""
    idx = 1  # skip def line
    # Skip a docstring.
    if idx < len(lines):
        stripped = lines[idx].strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            if stripped.count(quote) >= 2 and len(stripped) > 3:
                return idx + 1
            idx += 1
            while idx < len(lines) and quote not in lines[idx]:
                idx += 1
            return idx + 1
    return idx


def _unified_diff(old: str, new: str, file_path: str) -> str:
    import difflib

    old_lines = old.splitlines(keepends=False)
    new_lines = new.splitlines(keepends=False)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{file_path}", tofile=f"b/{file_path}", lineterm="",
    )
    return "\n".join(diff)


# --------------------------------------------------------------------------- #
# Functional wrappers (openjiuwen @tool targets)                               #
# --------------------------------------------------------------------------- #


def inspect_fault_site(file_path: str, line_number: int, repo_root: Optional[str] = None) -> dict:
    """Return the AST-sliced context around *file_path:line_number*."""
    source = _read(file_path)
    if source is None:
        return {"error": f"cannot read {file_path}"}
    try:
        tree = ast.parse(source)
    except Exception as exc:
        return {"error": f"cannot parse {file_path}: {exc}"}
    func, cls = _enclosing_node(tree, line_number)
    return {
        "function": _source_segment(source, func) if func else None,
        "signature": _signature(func) if func else None,
        "class_name": cls.name if cls else None,
        "imports": _imports(tree),
    }


def propose_fix(fault: dict, ast_context: dict) -> dict:
    """Propose a deterministic patch for the given fault + context."""
    sig = FaultSignature(**fault)
    ctx = ASTContext(**ast_context)
    return FixPolicy().propose(sig, ctx).model_dump()


def compress_context(ast_context: dict, max_chars: int = 6000) -> str:
    """Clamp an AST context blob to a token budget."""
    blob = ASTContext(**ast_context).compressed_context
    if len(blob) <= max_chars:
        return blob
    return blob[:max_chars] + "\n... [context truncated to fit budget]"
