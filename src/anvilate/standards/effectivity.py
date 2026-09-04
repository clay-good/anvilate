"""Standards effectivity: which edition a citation means, and whether they agree.

Every check in this library cites a clause, and the evidence bundle's whole claim is
"these numbers came from these clauses". A clause without an edition weakens that claim
to the point of being unfalsifiable: AISC 360-16 and -22 both have a Chapter E, ACI
318-14 and -19 both have a §22.8, and they do not always say the same thing. "AISC
§E3" identifies a paragraph in a book nobody named.

Three separable things, and this module is careful not to confuse them:

**What the library was written against.** A fact about this repository, verifiable by
reading it. :data:`WRITTEN_AGAINST` records it, one entry per standard, and the contract
gate holds it against the source so it cannot drift.

**What a project has adopted.** The user's to declare. A :class:`DesignBasis` pins an
edition per standard, and :meth:`DesignBasis.conflicts` reports where the pinned edition
is not the one a check was written against. Mixing editions inside one bundle is
permitted — it is what actually happens on real projects, where a structure is designed
to one code and a retrofit assessed under another — but it is never silent: it requires
a recorded :class:`MixedEditionWaiver` naming who accepted it and why.

**Which edition applies to a jurisdiction.** Not this module's business, and it will not
guess. Adoption is a legal question that varies by state, county and city, changes on
schedules nobody publishes centrally, and being wrong about it is the kind of wrong that
ends up in a deposition. A user who knows their adopted code says so; the library does
not infer it from an address.

Sources: none needed for the mechanism — the standard designations are names, and the
editions recorded here are read off this library's own source rather than asserted about
the world.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .._models import EMPTY_MAP, FrozenMap, Provenance, RevalidatedModel
from ..derivation import DerivationAbsence, Underived
from ..scorecard import CheckStatus, ScorecardEntry

__all__ = [
    "STANDARDS_BODIES",
    "Citation",
    "EditionAgreement",
    "MixedEditionWaiver",
    "DesignBasis",
    "WRITTEN_AGAINST",
    "parse_citation",
    "names_a_standard",
    "design_basis_scorecard",
]

# The bodies whose documents have editions. A citation naming one of these and no edition
# is incomplete; a citation naming Roark, Timoshenko or Shigley is not, because a textbook
# is cited by author and its printing is not a normative parameter. Keeping the two apart
# is the whole reason this is a curated list rather than "anything capitalised".
#
# NEC is listed beside NFPA because that is the name the electrical pack cites it by, and
# the National Electrical Code is issued in editions (2020, 2023) whose ampacity tables and
# voltage-drop guidance are not identical. BS is listed for BS 7910, whose editions carry
# different failure-assessment options.
#
# Two kinds of source are deliberately NOT here. OSHA 29 CFR 1910.95 is a REGULATION: its
# "edition" is a CFR revision date, an editionless citation of it is not the same defect,
# and listing it would fill the effectivity debt with lines whose fix is a different one.
# The IES Lighting Handbook is a handbook, cited the way Roark is — the illuminance
# recommendations are a reference table, and its printing is not a normative parameter.
STANDARDS_BODIES: frozenset[str] = frozenset(
    {
        "AASHTO",
        "ACI",
        "AGMA",
        "AISC",
        "AISI",
        "AMCA",
        "ANSI",
        "API",
        "ASCE",
        "ASHRAE",
        "ASME",
        "ASTM",
        "AWS",
        "AWWA",
        "BS",
        "DIN",
        "EN",
        "IEC",
        "IEEE",
        "ISO",
        "NEC",
        "NEMA",
        "NFPA",
        "NDS",
        "SAE",
        "TMS",
        "UL",
        "Aluminum Design Manual",
    }
)


def names_a_standard(text: str) -> str | None:
    """The standards body ``text`` cites, or ``None`` if it cites no standard at all.

    Used to decide whether a missing edition is a *gap* or simply not applicable. A
    reference reading "Timoshenko plate theory" is complete as it stands — a textbook has
    no edition semantics — while "ASME BTH-1 §3-3" is a normative document cited without
    saying which one, and those must not be counted together.
    """
    if not text:
        return None
    for body in sorted(STANDARDS_BODIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(body)}\b", text):
            return body
    return None


# The edition of each standard THIS LIBRARY's checks were written against. This is a
# statement about the repository, not about which edition is current or adopted anywhere.
# The contract gate reads the source and fails if a check cites a different edition of a
# standard listed here, so the two cannot drift apart.
WRITTEN_AGAINST: dict[str, str] = {
    "AISC 360": "16",
    "ACI 318": "19",
    "ASCE 7": "22",
    "Aluminum Design Manual": "2020",
    # The weld-fatigue curve anchors (N_C = 2M, N_D = 5M, N_L = 100M, m = 3 then 5) and
    # the §8 elastic limit are EN 1993-1-9:2005 — the only published edition, and the one
    # this library's own WeldDetailCategory records already declare.
    "EN 1993-1-9": "2005",
    # EN 15978:2011 is the only edition, and it is what the A1-A3 module boundary the
    # embodied-carbon screen refuses to mix comes from.
    "EN 15978": "2011",
}

# A standard designation followed by its edition: "AISC 360-16", "ASCE 7-22",
# "Aluminum Design Manual 2020", "EN 1993-1-9:2005". The edition is a trailing year —
# two-digit after a hyphen, four-digit after a space or a colon.
# Three ways an edition is written, and one shape that is not an edition at all.
#
# `-YYYY` is unambiguous: "ASME B31.3-2022", "AWS D1.1-2020", "ASME B36.10M-2018". These
# used to parse as no edition, because the four-digit branch required a space or a colon in
# front of the year — so a code that names its edition in the ordinary way was recorded as
# naming none, and a bundle citing it reported NOT_EVALUATED.
#
# `-NN` is the ambiguous one, and the ambiguity is not hypothetical: ASME Section VIII's
# clauses are "UG-37", "UG-99(b)", "UW-12", and this library cites two of them. They parsed
# as the standard "ASME VIII Div 1 UG" at editions 37 and 99, so a bundle carrying a UG-37
# reinforcement check and a UG-99 hydrostatic test FAILED `design_basis_scorecard` with
# "ASME VIII Div 1 UG appears at editions 37, 99" — one code, two clauses, read as a mixed
# edition. What separates the two cases is the character in front of the hyphen: a
# designation ending in a digit ("AISC 360", "ACI 318", "AISI S100") takes an edition
# suffix; one ending in a letter is a clause prefix and the number after it is the clause.
# This is the same trap the Eurocode pattern below already guards, in its other spelling.
_CITATION = re.compile(
    r"(?P<standard>[A-Z][A-Za-z0-9 .&/-]*?[A-Za-z0-9])"
    r"(?:"
    r"-(?P<hyphenated>(?:19|20)\d{2})\b"
    r"|(?<=\d)-(?P<short>\d{2})(?![\d-])"
    r"|[\s:](?P<long>(?:19|20)\d{2})\b"
    r")"
)
# Eurocode designations are EN 1990 through EN 1999 — document numbers that read exactly
# like years, and the one place a year-shaped token is not an edition. "EN 1993-1-9" names
# Eurocode 3 part 1-9 at no edition at all; its edition is the ":2005" that may follow.
# Getting this wrong would silently record every Eurocode citation as a 1990s edition.
_EUROCODE_NUMBERS = {str(n) for n in range(1990, 2000)}
# So Eurocodes get their own pattern, which reads the part numbers as part of the
# designation and takes the edition from the colon suffix where one is given.
_EUROCODE = re.compile(r"\bEN 199\d(?:-\d+)*(?::(?P<edition>(?:19|20)\d{2}))?")


class EditionAgreement(StrEnum):
    """How a project's pinned edition relates to the one a check was written against."""

    MATCHES = "matches"
    DIFFERS = "differs"
    NOT_PINNED = "not pinned"
    NOT_RECORDED = "not recorded"  # the citation itself names no edition to compare


