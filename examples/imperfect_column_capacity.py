"""Worked example: the column that passed on paper and failed in steel.

An S355 steel column of intermediate slenderness (lambda = 90) carries a mean
compressive stress of 200 MPa. The textbook screen — the perfect-column limit, the
lesser of yield and the Euler buckling stress — puts its capacity at 244 MPa and
waves it through with a 1.22 margin.

Real columns are never perfectly straight, and that initial crookedness is exactly
what the Euler screen ignores. The Perry-Robertson model — the basis of every
modern column curve — folds in an imperfection and asks when the bowed column's
extreme fibre first yields. With a realistic imperfection factor of 0.3 the
capacity of this column falls to 174 MPa, a 29% knockdown that lands hardest near
the transition slenderness where this column sits. Against the same 200 MPa the
real column is overloaded (0.87): it fails.

The gap between the two numbers is not conservatism, it is the imperfection every
rolled column carries. Designing a mid-slenderness column to the ideal Euler curve
overstates its strength; the Perry-Robertson curve is the one that predicts the
steel. The imperfection factor is code data, declared inline like any allowable.

Run it directly (``python examples/imperfect_column_capacity.py``);
:func:`screen_column_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import perry_robertson_stress
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

YIELD_STRENGTH = Quantity.parse("355 MPa")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
SLENDERNESS = 90.0
APPLIED_STRESS = Quantity.parse("200 MPa")
IMPERFECTION_FACTOR = 0.3


def _capacity(imperfection: float) -> float:
    return (
        perry_robertson_stress(
            yield_strength=YIELD_STRENGTH,
            elastic_modulus=ELASTIC_MODULUS,
            slenderness_ratio=SLENDERNESS,
            imperfection_factor=imperfection,
        )
        .to("MPa")
        .magnitude
    )


def screen_column_capacity() -> Scorecard:
    """Screen the applied stress against the perfect-column capacity (imperfection
    = 0, the Euler/yield envelope) and the real Perry-Robertson capacity."""
    applied = APPLIED_STRESS.to("MPa").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "Euler / perfect-column screen",
                computed=_capacity(0.0) / applied,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "Perry-Robertson (real imperfection)",
                computed=_capacity(IMPERFECTION_FACTOR) / applied,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(f"perfect-column capacity: {_capacity(0.0):.0f} MPa")
    print(f"Perry-Robertson capacity: {_capacity(IMPERFECTION_FACTOR):.0f} MPa")
    print(screen_column_capacity())


if __name__ == "__main__":
    main()
