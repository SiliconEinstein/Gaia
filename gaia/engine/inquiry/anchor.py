"""Map IR labels back to package source locations.

Gaia 的 Knowledge 只记录 ``module`` 名字，不记录行号。Inquiry 自己用
``ast`` 扫描 package 源代码，定位 ``<name> = claim(...) / derive(...) /
deduction(...)`` 等 DSL 顶层调用，将变量名 (或显式 ``label="..."`` 关键字)
映射到 (文件路径, 行号, 列号)。

只读：仅读取 .py 文件，不解析模块、不导入、不修改任何东西。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Gaia DSL 顶层构造器；这些调用的赋值目标即为该节点 label 的默认值。
_DSL_CALLABLES = {
    "abduction",
    "analogy",
    "associate",
    "case_analysis",
    "claim",
    "compare",
    "composite",
    "compose",
    "composition",
    "complement",
    "contradict",
    "contradiction",
    "context",
    "compute",
    "deduction",
    "depends_on",
    "derive",
    "disjunction",
    "equal",
    "elimination",
    "equivalence",
    "exclusive",
    "extrapolation",
    "fills",
    "induction",
    "infer",
    "mathematical_induction",
    "note",
    "noisy_and",
    "observe",
    "operator",
    "question",
    "setting",
    "support",
}


@dataclass(frozen=True)
class SourceAnchor:
    """Source location for a DSL declaration inside a package."""

    file: str  # 相对 package_root 的 POSIX 风格路径
    line: int  # 1-based
    column: int  # 0-based, 与 ast.AST.col_offset 一致

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible anchor payload."""
        return {"file": self.file, "line": self.line, "column": self.column}


def _label_from_call(node: ast.Call) -> str | None:
    """Return an explicit ``label=`` value, if the DSL call has one."""
    for kw in node.keywords:
        if (
            kw.arg == "label"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return kw.value.value
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        # 多数 DSL 把首个位置参数当作 content/label——claim() 是 content,
        # 但变量名才是 label, 因此首位置参数不直接当 label。
        return None
    return None


def _callable_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _scan_module(py_file: Path, rel_file: str) -> dict[str, SourceAnchor]:
    out: dict[str, SourceAnchor] = {}
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
    except (OSError, SyntaxError):
        return out

    for stmt in tree.body:
        # 只看顶层赋值: x = claim(...) / x: T = claim(...)
        if isinstance(stmt, ast.Assign):
            targets = stmt.targets
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets = [stmt.target]
            value = stmt.value
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            targets = []
            value = stmt.value
        else:
            continue
        if not isinstance(value, ast.Call):
            continue
        name = _callable_name(value.func)
        if name not in _DSL_CALLABLES:
            continue
        anchor = SourceAnchor(file=rel_file, line=stmt.lineno, column=stmt.col_offset)
        explicit = _label_from_call(value)
        if explicit:
            out[explicit] = anchor
        for tgt in targets:
            if isinstance(tgt, ast.Name):
                out.setdefault(tgt.id, anchor)
    return out


def find_anchors(pkg_path: str | Path) -> dict[str, SourceAnchor]:
    """Scan package Python files and return a label-to-anchor map.

    重复 label 取首次出现; 排除 .gaia/ 与隐藏目录。
    """
    root = Path(pkg_path).resolve()
    out: dict[str, SourceAnchor] = {}
    if not root.is_dir():
        return out
    for py_file in sorted(root.rglob("*.py")):
        # 跳过 .gaia/ / .venv / __pycache__ / 隐藏目录
        if any(
            part.startswith(".") or part == "__pycache__"
            for part in py_file.relative_to(root).parts
        ):
            continue
        rel = py_file.relative_to(root).as_posix()
        for label, anchor in _scan_module(py_file, rel).items():
            out.setdefault(label, anchor)
    return out
