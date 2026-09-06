"""A downstream consumer of this library's provenance fields, for a type checker to read.

Not collected as a test: `tests/test_typing.py` runs `mypy` over this file. It is here
rather than inline in that test because a type checker reads files, and a string written
into a temporary file at run time is a copy of this that nobody edits when the API moves.

Every field below is declared with `cited(...)` — the mechanism that refuses a blank
citation — and each was `Any` to a consumer until `_models` gained its `TYPE_CHECKING`
branch, because `cited` returns an `Annotated` alias built from a per-field sentence and a
call expression is not something a type checker can read as a type.
"""

from anvilate.evidence import SourceRecord
from anvilate.loads import CombinationEvidence
from anvilate.scorecard import ScorecardEntry
from anvilate.standards.fatigue import WeldDetailCategory


def takes_an_int(value: int) -> int:
    return value + 1


def a_named_field(entry: ScorecardEntry) -> str:
    return entry.name  # `Named`


def an_alias_field(record: SourceRecord) -> str:
    return record.ref  # `Provenance`


def an_inline_cited_field(evidence: CombinationEvidence) -> str:
    return evidence.citation  # `cited(...)` written in the annotation


def another_inline_cited_field(category: WeldDetailCategory) -> str:
    return category.standard


def a_citation_is_not_a_number(record: SourceRecord) -> int:
    # The line that has to fail. It type-checked clean while these fields were `Any`.
    return takes_an_int(record.ref)  # type: ignore[arg-type]