class Citation(RevalidatedModel):
    """A standard, its edition, and the clause — the three parts of a real citation.

    ``edition`` is a string, not an integer, because that is how editions are written and
    because "16" and "2016" are the same edition spelled two ways while "16" and "2016"
    as integers are not comparable at all. :func:`parse_citation` normalises the spelling.
    """

    model_config = ConfigDict(frozen=True)

    standard: Provenance
    edition: Provenance
    clause: str = ""
    # How the source joined the designation to the edition, kept because it cannot be
    # derived. All three conventions are in daily use — `AISC 360-16`, `Aluminum Design
    # Manual 2020`, `ISO 286-2:2010` — and which one a standard uses is a fact about that
    # standard, not about the shape of its edition. The renderer guessed from the edition's
    # *length* (two digits meant a hyphen), which was right only while four-digit editions
    # could reach it in one spelling: it rendered `ASME B31.3-2022` as `ASME B31.3 2022`.
    separator: Literal["-", " ", ":"] = "-"

    def __str__(self) -> str:
        base = f"{self.standard}{self.separator}{self.edition}"
        return f"{base} {self.clause}".rstrip()


def parse_citation(text: str) -> Citation | None:
    """Pull the standard, edition and clause out of a reference string, or ``None``.

    ``None`` means *this text does not name an edition* — which is the finding, not an
    error. The library's existing citations are free text, and the great majority of them
    name a standard without an edition. Returning ``None`` rather than guessing a default
    is what lets the contract gate count the debt honestly instead of papering over it.

    Editions are normalised to the spelling the standard itself uses: a two-digit
    suffix stays two-digit (``AISC 360-16``), a four-digit year stays four
    (``Aluminum Design Manual 2020``).
    """
    if not text or not text.strip():
        return None
    eurocode = _EUROCODE.search(text)
    if eurocode is not None:
        edition = eurocode.group("edition")
        if edition is None:
            return None  # "EN 1993-1-9" names a part, and no edition at all
        designation = eurocode.group(0).split(":")[0]
        return Citation(
            standard=designation,
            edition=edition,
            clause=text[eurocode.end() :].strip(" ,;:"),
            separator=":",  # a Eurocode's edition is always the colon suffix
        )
    for match in _CITATION.finditer(text):
        standard = match.group("standard").strip()
        edition = match.group("hyphenated") or match.group("short") or match.group("long")
        # "EN 1993" is Eurocode 3, not the 1993 edition of something called EN.
        if standard == "EN" and edition in _EUROCODE_NUMBERS:
            continue
        # "29 CFR 1926" is OSHA's construction part, not the 1926 edition of the Code of
        # Federal Regulations. This library cites it beside a B30.20 proof test, and it
        # parsed as `OSHA 29 CFR` at edition `1926` — so a bundle citing 29 CFR 1926 and
        # 29 CFR 1910 would have read as one regulation at two editions. Third spelling of
        # the same trap: a document number that looks like a year or an edition suffix.
        if standard.endswith("CFR"):
            continue
        clause = text[match.end() :].strip(" ,;:")
        # The separator the source used, read off the branch that matched rather than
        # guessed from the edition afterwards.
        if match.group("long") is not None:
            separator = text[match.start("long") - 1]
        else:
            separator = "-"
        return Citation(standard=standard, edition=edition, clause=clause, separator=separator)
    return None


