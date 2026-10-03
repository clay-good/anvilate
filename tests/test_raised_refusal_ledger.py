"""The ledger of raised refusals that still carry their remedy in prose only.

interaction-quality 2.1 asks for a structured remedy on every refusal. A module migrates by
raising a ``RefusalError`` subclass (which also stays a ``ValueError``) instead of a bare
``ValueError``. This ledger counts the bare ones that remain, per file, so the migration has a
meter: a new bare refusal fails, and so does a migration that forgets to lower its line.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from conftest import parsed_source

_ROOT = Path(__file__).parents[1]
_LEDGER = _ROOT / "docs/api/raised-refusals-without-remedies.txt"


def _is_value_error(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Name) and node.id == "ValueError"


def _bare_value_errors() -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in sorted((_ROOT / "src/anvilate").rglob("*.py")):
        # A refusal can be built in one place and raised in another (`raise self._x(...)`
        # where `_x` returns the error), so every construction counts, not only the ones
        # written directly after `raise`; a bare `raise ValueError` counts too.
        for node in ast.walk(parsed_source(path)):
            built = isinstance(node, ast.Call) and _is_value_error(node.func)
            bare = isinstance(node, ast.Raise) and _is_value_error(node.exc)
            if built or bare:
                counts[path.relative_to(_ROOT).as_posix()] += 1
    return counts


def _ledger() -> Counter[str]:
    counts: Counter[str] = Counter()
    for line in _LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        path, count = line.rsplit(" ", 1)
        assert path not in counts, f"{path} is listed twice"
        counts[path] = int(count)
    return counts


def test_the_ledger_matches_the_bare_refusals_in_the_source() -> None:
    found = _bare_value_errors()
    # The floor goes first: a census that matched nothing would agree with an empty ledger.
    # refusal.py's two refusals guard the construction of a remedy and can never carry one,
    # so a census that stops seeing them has stopped seeing anything.
    assert found["src/anvilate/refusal.py"] == 2
    recorded = _ledger()
    grew = {p: (recorded[p], n) for p, n in found.items() if n > recorded[p]}
    assert not grew, (
        "new bare `raise ValueError` sites (ledger, found); raise a RefusalError subclass with "
        f"a Remedy instead: {grew}"
    )
    shrank = {p: (n, found[p]) for p, n in recorded.items() if found[p] < n}
    assert not shrank, (
        "migrated sites still counted in docs/api/raised-refusals-without-remedies.txt "
        f"(ledger, found); lower or delete these lines: {shrank}"
    )
