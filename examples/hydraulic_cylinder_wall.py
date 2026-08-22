"""Worked example: an r/t = 2.5 barrel is not a thin-wall problem, and now it says so.

A hydraulic cylinder barrel — Ø50 bore, 10 mm wall, AISI 4140 annealed — holds 600 bar
(60 MPa). Fed to the thin-wall membrane formula the wall used to look comfortable:
σ = p·r/t = 150 MPa, SF 2.78 against the 417 MPa yield. But p·r/t is a membrane average
that is only honest above r/t ≈ 10, and this barrel sits at 2.5.

**The membrane form now refuses the geometry instead of answering it.** That refusal is
the example: an audit found the r/t ≳ 10 scope stated in three docstrings and enforced
nowhere, and the number it used to return was wrong in the direction that matters. So the
first entry here is NOT_EVALUATED carrying the library's own reason, not a comfortable
safety factor a reader has to know to distrust.

The exact Lamé solution answers the same barrel: the bore hoop is 185 MPa riding on
−60 MPa of radial compression, so the bore works at a Tresca intensity of 245 MPa — SF
1.70, FAIL at the required 2.0. Same barrel, same steel, same pressure. The two effects
the membrane average cannot see, the stress gradient through the wall and the biaxial
pinch at the bore, both err non-conservative.

Run it directly (``python examples/hydraulic_cylinder_wall.py``);
:func:`screen_cylinder_barrel` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import strength_scorecard, thick_wall_cylinder, thin_wall_cylinder
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

PRESSURE = Quantity.parse("60 MPa")  # 600 bar service
BORE_RADIUS = Quantity.parse("25 mm")
WALL = Quantity.parse("10 mm")
STEEL = "AISI-4140"
REQUIRED_SF = 2.0


def screen_cylinder_barrel() -> Scorecard:
    """Screen the same barrel with the membrane shortcut and the exact Lamé form."""
    record = default_materials_db().get(STEEL)
    yield_strength = record.yield_strength.quantity

    ratio = BORE_RADIUS.to("mm").magnitude / WALL.to("mm").magnitude
    try:
        thin = thin_wall_cylinder(pressure=PRESSURE, radius=BORE_RADIUS, wall_thickness=WALL)
    except ValueError as refusal:
        membrane_entry = ScorecardEntry(
            name=f"thin-wall membrane (r/t {ratio:.1f})",
            status=CheckStatus.NOT_EVALUATED,
            detail=f"not evaluated — {refusal}",
        )
    else:  # pragma: no cover - the guard makes this branch unreachable for this barrel
        membrane_entry = strength_scorecard(
            f"thin-wall membrane (r/t {thin.thin_wall_ratio:.1f})",
            stress=thin.hoop_stress,
            allowable=yield_strength,
            required=REQUIRED_SF,
        )
    thick = thick_wall_cylinder(pressure=PRESSURE, radius=BORE_RADIUS, wall_thickness=WALL)

    entries = (
        membrane_entry,
        strength_scorecard(
            "Lame bore intensity",
            stress=thick.bore_tresca_stress,
            allowable=yield_strength,
            required=REQUIRED_SF,
        ),
    )
    return Scorecard(entries=entries)


def main() -> None:
    card = screen_cylinder_barrel()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
