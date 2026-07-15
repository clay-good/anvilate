"""Worked example: the band brake whose width, not strength, was the problem.

A scrap-yard winch drum must hold 500 N·m against a suspended load. The band
brake wraps 270 degrees around the 300 mm drum with a molded lining at mu = 0.25,
and the band assembly (strap, anchor pin, lever) is rated to 8 kN tension --
plenty: at the rated tension the wrap can hold ~830 N·m, a 1.66 margin on the
torque. Sized backwards, holding 500 N·m needs only ~4.8 kN at the tight end.

Then the lining check lands. Band pressure peaks at the tight end at
p = 2*T1/(b*D), and on the shop's 40 mm strap that is 0.80 MPa against the
lining maker's 0.60 MPa allowable -- the brake holds, and eats its lining. The
fix costs nothing structural: a 60 mm band spreads the same tension to
0.54 MPa and passes. The lesson: friction and wrap size the band *tension*,
but the lining pressure sizes the band *width* -- two different levers, and the
second one is the one that wears.

The lining friction and allowable pressure are manufacturer's data, declared
inline like any allowable.

Run it directly (``python examples/winch_band_brake.py``);
:func:`screen_winch_brake` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    band_brake_max_lining_pressure,
    band_brake_tight_tension_for_torque,
    band_brake_torque,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

REQUIRED_TORQUE = Quantity.parse("500 N*m")
DRUM_DIAMETER = Quantity.parse("300 mm")
WRAP_ANGLE = 3.0 * pi / 2.0  # 270 degrees of contact, in radians
FRICTION = 0.25  # molded lining on cast iron (manufacturer's data)
LINING_ALLOWABLE = Quantity.parse("0.60 MPa")  # lining maker's pressure limit
RATED_TENSION = Quantity.parse("8 kN")  # band strap / anchor pin rating

BAND_WIDTHS = (Quantity.parse("40 mm"), Quantity.parse("60 mm"))


def working_tension() -> Quantity:
    """The tight-side tension that holding the required torque demands."""
    return band_brake_tight_tension_for_torque(
        torque=REQUIRED_TORQUE,
        drum_diameter=DRUM_DIAMETER,
        friction_coefficient=FRICTION,
        wrap_angle=WRAP_ANGLE,
    )


def screen_winch_brake() -> Scorecard:
    """Screen the brake's torque capacity at the rated band tension, then the
    lining pressure at the working tension for each candidate band width."""
    capacity = band_brake_torque(
        tight_tension=RATED_TENSION,
        drum_diameter=DRUM_DIAMETER,
        friction_coefficient=FRICTION,
        wrap_angle=WRAP_ANGLE,
    )
    torque_margin = capacity.to("N*m").magnitude / REQUIRED_TORQUE.to("N*m").magnitude
    entries = [
        ScorecardEntry.from_safety_factor("hold torque", computed=torque_margin, required=1.0)
    ]
    tension = working_tension()
    allow = LINING_ALLOWABLE.to("MPa").magnitude
    for width in BAND_WIDTHS:
        pressure = band_brake_max_lining_pressure(
            tight_tension=tension, band_width=width, drum_diameter=DRUM_DIAMETER
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"lining pressure ({width.to('mm').magnitude:.0f} mm band)",
                computed=allow / pressure.to("MPa").magnitude,
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    tension = working_tension()
    torque = REQUIRED_TORQUE.to("N*m").magnitude
    print(f"tight-side tension to hold {torque:.0f} N*m: {tension.to('N').magnitude:.0f} N")
    print(screen_winch_brake())


if __name__ == "__main__":
    main()
