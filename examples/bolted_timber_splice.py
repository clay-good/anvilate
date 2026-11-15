"""Worked example: the term the yield equations have and the usual clause does not.

A bolted double-shear splice in a Douglas Fir-Larch chord: one 3/4 in bolt through a
3-1/2 in main member with 1-1/2 in side members, grade-2 bolt steel. Six yield modes,
two of which a double-shear connection cannot reach, and mode IIIs governs: one plastic
hinge in the bolt with the side member crushing.

Drawn tight it is **7,693 lbf** of unreduced 5% offset yield. Now put a gap between the
members — a shim to line up a splice plate, a washer stack, a member that shrank away
from its neighbour. A quarter inch of gap takes **10.9%** of the capacity. An inch takes
**34.7%**.

The point is not the size of the loss. It is that **nothing floors it**. The gap enters
the governing mode's quadratic as a lever arm, so the capacity keeps falling as the gap
grows; and the yield limit clause an engineer reaches for first has no gap term at all,
which reads as "a gap does not matter" rather than "this clause assumes there is none."
A connection detailed with a shim is outside the clause, not conservatively inside it.

The second figure in the same splice is the grain angle. Resolve the side member's
dowel bearing strength to a load 30 degrees off the grain, which the Hankinson formula
does, and the same splice loses a further **9.4%** against the parallel-to-grain value
a caller gets by reaching for one number per species.

The example reports the tight capacity, the capacity at two gaps, and the angled-grain
capacity, each as the governing mode's unreduced value.

Run it directly (``python examples/bolted_timber_splice.py``);
:func:`bolted_timber_splice` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.dowel_yield import (
    DowelConnection,
    DowelYield,
    ShearPlanes,
    dowel_bearing_strength,
    dowel_yield_capacity,
    hankinson_bearing_strength,
)
from anvilate.units import Quantity

Q = Quantity.parse

#: Douglas Fir-Larch, the specific gravity the species table gives.
SPECIFIC_GRAVITY = 0.50
BOLT_DIAMETER = Q("0.75 inch")
#: A grade-2 bolt's dowel bending yield strength.
BOLT_BENDING_YIELD = Q("45000 psi")
MAIN_THICKNESS = Q("3.5 inch")
SIDE_THICKNESS = Q("1.5 inch")
GRAIN_ANGLE = Q("30 degree")

PARALLEL_BEARING = dowel_bearing_strength(specific_gravity=SPECIFIC_GRAVITY, diameter=BOLT_DIAMETER)
PERPENDICULAR_BEARING = dowel_bearing_strength(
    specific_gravity=SPECIFIC_GRAVITY, diameter=BOLT_DIAMETER, perpendicular=True
)


def _splice(gap: Quantity | None = None, side_bearing: Quantity | None = None) -> DowelYield:
    connection = DowelConnection(
        diameter=BOLT_DIAMETER,
        bending_yield_strength=BOLT_BENDING_YIELD,
        main_bearing_length=MAIN_THICKNESS,
        side_bearing_length=SIDE_THICKNESS,
        main_bearing_strength=PARALLEL_BEARING,
        side_bearing_strength=side_bearing or PARALLEL_BEARING,
        gap=gap,
        shear_planes=ShearPlanes.DOUBLE,
    )
    return dowel_yield_capacity(connection)


def drawn_tight() -> DowelYield:
    """The splice as detailed, members in contact."""
    return _splice()


def with_a_gap(gap: Quantity) -> DowelYield:
    """The same splice with ``gap`` of space between main and side members."""
    return _splice(gap=gap)


def at_an_angle_to_the_grain() -> DowelYield:
    """The tight splice with the side members' bearing strength resolved to the load."""
    return _splice(
        side_bearing=hankinson_bearing_strength(
            parallel=PARALLEL_BEARING,
            perpendicular=PERPENDICULAR_BEARING,
            angle=GRAIN_ANGLE,
        )
    )


def bolted_timber_splice() -> dict[str, float]:
    """The figures this example's prose turns on, each read off the yield modes."""

    def pounds(result: DowelYield) -> float:
        return result.capacity.to("lbf").magnitude

    tight = pounds(drawn_tight())
    quarter = pounds(with_a_gap(Q("0.25 inch")))
    inch = pounds(with_a_gap(Q("1 inch")))
    angled = pounds(at_an_angle_to_the_grain())
    return {
        "tight_lbf": tight,
        "quarter_inch_gap_lbf": quarter,
        "one_inch_gap_lbf": inch,
        "angled_grain_lbf": angled,
        "quarter_inch_loss_percent": 100.0 * (tight - quarter) / tight,
        "one_inch_loss_percent": 100.0 * (tight - inch) / tight,
        "angled_grain_loss_percent": 100.0 * (tight - angled) / tight,
    }


def main() -> None:
    print(f"parallel-to-grain dowel bearing strength: {PARALLEL_BEARING}")
    print(f"perpendicular: {PERPENDICULAR_BEARING}")
    print()
    for label, result in (
        ("drawn tight", drawn_tight()),
        ("1/4 in gap", with_a_gap(Q("0.25 inch"))),
        ("1 in gap", with_a_gap(Q("1 inch"))),
        (f"tight, load {GRAIN_ANGLE} to the grain", at_an_angle_to_the_grain()),
    ):
        print(f"--- {label}")
        print(result)
        for mode in result.modes:
            print(f"  {mode}")
        print()
    for name, value in bolted_timber_splice().items():
        print(f"{name}: {value:.4g}")


if __name__ == "__main__":
    main()
