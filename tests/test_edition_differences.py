"""The edition-difference registry: what became of a cited clause, read off the publisher."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from anvilate.standards.edition_differences import (
    EditionChange,
    compare_editions,
    default_edition_differences,
)

_SRC = Path(__file__).resolve().parents[1] / "src" / "anvilate"
_COMPARISON = "https://www.aisc.org/media/myzl4doa/2022-to-2016-spec-comparison.pdf"


def _cited_aisc_360_16_clauses() -> set[str]:
    found: set[str] = set()
    for path in _SRC.rglob("*.py"):
        found |= set(re.findall(r"AISC 360-16 (§[A-Z]\d+(?:\.\d+)*)", path.read_text("utf-8")))
    return found


def test_every_clause_the_library_cites_under_360_16_has_a_registered_answer():
    """A check pinned to AISC 360-16 says what became of its clause in 360-22. A new pinned
    citation fails here until its entry is read off the comparison document."""
    cited = _cited_aisc_360_16_clauses()
    assert len(cited) >= 10, cited
    registered = {key.split(" ", 2)[2] for key in default_edition_differences().designations()}
    assert cited <= registered, sorted(cited - registered)


def test_a_renumbered_clause_names_its_successor_and_its_source():
    """AISC 360-16 §J3.6 is bolt strength; in 360-22 bolt strength is §J3.7, and §J3.6 is
    bolt spacing. The comparison says so on page 19."""
    comparison = compare_editions("AISC 360-16 §J3.6 (bolt shear)", "22")
    difference = comparison.difference
    assert difference is not None
    assert difference.change is EditionChange.RENUMBERED and difference.successor == "§J3.7"
    assert difference.page == 19 and _COMPARISON in difference.source
    assert "maximum spacing and edge distance" in difference.summary
    assert comparison.statement.startswith("AISC 360-16 §J3.6 → AISC 360-22 §J3.7: renumbered")


def test_a_revised_coefficient_is_stated():
    difference = compare_editions("AISC 360-16 §F6", "22").difference
    assert difference.change is EditionChange.REVISED
    assert "0.69 multiplier in Equation F6-4 is 0.70" in difference.summary


def test_no_entry_is_stated_as_no_entry_and_never_as_agreement():
    comparison = compare_editions("AISC 360-16 §F2.2", "22")
    assert comparison.difference is None
    assert comparison.statement.startswith("no difference is registered")
    assert "not that the editions agree" in comparison.statement
    assert str(comparison) == comparison.statement
    # And an entry for the wrong target edition is not borrowed.
    assert compare_editions("AISC 360-16 §J3.6", "10").difference is None


def test_a_citation_without_an_edition_cannot_be_compared():
    """ "AISC 360 §J3.6" is bolt strength in one edition and bolt spacing in the next."""
    with pytest.raises(ValueError, match="names no edition"):
        compare_editions("AISC 360 §J3.6", "22")


def test_unchanged_is_claimed_only_with_a_page_behind_it():
    """The comparison lists only revised sections, so "unchanged" is the publisher's claim
    for an unlisted section; each such entry still cites where it would have appeared."""
    entries = [
        default_edition_differences().get(k) for k in default_edition_differences().designations()
    ]
    unchanged = [e for e in entries if e.change is EditionChange.UNCHANGED]
    assert {e.clause for e in unchanged} >= {"§D2", "§H1.2", "§J4.2", "§J4.3", "§J8", "§L3"}
    for entry in entries:
        assert 1 <= entry.page <= 37, entry
        assert entry.summary.strip() and _COMPARISON in entry.source
