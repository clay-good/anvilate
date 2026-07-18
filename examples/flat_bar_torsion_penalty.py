"""Worked example: the same steel, four times the twist, from the section shape.

A short shaft has to carry 200 N*m of torque over a metre without twisting more than
2 degrees. There is 1000 mm^2 of steel to spend on the cross-section, and two ways to
spend it: a compact ~31.6 mm square, or a flat 100 x 10 mm bar. They weigh the same.
They do not twist the same.

Torsion is unforgiving of thin, spread-out sections. The compact square gathers its
material near the centre where torsion wants it and twists 1.0 degrees -- inside the
limit. The flat bar spreads the same area into a wide, thin strip that St. Venant
torsion barely resists, and it twists 4.6 degrees, more than four times as much, well
past the limit. The torsion constant of a rectangle collapses as it gets thin (toward
the b*t^3/3 of an open strip), so the flat bar is a poor torsion member however much
metal it contains.

The lesson is that a member's torsional stiffness is set by how its area is arranged,
not just how much there is -- and for torsion, compact and closed beats wide and open
every time. A flat bar that twists too far is not fixed by making it thicker in the
plane it is already wide in; it wants a squarer section (or, better, a closed tube).
The sections and load are declared inline.

Run it directly (``python examples/flat_bar_torsion_penalty.py``);
:func:`screen_torsion_sections` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rectangular_bar_twist_angle
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

TORQUE = Quantity.parse("200 N*m")
LENGTH = Quantity.parse("1 m")
SHEAR_MODULUS = Quantity.parse("80 GPa")
TWIST_LIMIT_DEGREES = 2.0
SECTIONS = {
    "compact square (31.6 x 31.6 mm)": (Quantity.parse("31.62 mm"), Quantity.parse("31.62 mm")),
    "flat bar (100 x 10 mm)": (Quantity.parse("100 mm"), Quantity.parse("10 mm")),
}


def screen_torsion_sections() -> Scorecard:
    """Screen the twist of each equal-area section against the 2-degree limit
    (safety factor = limit / twist)."""
    limit = TWIST_LIMIT_DEGREES
    entries = []
    for name, (width, thickness) in SECTIONS.items():
        twist = (
            rectangular_bar_twist_angle(
                torque=TORQUE,
                length=LENGTH,
                width=width,
                thickness=thickness,
                shear_modulus=SHEAR_MODULUS,
            )
            .to("degree")
            .magnitude
        )
        entries.append(
            ScorecardEntry.from_safety_factor(name, computed=limit / twist, required=1.0)
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, (width, thickness) in SECTIONS.items():
        twist = rectangular_bar_twist_angle(
            torque=TORQUE,
            length=LENGTH,
            width=width,
            thickness=thickness,
            shear_modulus=SHEAR_MODULUS,
        )
        print(f"{name}: twist {twist.to('degree').magnitude:.2f} deg")
    print(screen_torsion_sections())


if __name__ == "__main__":
    main()
