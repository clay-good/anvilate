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
from collections.abc import Callable
from enum import StrEnum
from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING

from pydantic import ConfigDict

from .._models import Provenance, RevalidatedModel, _near_identifiers, cited, parse_yaml
from ..refusal import RefusalError, Remedy
from ..units import Quantity
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

# The clause a citation's free text names: "§J3.6 (bolt shear)" is §J3.6, and so are
# "§ J3.6", "Section J3.6", "Chapter J, §J3.6" and a bare "J3.6". Each of those was matched
# as written, found no entry, and was told no difference is registered. A subclause
# (§J3.6.1) or an equation (Eq. J3-1) is not its clause, and does not borrow its entry.
_CLAUSE = re.compile(r"(?:§|\bSect(?:ion|\.)?)\s*([A-Za-z]\d+(?:\.\d+)*)(?![\d.])")
_BARE_CLAUSE = re.compile(r"([A-Z]\d+(?:\.\d+)*)(?![\d.\w-])")


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
        text = citation.clause.strip()
        clause = _CLAUSE.search(text) or _BARE_CLAUSE.match(text)
        if clause is None:
            return None
        key = f"{citation.standard}-{citation.edition} §{clause.group(1).upper()}"
        entry = self._entries.get(key)
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
    # The check evaluated under each edition, when the caller can: (edition, result) pairs,
    # the cited edition first.
    results: tuple[tuple[str, Quantity], ...] = ()

    @property
    def statement(self) -> str:
        if self.difference is not None:
            said = str(self.difference)
        else:
            # Not "the editions agree": nothing here has compared them.
            said = (
                f"no difference is registered between {self.citation} and edition "
                f"{self.to_edition}; that is a statement about this registry, not that the "
                "editions agree"
            )
        if not self.results:
            return said
        side_by_side = "; ".join(f"under {edition}: {value}" for edition, value in self.results)
        return f"{self.citation} evaluates {side_by_side}. {said}"

    def __str__(self) -> str:
        return self.statement


def _target_edition(cited: Citation, written: str) -> str:
    """The edition ``written`` names, read the way the citation's own edition is.

    The registry is keyed on the bare edition, so `AISC 360-22` and `22 ` were looked up as
    themselves and told that no difference is registered for a clause that has one. A
    designation is accepted when it is the cited standard's, and refused when it is another's.
    """
    text = written.strip()
    prefix, separator, edition = text.rpartition(cited.separator)
    if separator:
        named = prefix.strip()
        # `360` names AISC 360 and `60` does not: the designation ends on a word.
        if named and not (cited.standard == named or cited.standard.endswith(f" {named}")):
            raise _EditionInputError(
                f"{written!r} is an edition of {named}, and {cited} is {cited.standard}: the "
                "comparison is between two editions of one standard",
                remedies=(
                    Remedy(
                        action="replace",
                        subject="to_edition",
                        source=f"an edition of {cited.standard}, e.g. {cited.edition}",
                    ),
                ),
            )
        text = edition.strip()
    if not text:
        raise _EditionInputError(
            f"to_edition {written!r} names no edition of {cited.standard} to compare to",
            remedies=(
                Remedy(
                    action="replace",
                    subject="to_edition",
                    source=f"an edition of {cited.standard}, written as the citation writes "
                    f"its own ({cited.edition})",
                ),
            ),
        )
    return text


def compare_editions(
    citation: str | Citation,
    to_edition: str,
    *,
    evaluate: Callable[[str], Quantity] | None = None,
) -> EditionComparison:
    """What became of ``citation``'s clause in ``to_edition``, or that nothing is registered.

    ``citation`` must name its edition: "AISC 360 §J3.6" is bolt strength in one edition
    and bolt spacing in the next, so a comparison from it would be a comparison from a
    guess. ``evaluate``, given an edition, returns the check's result under it; with it the
    comparison carries both results beside the differing clauses and the registry citation.
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
    to_edition = _target_edition(parsed, to_edition)
    results = (
        ()
        if evaluate is None
        else tuple(
            (f"{parsed.standard}{parsed.separator}{edition}", evaluate(edition))
            for edition in (parsed.edition, to_edition)
        )
    )
    return EditionComparison(
        citation=str(parsed),
        to_edition=to_edition,
        difference=default_edition_differences().find(parsed, to_edition),
        results=results,
    )
