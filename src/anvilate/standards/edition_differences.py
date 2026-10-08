"""What became of a cited clause in a standard's next edition, read off the publisher.

A check written against AISC 360-16 §J3.6 computes bolt strength. In AISC 360-22, §J3.6 is
maximum spacing and edge distance, and bolt strength is §J3.7. A citation without an
edition names a different requirement depending on which book is open, and one with an
edition says nothing about whether its provision survived. This registry records, clause
by clause, what the publisher's own comparison document says changed.

**Absence is stated, never read as agreement.** :func:`compare_editions` answers a clause
with no entry by saying no difference is registered, which is a statement about this
registry and not about the standard. An entry of kind ``unchanged`` exists only where the
comparison document itself supports it.
"""

from __future__ import annotations

import re
from enum import StrEnum
from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING

from pydantic import ConfigDict

from .._models import Provenance, RevalidatedModel, _near_identifiers, cited, parse_yaml
from ..refusal import RefusalError, Remedy
from .effectivity import Citation, parse_citation

__all__ = [
    "EditionChange",
    "EditionComparison",
    "EditionDifference",
    "EditionDifferenceTable",
    "UnknownEditionDifferenceError",
    "compare_editions",
    "default_edition_differences",
]

if TYPE_CHECKING:
    _Clause = str
else:
    _Clause = cited("the clause number as the standard writes it, e.g. §J3.6")

# The clause a citation's free text starts with: "§J3.6 (bolt shear)" is §J3.6.
_CLAUSE = re.compile(r"§\s?[A-Z]\d+(?:\.\d+)*")


class EditionChange(StrEnum):
    """What the publisher says happened to the clause."""

    RENUMBERED = "renumbered"
    REVISED = "revised"
    TERMINOLOGY = "terminology"
    UNCHANGED = "unchanged"


class EditionDifference(RevalidatedModel):
    """One clause, its successor in the next edition, and what changed, with its source."""

    model_config = ConfigDict(frozen=True)

    standard: Provenance
    from_edition: str
    to_edition: str
    clause: _Clause
    successor: _Clause
    change: EditionChange
    summary: Provenance
    source: Provenance
    page: int

    @property
    def key(self) -> str:
        return f"{self.standard}-{self.from_edition} {self.clause}"

    def __str__(self) -> str:
        moved = "" if self.successor == self.clause else f" (now {self.successor})"
        return (
            f"{self.standard}-{self.from_edition} {self.clause} → {self.standard}-"
            f"{self.to_edition} {self.successor}: {self.change.value}{moved}. {self.summary} "
            f"[{self.source}, p. {self.page}]"
        )


class _EditionInputError(RefusalError, ValueError):
    """A citation an edition comparison cannot be made from."""


class UnknownEditionDifferenceError(KeyError):
    """A requested clause has no entry in the registry."""

    def __init__(self, key: str, suggestions: list[str]) -> None:
        self.key = key
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no edition difference is registered for {key!r}{hint}")


class EditionDifferenceTable:
    """The registered differences, keyed ``AISC 360-16 §J3.6``."""

    def __init__(self, entries: dict[str, EditionDifference]) -> None:
        self._entries = entries

    def designations(self) -> list[str]:
        return sorted(self._entries)

    def get(self, key: str) -> EditionDifference:
        try:
            return self._entries[key]
        except KeyError:
            raise UnknownEditionDifferenceError(
                key, _near_identifiers(key, self._entries)
            ) from None

    def find(self, citation: Citation, to_edition: str) -> EditionDifference | None:
        clause = _CLAUSE.match(citation.clause.strip())
        if clause is None:
            return None
        entry = self._entries.get(f"{citation.standard}-{citation.edition} {clause.group()}")
        return entry if entry is not None and entry.to_edition == to_edition else None


@cache
def default_edition_differences() -> EditionDifferenceTable:
    """Every bundled edition difference, read from ``data/edition_differences.yaml``."""
    text = (files("anvilate.standards") / "data" / "edition_differences.yaml").read_text(
        encoding="utf-8"
    )
    document = parse_yaml(text)
    source = document["dataset"]["source"]
    entries = {}
    for row in document["differences"]:
        entry = EditionDifference(
            standard=row["standard"],
            from_edition=row["from"],
            to_edition=row["to"],
            clause=row["clause"],
            successor=row["successor"],
            change=EditionChange(row["change"]),
            summary=row["summary"],
            source=source,
            page=row["page"],
        )
        entries[entry.key] = entry
    return EditionDifferenceTable(entries)


class EditionComparison(RevalidatedModel):
    """What the registry says about one citation in another edition, in a sentence."""

    model_config = ConfigDict(frozen=True)

    citation: Provenance
    to_edition: str
    difference: EditionDifference | None

    @property
    def statement(self) -> str:
        if self.difference is not None:
            return str(self.difference)
        # Not "the editions agree": nothing here has compared them.
        return (
            f"no difference is registered between {self.citation} and edition "
            f"{self.to_edition}; that is a statement about this registry, not that the "
            "editions agree"
        )

    def __str__(self) -> str:
        return self.statement


def compare_editions(citation: str | Citation, to_edition: str) -> EditionComparison:
    """What became of ``citation``'s clause in ``to_edition``, or that nothing is registered.

    ``citation`` must name its edition: "AISC 360 §J3.6" is bolt strength in one edition
    and bolt spacing in the next, so a comparison from it would be a comparison from a
    guess.
    """
    parsed = citation if isinstance(citation, Citation) else parse_citation(citation)
    if parsed is None:
        raise _EditionInputError(
            f"{citation!r} names no edition, so there is nothing to compare from. A clause "
            "number alone can name different requirements in different editions",
            remedies=(
                Remedy(
                    action="replace",
                    subject="citation",
                    source="the citation with its edition, e.g. AISC 360-16 §J3.6",
                ),
            ),
        )
    return EditionComparison(
        citation=str(parsed),
        to_edition=to_edition,
        difference=default_edition_differences().find(parsed, to_edition),
    )
