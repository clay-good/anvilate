"""Worked example: how fast to spin a centrifugal-casting mold — the G-factor sets the speed.

Centrifugal casting makes a sound cast pipe by spinning the mold so the melt is flung against the
wall, packing a dense outer skin while slag and gas float to the bore. The quality depends not on
the rpm directly but on the centrifugal field at the wall, measured in multiples of gravity — the
G-factor. Too few G and the metal will not pack or the slag will not separate; too many and the mold
strains and the metal spatters. So the foundry picks a target G-factor from the alloy and the part,
and the rpm falls out of the wall radius: a big pipe reaches the same G at a far lower speed than a
small ring, which is why spin speed is never quoted without the diameter.

This example casts a pipe of 150 mm bore (75 mm wall radius) in molten steel (7000 kg/m³), aiming
for a 90 G field. Inverting G = ω²·r/g gives a mold speed of about 1036 rpm. Spinning at that, the
example checks the G-factor back out (90, as designed) and computes the metallostatic pressure the
rotation presses on a 90 mm outer wall: about 0.10 MPa squeezing the solidifying skin dense. The
example reports the required speed, the achieved G-factor, and the wall pressure, so the chain from
quality target to machine setting to the pressure that packs the casting is explicit.

Run it directly (``python examples/centrifugal_cast_pipe_speed.py``);
:func:`centrifugal_cast_setup` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    centrifugal_g_factor,
    centrifugal_speed_for_g_factor,
    centrifugal_wall_pressure,
)
from anvilate.units import Quantity

TARGET_G_FACTOR = 90.0
BORE_RADIUS = Quantity.parse("75 mm")  # free surface at the bore
OUTER_RADIUS = Quantity.parse("90 mm")  # mold wall
MELT_DENSITY = Quantity.parse("7000 kg/m**3")


def centrifugal_cast_setup() -> dict[str, float]:
    """Return the spin speed for the target G, the achieved G-factor, and the wall pressure."""
    speed = centrifugal_speed_for_g_factor(g_factor=TARGET_G_FACTOR, radius=BORE_RADIUS)
    achieved_g = centrifugal_g_factor(rotational_speed=speed, radius=BORE_RADIUS)
    pressure = centrifugal_wall_pressure(
        rotational_speed=speed,
        density=MELT_DENSITY,
        inner_radius=BORE_RADIUS,
        outer_radius=OUTER_RADIUS,
    )
    return {
        "speed_rpm": speed.to("rpm").magnitude,
        "achieved_g_factor": achieved_g,
        "wall_pressure_mpa": pressure.to("MPa").magnitude,
    }


def main() -> None:
    d = centrifugal_cast_setup()
    print(f"mold speed for {TARGET_G_FACTOR:.0f} G: {d['speed_rpm']:.0f} rpm")
    print(f"G-factor check at that speed: {d['achieved_g_factor']:.0f} G")
    print(
        f"metallostatic wall pressure: {d['wall_pressure_mpa']:.2f} MPa "
        f"-> packs the outer skin dense"
    )


if __name__ == "__main__":
    main()
