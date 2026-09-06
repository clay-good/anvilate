"""What a downstream consumer's type checker sees of this library's public surface.

Nothing inside a package notices a field it declared itself as `Any` — the annotation is
right there, and every use inside the package is compatible with anything. It shows up on
the far side of an install, in a consumer that imports the wheel and runs a type checker,
which is why this file exists rather than a mypy run over `src/`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_CONSUMER = Path(__file__).resolve().parent / "typing" / "provenance_consumer.py"


def test_a_provenance_field_is_a_string_to_a_consumer_that_type_checks():
    """`cited` returns `Any`, so every field declared with it was `Any` to a consumer.

    Seventy-four fields through `Provenance` and `Named`, nine more written inline, in a
    library whose stated purpose is carrying provenance — and `takes_an_int(record.ref)`
    type-checked clean while `record.sources` beside it was correctly `tuple[str, ...]`.

    The consumer file asserts both directions. Its five `return` statements are declared
    `-> str`, so a field that is `Any` again fails `--strict` with `no-any-return`; and its
    last line carries `# type: ignore[arg-type]` over a citation passed where an `int` is
    wanted, which `--strict` reports as an *unused* ignore the moment that stops being an
    error. A gate that only checked the first half would pass on a field typed `object`.
    """
    pytest.importorskip("mypy", reason="mypy is a dev dependency")
    finished = subprocess.run(  # noqa: S603 - the interpreter running this suite
        [sys.executable, "-m", "mypy", "--strict", str(_CONSUMER)],
        capture_output=True,
        text=True,
        cwd=_REPO,
        check=False,
    )
    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_every_cited_field_is_declared_through_an_alias_a_type_checker_can_read():
    """The structural half, which cannot skip when mypy is not installed.

    A *call expression* in an annotation — `identifier: cited("...")` — is not something a
    type checker can read, so it is `Any` whatever `cited` is annotated to return. Nine
    fields were written that way. Each has a module-private alias now, under the same
    `if TYPE_CHECKING` branch `Provenance` and `Named` use, and this is what stops a tenth.
    """
    inline = []
    for path in sorted((_REPO / "src" / "anvilate").rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # A field annotation, not the aliases' own assignment below `else:`.
            if re.match(r"^\s+\w+:\s*cited\(", line):
                inline.append(f"{path.relative_to(_REPO)}:{number}: {line.strip()}")
    assert not inline, (
        "these declare a field by calling `cited(...)` in the annotation, which a type "
        "checker reads as `Any`:\n  " + "\n  ".join(inline) + "\nGive each a module-private "
        "alias under an `if TYPE_CHECKING:` branch, as anvilate._models.Provenance does."
    )


def test_the_typed_consumer_actually_reaches_every_shape_of_cited_field():
    """The floor. A consumer that imported nothing would pass the mypy gate above.

    Three shapes have to be in it: a `Named` field, a `Provenance` field, and a field whose
    annotation was written as an inline `cited(...)` call — they fail differently, and the
    inline one is the shape a `TYPE_CHECKING` branch on the two aliases does not reach.
    """
    source = _CONSUMER.read_text(encoding="utf-8")
    for marker in ("`Named`", "`Provenance`", "`cited(...)` written in the annotation"):
        assert marker in source, f"the consumer no longer exercises {marker}"
    assert source.count("def ") >= 6, "the consumer has been trimmed below what it checks"
    assert "type: ignore[arg-type]" in source, (
        "the consumer no longer asserts that a citation is refused where an int is wanted, "
        "which is the half that fails on a field typed `object` rather than `str`"
    )
