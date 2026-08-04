"""Worked example: a clay pile that carries its load on its sides, not its tip.

People picture a pile as a column that stands on firm ground at its tip, but a slender pile
driven into clay works almost entirely the other way — by friction along its shaft. This example
sizes a 400 mm bored pile 15 m into stiff clay by the α-method and splits its capacity into the
two mechanisms: the shaft skin friction and the end bearing. The shaft carries about 990 kN and
the tip barely 85 kN, so more than nine-tenths of the load never reaches the bottom of the pile.
That split is why deepening a friction pile a little buys real capacity (more shaft), while
fattening the tip buys almost none. Dividing the ultimate by a factor of safety of 2.5 gives the
working load the pile can actually be designed to.

Run it directly (``python examples/friction_pile_capacity.py``);
:func:`pile_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    pile_allowable_capacity,
    pile_end_bearing_capacity,
    pile_skin_friction_capacity,
)
from anvilate.units import Quantity

UNDRAINED_STRENGTH = Quantity.parse("75 kPa")  # c_u, stiff clay
ADHESION_FACTOR = 0.7  # alpha for stiff clay
DIAMETER = Quantity.parse("0.4 m")
LENGTH = Quantity.parse("15 m")
FACTOR_OF_SAFETY = 2.5


def pile_capacity() -> dict[str, float]:
    """Return the shaft, tip, and allowable capacities (kN) and the shaft's share of the total."""
    shaft = pile_skin_friction_capacity(
        adhesion_factor=ADHESION_FACTOR,
        undrained_shear_strength=UNDRAINED_STRENGTH,
        diameter=DIAMETER,
        length=LENGTH,
    )
    tip = pile_end_bearing_capacity(
        undrained_shear_strength=UNDRAINED_STRENGTH,
        diameter=DIAMETER,
    )
    allowable = pile_allowable_capacity(
        skin_friction=shaft, end_bearing=tip, factor_of_safety=FACTOR_OF_SAFETY
    )
    shaft_kn = shaft.to("kN").magnitude
    tip_kn = tip.to("kN").magnitude
    return {
        "shaft_kn": shaft_kn,
        "tip_kn": tip_kn,
        "allowable_kn": allowable.to("kN").magnitude,
        "shaft_fraction": shaft_kn / (shaft_kn + tip_kn),
    }


def main() -> None:
    p = pile_capacity()
    print(f"shaft skin friction : {p['shaft_kn']:.0f} kN")
    print(f"end bearing (tip)   : {p['tip_kn']:.0f} kN")
    print(f"  -> the shaft carries {p['shaft_fraction']:.0%} of the ultimate load")
    print(f"allowable (FS 2.5)  : {p['allowable_kn']:.0f} kN working load")


if __name__ == "__main__":
    main()
