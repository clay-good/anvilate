"""Worked example: the strut that crinkles long before it would ever buckle.

A thin steel tube -- 200 mm across, a 0.5 mm wall -- is pressed 2 m long as a
compression strut at 200 MPa, well under the 250 MPa yield. Checked as a column it
looks bombproof: at a slenderness of only 28 its Euler critical stress is 2455 MPa,
twelve times the working stress. Nothing about the column check hints at a problem.

But a thin-walled tube does not fail as a column. Long before the whole strut bows,
its wall buckles *locally* -- the skin folds into a diamond pattern the way a soda can
crushes -- and that happens at a stress the column formula never considers. The
classical shell buckling stress here is 607 MPa, and thin cylinders are so sensitive
to tiny dimples that codes knock it down hard; at a conservative 0.3 the allowable is
182 MPa, below the 200 MPa working stress. The strut fails by shell buckling (safety
factor 0.91) while sitting at 1/13 of its Euler column capacity.

The lesson is that slenderness is the wrong question for a thin shell. A compact strut
is governed by column buckling and yield; a thin-walled one is governed by *local*
shell buckling at a far lower stress, and it is acutely imperfection-sensitive, which
is why the classical value is only reached in the laboratory and real designs apply a
steep knockdown. Sizing a tube as a solid column overstates its strength many times
over. The tube, length, and knockdown are declared inline.

Run it directly (``python examples/thin_tube_shell_buckling.py``);
:func:`screen_tube_strut` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    cylinder_axial_buckling_stress,
    euler_critical_stress,
    hollow_circular_second_moment,
    radius_of_gyration,
    slenderness_ratio,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

OUTER_DIAMETER = Quantity.parse("200 mm")
WALL_THICKNESS = Quantity.parse("0.5 mm")
LENGTH = Quantity.parse("2 m")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
WORKING_STRESS = Quantity.parse("200 MPa")
SHELL_KNOCKDOWN = 0.3  # conservative allowance for imperfection sensitivity


def screen_tube_strut() -> Scorecard:
    """Screen the working stress against the Euler column-buckling stress and the
    knocked-down shell (local wall) buckling stress (safety factor = capacity /
    working stress)."""
    working = WORKING_STRESS.to("MPa").magnitude
    inner_diameter = Quantity(
        magnitude=OUTER_DIAMETER.to("mm").magnitude - 2 * WALL_THICKNESS.to("mm").magnitude,
        unit="mm",
    )
    do = OUTER_DIAMETER.to("mm").magnitude
    di = inner_diameter.to("mm").magnitude
    area = Quantity(magnitude=pi * (do**2 - di**2) / 4, unit="mm**2")
    second_moment = hollow_circular_second_moment(
        outer_diameter=OUTER_DIAMETER, inner_diameter=inner_diameter
    )
    lam = slenderness_ratio(
        effective_length=LENGTH,
        radius_of_gyration=radius_of_gyration(second_moment=second_moment, area=area),
    )
    euler = (
        euler_critical_stress(elastic_modulus=ELASTIC_MODULUS, slenderness_ratio=lam)
        .to("MPa")
        .magnitude
    )
    shell = (
        SHELL_KNOCKDOWN
        * cylinder_axial_buckling_stress(
            elastic_modulus=ELASTIC_MODULUS,
            wall_thickness=WALL_THICKNESS,
            mean_radius=Quantity(magnitude=(do - WALL_THICKNESS.to("mm").magnitude) / 2, unit="mm"),
        )
        .to("MPa")
        .magnitude
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "Euler column buckling", computed=euler / working, required=1.0
            ),
            ScorecardEntry.from_safety_factor(
                "shell (local wall) buckling", computed=shell / working, required=1.0
            ),
        )
    )


def main() -> None:
    print(screen_tube_strut())


if __name__ == "__main__":
    main()
