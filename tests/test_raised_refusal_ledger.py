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


def _bare_value_errors() -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in sorted((_ROOT / "src/anvilate").rglob("*.py")):
        for node in ast.walk(parsed_source(path)):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if isinstance(raised, ast.Name) and raised.id == "ValueError":
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
    assert sum(found.values()) > 1_000
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
