"""Worked example: the flywheel that stored, held, and still whirled.

A press flywheel is a Ø400 x 50 mm steel disc — 49 kg — running at 3000 rpm on a
Ø40 mm shaft spanning 600 mm between bearings. Three different things about it all
depend on that speed, and a flywheel is only right if all three are:

* it must store enough energy to smooth the press stroke — at a 5% speed
  fluctuation the disc trades 4870 J against a 4000 J demand (1.22);
* it must not burst — the centrifugal rim hoop stress rho*v^2 is a trivial 31 MPa
  against a 150 MPa allowable (4.84), because at this radius and speed the rim is
  loafing;
* and its shaft must not whirl — the disc's mass on the slender Ø40 shaft has a
  lateral critical speed of just 54 Hz, uncomfortably close to the 50 Hz running
  speed and short of the 1.25x separation the drive needs (0.86).

The flywheel does its job and is nowhere near bursting, yet the assembly fails —
on the one speed limit a stress or energy check never sees. The disc is fine; the
shaft is too slender for the mass hung on it, and the fix is a stiffer shaft (a
Ø50 shaft lifts the critical speed to 84 Hz), not a different flywheel. Sizing a
rotor means checking every speed-dependent limit, and the whirl is the quiet one.

The density, modulus, and allowable are material data, declared inline.

Run it directly (``python examples/flywheel_speed_limits.py``);
:func:`screen_flywheel` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    circular_second_moment,
    flywheel_energy_fluctuation,
    natural_frequency,
    rotating_rim_hoop_stress,
    solid_disc_polar_mass_moment,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

DENSITY = Quantity.parse("7850 kg/m**3")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
DISC_DIAMETER = Quantity.parse("400 mm")
DISC_THICKNESS = Quantity.parse("50 mm")
SPEED = Quantity.parse("3000 rpm")
COEFFICIENT_OF_FLUCTUATION = 0.05
ENERGY_DEMAND = Quantity.parse("4000 J")
RIM_ALLOWABLE = Quantity.parse("150 MPa")
SHAFT_DIAMETER = Quantity.parse("40 mm")
BEARING_SPAN = Quantity.parse("600 mm")
RUNNING_FREQUENCY = Quantity.parse("50 Hz")
SEPARATION_FACTOR = 1.25


def _disc_mass() -> float:
    r = DISC_DIAMETER.to("m").magnitude / 2.0
    return DENSITY.to("kg/m**3").magnitude * pi * r**2 * DISC_THICKNESS.to("m").magnitude


def screen_flywheel() -> Scorecard:
    """Screen the flywheel's three speed-dependent limits: stored energy, rim
    burst stress, and shaft whirl critical speed."""
    mass = _disc_mass()
    inertia = solid_disc_polar_mass_moment(
        mass=Quantity(magnitude=mass, unit="kg"), diameter=DISC_DIAMETER
    )
    energy = flywheel_energy_fluctuation(
        inertia=inertia, mean_speed=SPEED, coefficient_of_fluctuation=COEFFICIENT_OF_FLUCTUATION
    )
    rim_stress = rotating_rim_hoop_stress(
        density=DENSITY, mean_radius=Quantity.parse("200 mm"), rotational_speed=SPEED
    )
    # Shaft lateral critical speed: central mass on a simply-supported shaft,
    # k = 48*E*I / L^3, then f = (1/2pi)*sqrt(k/m).
    second_moment = circular_second_moment(diameter=SHAFT_DIAMETER).to("m**4").magnitude
    span = BEARING_SPAN.to("m").magnitude
    stiffness = 48.0 * ELASTIC_MODULUS.to("Pa").magnitude * second_moment / span**3
    critical = natural_frequency(
        stiffness=Quantity(magnitude=stiffness, unit="N/m"),
        mass=Quantity(magnitude=mass, unit="kg"),
    )
    running = RUNNING_FREQUENCY.to("Hz").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "stored energy",
                computed=energy.to("J").magnitude / ENERGY_DEMAND.to("J").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "rim burst stress",
                computed=RIM_ALLOWABLE.to("MPa").magnitude / rim_stress.to("MPa").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "shaft whirl critical speed",
                computed=critical.to("Hz").magnitude / (running * SEPARATION_FACTOR),
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(f"disc mass: {_disc_mass():.0f} kg")
    print(screen_flywheel())


if __name__ == "__main__":
    main()