class MixedEditionWaiver(RevalidatedModel):
    """A recorded acceptance that one bundle spans more than one edition of a standard.

    Mixing is not forbidden — it is what real projects do, where a structure was designed
    to one code and a retrofit is assessed under another. What is forbidden is mixing
    *silently*, because the resulting bundle reads as though every number came from one
    book. ``accepted_by`` and ``rationale`` are required and may not be blank: a waiver
    with nobody's name on it is not a waiver, it is a suppressed warning.
    """

    model_config = ConfigDict(frozen=True)

    standard: Provenance
    editions: tuple[str, ...]
    accepted_by: str
    rationale: str
    accepted_on: date

    @model_validator(mode="after")
    def _well_formed(self) -> MixedEditionWaiver:
        if len(set(self.editions)) < 2:
            raise ValueError(
                f"a mixed-edition waiver covers at least two editions of {self.standard}; "
                f"got {self.editions}. One edition needs no waiver."
            )
        for value, name in ((self.accepted_by, "accepted_by"), (self.rationale, "rationale")):
            if not value.strip():
                raise ValueError(
                    f"{name} may not be blank — a waiver with nobody's name on it and no "
                    f"reason is a suppressed warning, not an accepted risk"
                )
        return self


class DesignBasis(RevalidatedModel):
    """The editions a project has adopted, and the waivers it has recorded.

    ``pins`` maps a standard designation to the edition this project designs to, e.g.
    ``{"AISC 360": "22"}``. Nothing infers it: adoption is a legal question that varies
    by jurisdiction and changes on schedules nobody publishes centrally, and a library
    that guesses it would be confidently wrong somewhere.
    """

    model_config = ConfigDict(frozen=True)

    pins: FrozenMap[str, str] = Field(default_factory=lambda: EMPTY_MAP)
    waivers: tuple[MixedEditionWaiver, ...] = ()

    def agreement(self, citation: Citation | None) -> EditionAgreement:
        """How ``citation`` stands against this basis.

        ``None`` — a reference that names no edition — is :attr:`EditionAgreement.NOT_RECORDED`:
        there is nothing to agree or disagree with, which is precisely the problem.

        This reads the project's pins only. What the *library* was written against is
        :data:`WRITTEN_AGAINST`, and it is a different question with a different answer —
        :func:`design_basis_scorecard` asks both, because a pin no citation in the bundle
        matches is still a declaration the library can answer.
        """
        if citation is None:
            return EditionAgreement.NOT_RECORDED
        pinned = self.pins.get(citation.standard)
        if pinned is None:
            return EditionAgreement.NOT_PINNED
        return EditionAgreement.MATCHES if pinned == citation.edition else EditionAgreement.DIFFERS

    def conflicts(self, citations: list[Citation | None]) -> tuple[str, ...]:
        """Every standard appearing at more than one edition without a recorded waiver.

        Reported per standard rather than per citation, because the question a reviewer
        asks is "was this bundle built out of one book or two", and it is asked once per
        standard.
        """
        seen: dict[str, set[str]] = {}
        for citation in citations:
            if citation is None:
                continue
            seen.setdefault(citation.standard, set()).add(citation.edition)
        waived = {w.standard: set(w.editions) for w in self.waivers}
        out: list[str] = []
        for standard, editions in sorted(seen.items()):
            if len(editions) < 2:
                continue
            covered = waived.get(standard, set())
            if editions <= covered:
                continue
            out.append(
                f"{standard} appears at editions {', '.join(sorted(editions))} with no "
                f"recorded waiver covering them"
            )
        return tuple(out)


