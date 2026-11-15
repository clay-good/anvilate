"""Write the census of checks whose result is a life, and whether each publishes one.

    python tools/audit/lives.py            # rewrite docs/api/life-publishing-checks.txt
    python tools/audit/lives.py --check    # exit 1 if the file is not what this writes

service-life-planning 1.2. A check whose result *is* a life has to publish it as a typed
:class:`~anvilate.scorecard.LifeQuantity`, because the maintenance plan is derived from
the number and never from the detail line's prose. Nothing stops a new wear check from
shipping without one, and the plan would then be quietly shorter rather than visibly
incomplete — the exact failure the coverage rule exists to prevent one layer out.

One line per construction site:

    module:line | check name | publishes a life | the phrase that matched

**The detector, stated so it can be argued with.** The premise is "the check's result is
a life", and no detector can read that. What this reads instead is the check's *name*
against :data:`PHRASES` — a short, reviewed list of the phrases this library actually
uses for a life, not a loose match on "life" or "fatigue". A stress check named
"rotating-shaft fatigue" computes a safety factor and not a life, and a detector wide
enough to catch it would demand a life no method here produces. So the list is narrow and
explicit, and the census is only as complete as the list: adding a life-bearing check
under a new phrase means adding the phrase here too, which is itself a reviewed diff.

"Publishes" is read from the same statement: the construction, and any ``model_copy``
chained onto it, naming ``life``. A check that sets a life somewhere else entirely would
read as not publishing, which is the safe direction to be wrong in.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "anvilate"
PAGE = REPO / "docs" / "api" / "life-publishing-checks.txt"

#: The phrases this library names a life-bearing check with. Reviewed, not inferred: see
#: the module docstring on why a wide match is the wrong detector here.
PHRASES: tuple[str, ...] = (
    "rating life",
    "duty-cycle fatigue",
    "wear allowance",
    "corrosion allowance",
    "compression set",
    "creep retention",
    "remaining life",
    "service life",
    "rupture life",
    "anode life",
)

_BUILDERS = {"ScorecardEntry", "from_safety_factor", "from_comparison"}


def _matched(name: str) -> str | None:
    lowered = name.lower()
    return next((phrase for phrase in PHRASES if phrase in lowered), None)


def _check_name(call: ast.Call) -> str | None:
    """The check's name, when this call builds an entry and names it with a literal."""
    func = call.func
    label = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if label not in _BUILDERS:
        return None
    if call.args and isinstance(call.args[0], ast.Constant):
        value = call.args[0].value
        return value if isinstance(value, str) else None
    for keyword in call.keywords:
        if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            return value if isinstance(value, str) else None
    return None


def _is_a_life_assignment(node: ast.AST) -> bool:
    """Whether this node hands a check a ``life``.

    Two spellings and no third: ``life=`` as a keyword on a builder, and ``"life"`` as a
    key of a ``model_copy(update={...})`` mapping. A bare mention of a variable called
    ``life`` does not count — the first draft read `ast.dump` for the substring and called
    the zero-damage duty-cycle branch a publisher because a local above it had that name.
    """
    if isinstance(node, ast.keyword) and node.arg == "life":
        return True
    if isinstance(node, ast.Dict):
        return any(
            isinstance(key, ast.Constant) and key.value == "life" for key in node.keys
        )
    return False


def _blocks(body: list[ast.stmt]) -> list[list[ast.stmt]]:
    """This block, then every block nested inside its statements.

    A block is a list of statements that run together: a function body, an ``if`` arm, a
    ``for`` body. It is the unit this census attributes a life to, and getting that unit
    right is the whole accuracy of the file.

    The two wrong units were both tried. Attributing a call to the enclosing *function*
    made one branch's life cover every branch: the duty-cycle screen's zero-damage return,
    which publishes nothing, read as publishing. Attributing it to the enclosing
    *statement* split the component bearing check in two — it builds the entry in one
    statement and attaches the life in the next — and called it a gap.
    """
    out = [body]
    for statement in body:
        for field in ("body", "orelse", "finalbody"):
            nested = getattr(statement, field, None)
            if isinstance(nested, list) and nested and isinstance(nested[0], ast.stmt):
                out.extend(_blocks(nested))
        for handler in getattr(statement, "handlers", []):
            out.extend(_blocks(handler.body))
        for case in getattr(statement, "cases", []):
            out.extend(_blocks(case.body))
    return out


def _own_nodes(block: list[ast.stmt]):
    """Every node of a block that is not inside one of its nested blocks.

    A pruning walk rather than ``ast.walk``: descending from an ``if`` statement reaches
    its arms, and those are their own blocks. Without the prune the zero-damage branch of
    the duty-cycle screen appeared twice, once attributed to its own arm and once to the
    function around it, with opposite answers.
    """
    nested = {id(inner) for sub in _blocks(block)[1:] for inner in sub}
    stack = [statement for statement in block if id(statement) not in nested]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if id(child) in nested:
                continue
            stack.append(child)


def census() -> list[tuple[str, int, str, bool, str]]:
    """Every life-named construction site: module, line, name, publishes, phrase."""
    found: list[tuple[str, int, str, bool, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - the suite would be broken anyway
            continue
        for block in _blocks(tree.body):
            nodes = list(_own_nodes(block))
            publishes = any(_is_a_life_assignment(node) for node in nodes)
            for node in nodes:
                if not isinstance(node, ast.Call):
                    continue
                name = _check_name(node)
                if name is None:
                    continue
                phrase = _matched(name)
                if phrase is None:
                    continue
                found.append(
                    (str(path.relative_to(REPO)), node.lineno, name, publishes, phrase)
                )
    return sorted(set(found), key=lambda row: (row[0], row[1]))


def rendered() -> str:
    rows = census()
    missing = [row for row in rows if not row[3]]
    lines = [
        "# Every check this library names as a life, and whether it publishes a typed one.",
        "# Generated by tools/audit/lives.py; do not edit.",
        "#",
        "# module:line | check name | publishes | matched phrase",
        f"# {len(rows)} sites, {len(missing)} publishing no life quantity.",
        "",
    ]
    for module, line, name, publishes, phrase in rows:
        lines.append(
            f"{module}:{line} | {name} | {'yes' if publishes else 'NO'} | {phrase}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    text = rendered()
    if "--check" in argv:
        current = PAGE.read_text(encoding="utf-8") if PAGE.exists() else ""
        if current != text:
            print(f"{PAGE.relative_to(REPO)} is not what tools/audit/lives.py writes")
            return 1
        return 0
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(text, encoding="utf-8")
    print(f"wrote {PAGE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
