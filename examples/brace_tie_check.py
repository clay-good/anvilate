"""Worked example: screening a bolted single-angle brace tie with the structural pack.

Declares a diagonal brace — a single L102x102x12.7 angle bolted through one leg —
that carries a 250 kN tension, and screens its two AISC 360-16 §D2 limit states in
one call. The instructive part: the gross section yields comfortably, but bolting
through only one leg engages the section unevenly, so the shear-lag factor U cuts
the effective net area and net-section rupture (§D2(b)) — not gross yielding — is
what governs. A gross-area-only hand check would miss the tighter limit state.

Run it directly (``python examples/brace_tie_check.py``); :func:`screen_brace_tie`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.structural import TensionMember, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

BRACE_LOAD = Quantity.parse("250 kN")


def screen_brace_tie() -> Scorecard:
    """Declare and screen the bolted single-angle brace, returning the scorecard."""
    tie = TensionMember(
        name="brace",
        gross_area=Quantity.parse("2420 mm**2"),  # L102x102x12.7 single angle
        net_area=Quantity.parse("2141 mm**2"),  # less one 22 mm bolt hole in the leg
        load=BRACE_LOAD,
        material="ASTM-A36",
        shear_lag_factor=0.6,  # single angle bolted through one leg (§D3, Table D3.1)
    )
    # AISC ASD: Omega = 1.67 on the governing tensile strength.
    return screen_structure([tie], required_safety_factor=1.67)


def main() -> None:
    card = screen_brace_tie()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