def design_basis_scorecard(
    name: str,
    *,
    basis: DesignBasis,
    references: list[str],
) -> ScorecardEntry:
    """Screen a bundle's citations against a design basis → a :class:`ScorecardEntry`.

    ``references`` are the raw reference strings the checks carried. The entry is:

    * ``FAIL`` when one standard appears at two editions with no recorded waiver — the
      bundle reads as though it came from one book and did not.
    * ``NOT_EVALUATED`` when any reference names no edition at all. That is not a pass:
      an unversioned clause cannot be checked against a basis, and reporting the ones
      that happen to carry editions would describe a bundle nobody assembled.
    * ``PASS`` only when every reference names an edition and no standard is split.

    A reference whose edition differs from a pinned one is *reported*, not failed — a
    project may deliberately assess an existing structure under the edition it was
    designed to, and the basis says which is which.
    """
    # An empty reference list is a bundle whose citations were never collected, not a
    # bundle whose citations all check out. Reporting PASS on it — with a detail line
    # asserting "all 0 references name an edition" — is the same silent green
    # `Scorecard.status` already refuses for an empty entry tuple.
    if not references:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "not evaluated — no references were supplied, so there is nothing to "
                "check against the design basis. An empty citation list is a bundle "
                "whose citations were not collected, not one that agrees"
            ),
            reference="standards effectivity",
            underived=Underived(
                kind=DerivationAbsence.LOOKUP,
                reason=(
                    "a consistency verdict over the citations a bundle carries — every "
                    "reference names an edition, and no standard appears at two. No quantity "
                    "is calculated"
                ),
            ),
        )
    citations = [parse_citation(text) for text in references]
    editionless = [text for text, c in zip(references, citations, strict=True) if c is None]
    conflicts = basis.conflicts(citations)

    # A pin is a declaration, and a declaration nothing reads is the silent green this
    # library refuses. Two things can answer one: a citation this bundle carries, or the
    # library's own WRITTEN_AGAINST. A pin no citation matched is NOT unanswerable — the
    # library still knows which edition its checks were written to, and a project pinning
    # ASCE 7-16 against load combinations written to ASCE 7-22 must hear about it whether
    # or not this particular bundle happens to cite ASCE 7.
    cited_standards = {c.standard for c in citations if c is not None}
    uncited_pins = {s: e for s, e in basis.pins.items() if s not in cited_standards}
    against_library = sorted(
        f"{standard}-{edition} is pinned while this library's checks are written "
        f"against {standard}-{WRITTEN_AGAINST[standard]}"
        for standard, edition in uncited_pins.items()
        if standard in WRITTEN_AGAINST and WRITTEN_AGAINST[standard] != edition
    )
    # What is left is a pin naming a designation nothing in this bundle cites and this
    # library does not declare — most often a spelling that cannot match ("AISC-360" for
    # "AISC 360"). It screens against nothing, so the card may not say it passed.
    unread_pins = sorted(s for s in uncited_pins if s not in WRITTEN_AGAINST)
    differing = sorted(
        {
            f"{c.standard}-{c.edition} against the pinned {basis.pins[c.standard]}"
            for c in citations
            if c is not None and basis.agreement(c) is EditionAgreement.DIFFERS
        }
    )

    detail_parts: list[str] = []
    if against_library:
        detail_parts.append("; ".join(against_library))
    if differing:
        detail_parts.append(
            "cited at an edition other than the pinned one: " + "; ".join(differing)
        )
    if basis.waivers:
        # The rationale and the date, not only the name. `MixedEditionWaiver` requires
        # `accepted_by` AND `rationale` for one stated reason — a waiver with nobody's name
        # on it and no reason is a suppressed warning, not an accepted risk — and the entry
        # carried the name alone, which is half of what the model says makes it a waiver.
        # The reason a risk was accepted is the substance of the acceptance; a reviewer
        # reading "AISC 360 16/22 by A. Engineer" cannot tell an assessed retrofit from a
        # mistake somebody signed.
        detail_parts.append(
            "recorded waivers: "
            + "; ".join(
                f"{w.standard} {'/'.join(w.editions)} by {w.accepted_by} "
                f"on {w.accepted_on.isoformat()}: {w.rationale}"
                for w in basis.waivers
            )
        )

    if conflicts:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.FAIL,
            detail="; ".join([*conflicts, *detail_parts]),
            reference="standards effectivity",
            underived=Underived(
                kind=DerivationAbsence.LOOKUP,
                reason=(
                    "a consistency verdict over the citations a bundle carries — every "
                    "reference names an edition, and no standard appears at two. No quantity "
                    "is calculated"
                ),
            ),
        )
    if editionless:
        shown = ", ".join(repr(t) for t in editionless[:3])
        more = f" (and {len(editionless) - 3} more)" if len(editionless) > 3 else ""
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"not evaluated — {len(editionless)} of {len(references)} references name no "
                f"edition, so they cannot be checked against a design basis: {shown}{more}. "
                f"An unversioned clause identifies a paragraph in a book nobody named."
            ),
            reference="standards effectivity",
            underived=Underived(
                kind=DerivationAbsence.LOOKUP,
                reason=(
                    "a consistency verdict over the citations a bundle carries — every "
                    "reference names an edition, and no standard appears at two. No quantity "
                    "is calculated"
                ),
            ),
        )
    if unread_pins:
        known = sorted(cited_standards | set(WRITTEN_AGAINST))
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"not evaluated — {len(unread_pins)} pinned "
                f"{'standard is' if len(unread_pins) == 1 else 'standards are'} named by no "
                f"citation in this bundle and not declared by this library, so the basis was "
                f"screened against nothing: {', '.join(repr(s) for s in unread_pins)}. "
                f"Designations available to pin: {', '.join(known)}"
            ),
            reference="standards effectivity",
            underived=Underived(
                kind=DerivationAbsence.LOOKUP,
                reason=(
                    "a consistency verdict over the citations a bundle carries — every "
                    "reference names an edition, and no standard appears at two. No quantity "
                    "is calculated"
                ),
            ),
        )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS,
        detail="; ".join(
            [
                f"all {len(references)} references name an edition and no standard is split",
                *detail_parts,
            ]
        ),
        reference="standards effectivity",
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "a consistency verdict over the citations a bundle carries — every "
                "reference names an edition, and no standard appears at two. No quantity "
                "is calculated"
            ),
        ),
    )
