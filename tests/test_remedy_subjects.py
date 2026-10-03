"""Every remedy subject outside the analysis package names something a caller can find.

interaction-quality 7.3: a refusal carries a remedy with a *resolvable* subject. The analysis
package holds the strict form of this (tests/test_refusal_remedies_analysis.py: a public
parameter or field of the module). The rest of the library refuses documents, command lines
and files as well as function arguments, so a subject there resolves when it names one of:

- a public parameter, method parameter or model field of its module;
- a command-line flag (``--fit``) or a Design Spec document path (``element_params.x``);
- nothing a caller supplies, because the guard is marked unreachable (``pragma: no cover``)
  and its subject names the artifact to rebuild or report instead.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from conftest import parsed_source

_ROOT = Path(__file__).parents[1] / "src/anvilate"
_WORD = re.compile(r"[A-Za-z_]\w*")


def _public_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()

    def arguments(function: ast.FunctionDef) -> set[str]:
        a = function.args
        found = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
        found |= {x.arg for x in (a.vararg, a.kwarg) if x is not None}
        return found - {"self", "cls"}

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            names |= arguments(node)
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for member in node.body:
                if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                    names.add(member.target.id)
                if isinstance(member, ast.FunctionDef) and (
                    not member.name.startswith("_") or member.name == "__init__"
                ):
                    names |= arguments(member)
    return names


def _unreachable(raise_node: ast.Raise, guard: ast.AST | None, lines: list[str]) -> bool:
    marked = [raise_node.lineno] + ([guard.lineno] if guard is not None else [])
    return any("pragma: no cover" in lines[n - 1] for n in marked)


def _unresolvable_subjects() -> tuple[int, list[str]]:
    checked, unresolved = 0, []
    for path in sorted(_ROOT.rglob("*.py")):
        if "analysis" in path.relative_to(_ROOT).parts:
            continue
        tree = parsed_source(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        public = _public_names(tree)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.keyword)
                and node.arg == "subject"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            call = parents[node]
            # `ToolDefinition.subject` is the MCP tool's acted-on argument, not a remedy.
            if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "ToolDefinition":
                continue
            checked += 1
            subject = node.value.value
            if set(_WORD.findall(subject)) & public:
                continue
            if "--" in subject or "element_params." in subject:
                continue
            raise_node, guard = node, None
            while raise_node in parents and not isinstance(raise_node, ast.Raise):
                raise_node = parents[raise_node]
            if isinstance(raise_node, ast.Raise):
                guard = parents.get(raise_node)
                if isinstance(guard, ast.ExceptHandler | ast.If) and _unreachable(
                    raise_node, guard, lines
                ):
                    continue
            unresolved.append(f"{path.relative_to(_ROOT)}:{node.value.lineno}: {subject!r}")
    return checked, unresolved


def test_every_remedy_subject_outside_analysis_resolves() -> None:
    checked, unresolved = _unresolvable_subjects()
    assert checked > 500, f"only {checked} literal subjects found outside analysis/"
    assert not unresolved, "\n".join(unresolved)
