"""Worked example: the weld detail, not the stress, decides fatigue life.

Two welded brackets carry the identical service spectrum — the same stress ranges,
the same cycle counts. One survives its design life with room to spare; the other
cracks. The only difference is the weld *detail*: how the joint is made and where the
weld toe sits relative to the stress flow. In EN 1993-1-9 that choice is a detail
category, the fatigue strength at two million cycles, and it is the number an
engineer actually gets wrong.

The spectrum is 100,000 cycles at a 90 MPa stress range, a million at 60 MPa, and ten
million at 40 MPa. Run against a category-56 detail — a transverse attachment welded
across the flow, a harsh notch — the standardized S-N curve gives short lives and the
Palmgren-Miner damage sums to 2.5: the detail is spent two and a half times over
before the design life is reached. Move to a category-90 detail — a ground,
flow-aligned weld — and the same spectrum sums to 0.33, a comfortable margin. Nothing
about the loads changed; the weld geometry did.

Anvilate encodes the standardized curve construction — the m = 3 and m = 5 slopes, the
constant-amplitude limit at five million cycles, the cutoff at a hundred million — and
composes it with the Palmgren-Miner summation already in the library. The detail
category itself is a user-supplied input from EN 1993-1-9 (Anvilate ships the curve,
not the copyrighted table), so the engineer owns and defends the one judgment that
matters. Run it directly (``python examples/welded_bracket_fatigue.py``);
:func:`screen_detail` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import weld_fatigue_scorecard
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

# The service spectrum: (applied cycles, nominal stress range). Identical for both
# details — only the weld category differs.
SPECTRUM = (
    (100_000.0, "90 MPa"),
    (1_000_000.0, "60 MPa"),
    (10_000_000.0, "40 MPa"),
)

HARSH_DETAIL = Quantity.parse("56 MPa")  # transverse attachment across the stress flow
GOOD_DETAIL = Quantity.parse("90 MPa")  # ground, flow-aligned weld


def screen_detail(detail_category: Quantity) -> Scorecard:
    """Screen the spectrum against a weld detail category.

    The Palmgren-Miner damage D must stay below 1 for the detail to survive its
    design life, so the fatigue safety factor is 1/D against a required 1.0.
    """
    return Scorecard(
        entries=(
            weld_fatigue_scorecard(
                "weld fatigue (Miner damage)",
                applied_cycles=[cycles for cycles, _ in SPECTRUM],
                stress_ranges=[Quantity.parse(stress) for _, stress in SPECTRUM],
                detail_category=detail_category,
                required=1.0,
            ),
        )
    )


def screen_harsh_detail() -> Scorecard:
    """The category-56 detail: the spectrum spends it 2.5 times over."""
    return screen_detail(HARSH_DETAIL)


def screen_good_detail() -> Scorecard:
    """The category-90 detail: the same spectrum survives with margin."""
    return screen_detail(GOOD_DETAIL)


def main() -> None:
    for label, detail in (
        ("category 56 (harsh)", HARSH_DETAIL),
        ("category 90 (good)", GOOD_DETAIL),
    ):
        entry = screen_detail(detail).entries[0]
        # SF = 1/D, so the Miner damage is the reciprocal of the reported factor.
        print(f"{label}: Miner damage {1.0 / entry.safety_factor:.2f}")
        print(f"  {entry}")


if __name__ == "__main__":
    main()
