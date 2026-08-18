"""Worked example: what a licensed engineer sees before deciding whether to seal.

A bracket screens to four checks. In declaration order they read: bending passes, shear
passes, fatigue not evaluated, deflection fails. That order is the order they were
written in, and it is no help at all to the person who has to decide where to look.

The dossier reorders them by what is most likely to change that decision:

1. **fatigue — did not run.** First, ahead of the failure. A FAIL is already visible and
   already blocking; a NOT_EVALUATED is the check that silently is not there, and it is
   the one a reviewer can miss entirely.
2. **deflection — fails.**
3. **bending — rests on an assumption nobody sourced.** It passes at a safety factor of
   3.0 and it is still here, because the verdict is only as good as the input nobody
   recorded the origin of. A check absent from the origin map is *unattributed*, never
   routine.
4. **shear — passes, but close to its requirement** (1.55 against 1.50). The band where
   an assumption the reviewer disagrees with flips the answer.

Then the part that matters most about review records: the engineer reviews it, and
somebody changes a load. The record does not quietly carry over. Its digest covers the
scorecard *and the toolchain version*, so the dossier reports that a prior review no
longer applies — which is different information from "never reviewed", and is exactly
what looks identical to "reviewed" from the outside.

Two things this example does not show, because Anvilate cannot do them: it never turns a
failing check into a pass, even with the engineer's accepted exception recorded against
it, and it never uses the language of certification about its own output. Responsible
charge is the engineer's; this is the material they need to exercise it.

Run it directly (``python examples/bracket_reviewer_dossier.py``);
:func:`review_the_bracket` is exercised in the test suite.
"""

from __future__ import annotations

from datetime import date

from anvilate.review import (
    DecisionOrigin,
    ReviewRecord,
    artifact_digest,
    build_dossier,
)
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

TOOLCHAIN = "anvilate 0.1.0"

BRACKET = Scorecard(
    entries=(
        ScorecardEntry.from_safety_factor("bending", computed=3.0, required=1.5),
        ScorecardEntry.from_safety_factor("shear", computed=1.55, required=1.5),
        ScorecardEntry(
            name="fatigue",
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no S-N detail category supplied for the weld",
        ),
        ScorecardEntry.from_safety_factor("deflection", computed=0.8, required=1.0),
    )
)
# `bending` is deliberately absent: nobody recorded where its allowable came from.
ORIGINS = {
    "shear": DecisionOrigin.DETERMINISTIC,
    "fatigue": DecisionOrigin.USER,
    "deflection": DecisionOrigin.DETERMINISTIC,
}
DETAILS = {"deflection": "AISC 360-16 serviceability limit, L/360"}


def review_the_bracket():
    """The dossier before review, after review, and after the design moved under it."""
    before = build_dossier(BRACKET, toolchain=TOOLCHAIN, origins=ORIGINS, origin_details=DETAILS)
    record = ReviewRecord(
        reviewer="A. Engineer, P.E.",
        reviewed_on=date(2026, 8, 17),
        covers_digest=artifact_digest(BRACKET, toolchain=TOOLCHAIN),
        scope="all four structural checks on the bracket",
        accepted_exceptions=("deflection",),
        notes="deflection accepted per RFI 12; the cladding tolerates L/240 here",
    )
    reviewed = build_dossier(
        BRACKET, toolchain=TOOLCHAIN, origins=ORIGINS, origin_details=DETAILS, record=record
    )
    # Somebody trims the section and bending drops from 3.0 to 2.1.
    moved = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("bending", computed=2.1, required=1.5),
            *BRACKET.entries[1:],
        )
    )
    after_change = build_dossier(
        moved, toolchain=TOOLCHAIN, origins=ORIGINS, origin_details=DETAILS, record=record
    )
    return before, reviewed, after_change


def main() -> None:
    before, reviewed, after_change = review_the_bracket()
    print("BEFORE REVIEW")
    print(f"  {before.summary()}")
    for item in before.items:
        print(f"    {item.priority.name.lower().replace('_', ' '):<24} {item.headline}")
    print("\nAFTER REVIEW")
    print(f"  {reviewed.summary()}")
    print(
        f"    deflection still renders "
        f"{reviewed.items[1].entry.status.value}, with the exception recorded"
    )
    print("\nAFTER SOMEBODY TRIMS THE SECTION")
    print(f"  {after_change.summary()}")


if __name__ == "__main__":
    main()
