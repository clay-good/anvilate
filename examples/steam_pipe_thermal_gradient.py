"""Worked example: the pipe stress that has nothing to do with its pressure.

A steel pipe carries 2 MPa steam. Sizing it for pressure is easy: the thin-wall hoop
stress is p*r/t = 20 MPa, a trivial fraction of the 250 MPa yield -- a safety factor
of 12. On the pressure check the pipe is enormously overbuilt.

But a steam pipe is hot on the inside and cooler on the outside, and the wall is
restrained from bowing by its own length and its supports. That through-wall
temperature gradient develops a bending stress the pressure calculation never sees:
for a 150 K difference across the wall it comes to E*alpha*dT/(2(1-nu)) = 257 MPa --
past yield, a safety factor of 0.97. The stress that governs this pipe is not the one
it was named for. It is why power-plant piping cracks by thermal fatigue at startups
and trips, where the gradient swings hardest, long before pressure ever threatens it,
and why such lines are warmed slowly and heavily insulated to keep the gradient down.

The lesson is that a pressure vessel is not only a pressure problem. A component that
runs hot with a temperature difference across its wall must be checked for the
thermal gradient too -- and here that check, not the pressure one, decides the pipe.
The wall geometry, pressure, and gradient are declared inline.

Run it directly (``python examples/steam_pipe_thermal_gradient.py``);
:func:`screen_steam_pipe` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    thin_wall_cylinder,
    through_wall_gradient_thermal_stress,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

INTERNAL_PRESSURE = Quantity.parse("2 MPa")
MEAN_RADIUS = Quantity.parse("100 mm")
WALL_THICKNESS = Quantity.parse("10 mm")
WALL_TEMPERATURE_DIFFERENCE = Quantity.parse("150 K")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
THERMAL_EXPANSION = Quantity.parse("12e-6 1/K")
YIELD = Quantity.parse("250 MPa")
REQUIRED_SAFETY_FACTOR = 1.5


def screen_steam_pipe() -> Scorecard:
    """Screen the pipe against yield on both its pressure hoop stress and its
    through-wall thermal-gradient stress (safety factor = yield / stress)."""
    yield_strength = YIELD.to("MPa").magnitude
    hoop = (
        thin_wall_cylinder(
            pressure=INTERNAL_PRESSURE, radius=MEAN_RADIUS, wall_thickness=WALL_THICKNESS
        )
        .hoop_stress.to("MPa")
        .magnitude
    )
    thermal = (
        through_wall_gradient_thermal_stress(
            elastic_modulus=ELASTIC_MODULUS,
            thermal_expansion_coefficient=THERMAL_EXPANSION,
            temperature_difference=WALL_TEMPERATURE_DIFFERENCE,
        )
        .to("MPa")
        .magnitude
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "pressure hoop stress",
                computed=yield_strength / hoop,
                required=REQUIRED_SAFETY_FACTOR,
            ),
            ScorecardEntry.from_safety_factor(
                "through-wall thermal gradient",
                computed=yield_strength / thermal,
                required=REQUIRED_SAFETY_FACTOR,
            ),
        )
    )


def main() -> None:
    hoop = thin_wall_cylinder(
        pressure=INTERNAL_PRESSURE, radius=MEAN_RADIUS, wall_thickness=WALL_THICKNESS
    ).hoop_stress
    thermal = through_wall_gradient_thermal_stress(
        elastic_modulus=ELASTIC_MODULUS,
        thermal_expansion_coefficient=THERMAL_EXPANSION,
        temperature_difference=WALL_TEMPERATURE_DIFFERENCE,
    )
    print(f"pressure hoop stress:        {hoop.to('MPa').magnitude:.0f} MPa")
    print(f"through-wall thermal stress: {thermal.to('MPa').magnitude:.0f} MPa")
    print(screen_steam_pipe())


if __name__ == "__main__":
    main()
