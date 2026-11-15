"""Worked example: the seventh bolt that makes the row weaker than six.

A bolted timber splice has a fixed amount of member to work with: 15 in of end zone on a
4x6 main member with two 2x6 side members, 3/4 in bolts in one row. Add bolts to that
fixed length and the spacing between them shrinks, and **two NDS factors read the
spacing**. The group action factor C_g (§11.3.6) falls because closer fasteners share
the load less evenly. The geometry factor C_Delta (§12.5.1) falls once the spacing drops
below 4D, and below 3D the detail is not permitted at all.

So the row's effective fastener count, `n x C_g x C_Delta`, is not monotone in n. Six
bolts at 3.00 in are worth **5.70** bolts. The seventh, at 2.50 in, is worth **5.48** —
the row is **3.9%** weaker for having one more bolt in it. The eighth would sit at
2.14 in, under the 2.25 in the clause permits, and the screen refuses rather than
returning a small factor.

This is not a rounding effect and it is not conservative. An engineer short of capacity
adds a fastener, the spreadsheet multiplies one bolt's capacity by seven, and the
connection is weaker than the one that was already failing.

The example reports the effective count at each n, the n where it turns over, and the
first n the geometry clause refuses.

Run it directly (``python examples/bolt_row_weakened_by_a_bolt.py``);
:func:`bolt_row_weakened_by_a_bolt` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import nds_geometry_factor, nds_group_action_factor
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

#: The end zone the detail has to fit the row into, first bolt to last.
ROW_LENGTH = Q("15 inch")
BOLT_DIAMETER = Q("0.75 inch")
#: 4x6 main member, actual 3.5 x 5.5 in.
MAIN_AREA = Q("19.25 inch**2")
#: Two 2x6 side members, actual 1.5 x 5.5 in each, summed as NDS §11.3.6 asks.
SIDE_AREA = Q("16.5 inch**2")
MODULUS = Q("1600000 psi")
#: NDS Table 12.5.1B, parallel to grain: 4D earns C_Delta = 1.0 and 3D is the floor.
FULL_VALUE_SPACING = Q("3 inch")
PERMITTED_SPACING = Q("2.25 inch")


def spacing_for(count: int) -> Quantity:
    """The centre-to-centre spacing ``count`` bolts leave in a fixed row length."""
    return Quantity(magnitude=ROW_LENGTH.to("inch").magnitude / (count - 1), unit="inch")


def effective_fasteners(count: int) -> float:
    """``n x C_g x C_Delta`` — the row's capacity in units of one bolt's capacity."""
    spacing = spacing_for(count)
    geometry = nds_geometry_factor(
        actual=spacing,
        minimum_for_full_value=FULL_VALUE_SPACING,
        minimum_permitted=PERMITTED_SPACING,
        diameter=BOLT_DIAMETER,
    )
    group = nds_group_action_factor(
        fasteners_in_row=count,
        diameter=BOLT_DIAMETER,
        spacing=spacing,
        main_area=MAIN_AREA,
        side_area=SIDE_AREA,
        main_modulus=MODULUS,
        side_modulus=MODULUS,
    )
    return count * group * geometry


def the_row(upper: int = 10) -> dict[int, float | str]:
    """Every count from two up, each with its effective fastener count or its refusal."""
    rows: dict[int, float | str] = {}
    for count in range(2, upper + 1):
        try:
            rows[count] = effective_fasteners(count)
        except RefusalError as refused:
            rows[count] = str(refused)
    return rows


def bolt_row_weakened_by_a_bolt() -> dict[str, float]:
    """The figures this example's prose turns on."""
    rows = the_row()
    worked = {n: v for n, v in rows.items() if isinstance(v, float)}
    best = max(worked, key=lambda n: worked[n])
    refused = min((n for n, v in rows.items() if isinstance(v, str)), default=0)
    return {
        "six_bolts_effective": worked[6],
        "seven_bolts_effective": worked[7],
        "loss_percent_for_the_seventh": 100.0 * (worked[6] - worked[7]) / worked[6],
        "best_count": float(best),
        "first_refused_count": float(refused),
        "sixth_spacing_in": spacing_for(6).to("inch").magnitude,
        "seventh_spacing_in": spacing_for(7).to("inch").magnitude,
        "eighth_spacing_in": spacing_for(8).to("inch").magnitude,
    }


def main() -> None:
    for count, value in the_row().items():
        inches = spacing_for(count).to("inch").magnitude
        if isinstance(value, float):
            print(f"{count:2d} bolts at {inches:5.2f} in — worth {value:.3f} bolts")
        else:
            print(f"{count:2d} bolts at {inches:5.2f} in — refused: {value}")
    print()
    for name, value in bolt_row_weakened_by_a_bolt().items():
        print(f"{name}: {value:.4g}")


if __name__ == "__main__":
    main()
