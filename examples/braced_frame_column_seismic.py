"""Worked example: the gravity column a seismic reversal puts into tension.

A column in a braced frame carries gravity load in compression all day — dead plus
a little live — and its base connection is sized, reflexively, for that compression.
But the brace that frames into it delivers a seismic axial force that reverses with
the ground motion. Under the reduced-dead seismic combination, 0.9D minus the
vertical seismic, with the horizontal seismic pulling the other way, the column can
go into net *tension* — a demand the gravity design never revealed, carried entirely
by anchor bolts and welds that were never checked for it.

The column here sees 60 kN dead and 30 kN live in compression, and a 180 kN seismic
axial force, at a site with S_DS = 1.0 and a redundancy factor of 1.3. The ASCE 7-22
§2.3.6 combinations give two very different governing demands. Compression peaks at
LRFD 6, (1.2 + 0.2·S_DS)·60 + 1.3·180 + 30 = 348 kN — a safety factor of 1.72
against the column's 600 kN capacity, comfortably clear. But LRFD 7 with the
reversed horizontal seismic, (0.9 − 0.2·S_DS)·60 − 1.3·180 = −192 kN, is a net
tension the gravity cases never produce. Screened against a base connection detailed
for 220 kN of tension, that is a safety factor of 1.15 — below the required 1.5, and
the check that actually governs.

The member is fine; the connection is the exposure. The lesson is the seismic one:
size the column on the compression envelope, but size its anchorage on the tension
the reversal reveals — and never let a gravity-only load case stand in for a seismic
combination on a member whose axial force reverses.

Run it directly (``python examples/braced_frame_column_seismic.py``);
:func:`screen_column` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.loads import LoadNature, asce7_lrfd_seismic, combination_scorecard
from anvilate.scorecard import Scorecard

# The load cases, in kN. Seismic axial is supplied as a magnitude; its reversal is
# handled by the ±Eh directions the generator builds.
LOADS = {
    LoadNature.DEAD: 60.0,
    LoadNature.LIVE: 30.0,
    LoadNature.SEISMIC: 180.0,
}

S_DS = 1.0  # design spectral acceleration (from the site — your input, not derived)
REDUNDANCY = 1.3  # ρ, the redundancy factor

COLUMN_COMPRESSION_CAPACITY = 600.0  # kN, the column in axial compression
CONNECTION_TENSION_CAPACITY = 220.0  # kN, what the base detail can carry in tension
REQUIRED_SF = 1.5


def screen_column() -> Scorecard:
    """Screen the column in compression and its base connection in tension.

    Compression is governed by the maximizing combination, the base tension by the
    minimizing (reversed-seismic) combination — two different governing cases.
    """
    combos = asce7_lrfd_seismic(s_ds=S_DS, redundancy=REDUNDANCY)
    return Scorecard(
        entries=(
            combination_scorecard(
                "column axial compression",
                combinations=combos,
                loads=LOADS,
                capacity=COLUMN_COMPRESSION_CAPACITY,
                required=REQUIRED_SF,
            ),
            combination_scorecard(
                "base connection tension (seismic reversal)",
                combinations=combos,
                loads=LOADS,
                capacity=CONNECTION_TENSION_CAPACITY,
                required=REQUIRED_SF,
                minimize=True,  # the net-tension case the gravity design never sees
            ),
        )
    )


def main() -> None:
    card = screen_column()
    print(card.report())
    for entry in card.entries:
        print(f"  {entry}")
    governing = card.governing()
    print(f"\ngoverning check: {governing.name} (utilization {governing.utilization:.2f})")


if __name__ == "__main__":
    main()
