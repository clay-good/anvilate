"""Worked example: the horizontal thrust on a footing quietly halves its bearing capacity.

A footing rarely carries a purely vertical load. The base of a retaining wall, the footing under
a braced-frame column, an abutment taking bridge thrust — all carry a horizontal force alongside
the vertical one, and that inclination costs bearing capacity, because some of the soil's strength
is spent resisting sliding instead of plunging. Meyerhof's inclination factors quantify it from
the load's angle from vertical. This example takes a footing carrying 1000 kN down and 200 kN
sideways (a modest 11° tilt) and shows the ultimate bearing pressure fall by more than a third
once the inclination factors are applied — capacity that a vertical-only check would wrongly
count on. The self-weight term is hit hardest, since it vanishes entirely once the load angle
reaches the friction angle.

Run it directly (``python examples/inclined_load_footing.py``);
:func:`inclined_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bearing_capacity_factors,
    bearing_inclination_factors,
    terzaghi_bearing_capacity,
)
from anvilate.units import Quantity

FRICTION_ANGLE = 30.0
COHESION = Quantity.parse("25 kPa")
SURCHARGE = Quantity.parse("18 kPa")
UNIT_WEIGHT = Quantity.parse("18 kN/m**3")
WIDTH = Quantity.parse("2 m")
VERTICAL_LOAD = Quantity.parse("1000 kN")
HORIZONTAL_LOAD = Quantity.parse("200 kN")


def inclined_capacity() -> dict[str, float]:
    """Return the vertical-only and inclined-load ultimate bearing pressures (kPa)."""
    n = bearing_capacity_factors(friction_angle=FRICTION_ANGLE)
    common = {
        "cohesion": COHESION,
        "surcharge": SURCHARGE,
        "unit_weight": UNIT_WEIGHT,
        "width": WIDTH,
    }
    vertical = (
        terzaghi_bearing_capacity(
            bearing_factor_c=n["N_c"],
            bearing_factor_q=n["N_q"],
            bearing_factor_gamma=n["N_gamma"],
            **common,
        )
        .to("kPa")
        .magnitude
    )
    i = bearing_inclination_factors(
        vertical_load=VERTICAL_LOAD,
        horizontal_load=HORIZONTAL_LOAD,
        friction_angle=FRICTION_ANGLE,
    )
    inclined = (
        terzaghi_bearing_capacity(
            bearing_factor_c=n["N_c"] * i["i_c"],
            bearing_factor_q=n["N_q"] * i["i_q"],
            bearing_factor_gamma=n["N_gamma"] * i["i_gamma"],
            **common,
        )
        .to("kPa")
        .magnitude
    )
    return {
        "vertical_kpa": vertical,
        "inclined_kpa": inclined,
        "ratio": inclined / vertical,
    }


def main() -> None:
    r = inclined_capacity()
    print(f"vertical-only q_ult  : {r['vertical_kpa']:.0f} kPa")
    print(f"inclined-load q_ult  : {r['inclined_kpa']:.0f} kPa (1000 kN down, 200 kN across)")
    lost = (1 - r["ratio"]) * 100
    print(f"  -> the 11 deg tilt costs {lost:.0f}% of the bearing capacity")


if __name__ == "__main__":
    main()
