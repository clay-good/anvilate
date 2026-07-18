"""Worked example: the shaft bore that doubles a flywheel's peak stress.

A solid steel flywheel disc, 600 mm across, spins at 7000 rpm. As a solid disc its
peak stress sits at the centre and comes to 157 MPa -- against a 350 MPa yield that
is a comfortable 2.24 safety factor. So far so good.

But a flywheel has to mount on a shaft, which means a hole down the axis. Rotating
elastic theory has a sharp surprise here: boring even a *small* hole at the centre
does not just remove a little material, it moves the peak stress to the bore and
*doubles* it. The bored disc's peak stress climbs to 314 MPa, a 1.12 safety factor
-- the same disc at the same speed now fails a 2.0 requirement. The hole the design
needs is the thing that breaks it.

This is why flywheels and turbine rotors are so sensitive to their centre detail:
you cannot simply drill the disc you sized as solid. The fixes are to run slower, to
mount the disc on a stub shaft it grips by a shrink fit rather than a through-bore,
or to move to a stronger material -- but never to ignore the doubling. The stress
distributions come from the solid- and annular-disc closed forms; the material and
speed are declared inline.

Run it directly (``python examples/flywheel_bore_stress.py``);
:func:`screen_flywheel_bore` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    rotating_annular_disc_bore_stress,
    rotating_solid_disc_max_stress,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

DENSITY = Quantity.parse("7850 kg/m**3")
OUTER_RADIUS = Quantity.parse("300 mm")
BORE_RADIUS = Quantity.parse("25 mm")
SPEED = Quantity.parse("7000 rpm")
YIELD = Quantity.parse("350 MPa")
REQUIRED_SAFETY_FACTOR = 2.0


def screen_flywheel_bore() -> Scorecard:
    """Screen the peak stress of the disc as solid and as bored against yield
    (safety factor = yield / peak stress, required >= 2.0)."""
    yield_strength = YIELD.to("MPa").magnitude
    solid = rotating_solid_disc_max_stress(
        density=DENSITY, outer_radius=OUTER_RADIUS, rotational_speed=SPEED
    )
    bored = rotating_annular_disc_bore_stress(
        density=DENSITY,
        outer_radius=OUTER_RADIUS,
        inner_radius=BORE_RADIUS,
        rotational_speed=SPEED,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "solid disc (peak at centre)",
                computed=yield_strength / solid.to("MPa").magnitude,
                required=REQUIRED_SAFETY_FACTOR,
            ),
            ScorecardEntry.from_safety_factor(
                "disc with shaft bore (peak at bore)",
                computed=yield_strength / bored.to("MPa").magnitude,
                required=REQUIRED_SAFETY_FACTOR,
            ),
        )
    )


def main() -> None:
    solid = rotating_solid_disc_max_stress(
        density=DENSITY, outer_radius=OUTER_RADIUS, rotational_speed=SPEED
    )
    bored = rotating_annular_disc_bore_stress(
        density=DENSITY,
        outer_radius=OUTER_RADIUS,
        inner_radius=BORE_RADIUS,
        rotational_speed=SPEED,
    )
    print(f"solid-disc centre stress: {solid.to('MPa').magnitude:.0f} MPa")
    print(f"bored-disc bore stress:   {bored.to('MPa').magnitude:.0f} MPa")
    print(screen_flywheel_bore())


if __name__ == "__main__":
    main()
