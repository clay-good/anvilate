"""Worked example: sizing a bimetal thermostat blade to reach its trip contact.

A thermostat is a cantilever of two bonded metals -- here Invar (almost no thermal
expansion) backed with brass (a lot of it). Heat the blade and the brass grows while
the Invar holds, so the strip curls toward the Invar side; its free tip sweeps across
a gap and closes (or opens) a contact at a set temperature. The design question is
simple: at the temperature rise that should trip it, does the tip actually move far
enough to reach the contact?

Timoshenko's bimetal formula turns the two expansion coefficients, moduli, and
thicknesses into a curvature, and a cantilever of length L deflects its tip by
(1/rho)*L^2/2. The L-squared is the lever. For a 50 K rise this 0.6 mm-thick blade
must clear a 2.5 mm contact gap: a 40 mm blade reaches only 1.77 mm and fails to
trip, a 50 mm blade makes 2.77 mm and just trips, and a 60 mm blade sweeps 3.99 mm
with room to spare. Doubling the length would quadruple the stroke, so a blade that
falls short is lengthened (or thinned, or given a larger expansion mismatch), not
merely nudged.

The point is that a bimetal actuator's stroke is a geometry problem as much as a
materials one: the metals set the curvature per degree, but the length sets how much
tip motion that curvature becomes. The layer materials and geometry are declared
inline.

Run it directly (``python examples/bimetal_thermostat_blade.py``);
:func:`screen_thermostat_blades` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import bimetallic_strip_tip_deflection
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LAYERS = {
    "alpha_1": Quantity.parse("1.2e-6 1/K"),  # Invar (low-expansion) side
    "elastic_modulus_1": Quantity.parse("145 GPa"),
    "thickness_1": Quantity.parse("0.3 mm"),
    "alpha_2": Quantity.parse("19e-6 1/K"),  # brass (high-expansion) side
    "elastic_modulus_2": Quantity.parse("110 GPa"),
    "thickness_2": Quantity.parse("0.3 mm"),
    "temperature_change": Quantity.parse("50 K"),
}
CONTACT_GAP = Quantity.parse("2.5 mm")
BLADE_LENGTHS = (Quantity.parse("40 mm"), Quantity.parse("50 mm"), Quantity.parse("60 mm"))


def screen_thermostat_blades() -> Scorecard:
    """Screen each candidate blade length: its tip deflection at the trip temperature
    rise must reach the contact gap (safety factor = tip deflection / gap)."""
    gap = CONTACT_GAP.to("mm").magnitude
    entries = []
    for length in BLADE_LENGTHS:
        tip = bimetallic_strip_tip_deflection(length=length, **LAYERS)
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{length.to('mm').magnitude:.0f} mm blade",
                computed=abs(tip.to("mm").magnitude) / gap,
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for length in BLADE_LENGTHS:
        tip = abs(bimetallic_strip_tip_deflection(length=length, **LAYERS).to("mm").magnitude)
        print(f"{length.to('mm').magnitude:.0f} mm blade: tip sweep {tip:.2f} mm")
    print(screen_thermostat_blades())


if __name__ == "__main__":
    main()
