"""Worked example: how long sand and silt take to settle, and why fines set the tank size.

A sedimentation tank works by giving particles time to fall out of suspension, and Stokes' law says
that time is brutally sensitive to particle size: the settling velocity goes as the *square* of the
diameter. This example drops two particles through 2 m of still water in a clarifier — a 100 µm
grain of fine sand and a 10 µm silt particle, a tenfold difference in size. The sand reaches the
floor in minutes; the silt, a hundred times slower, takes hours. That is why a clarifier sized to
the sand does nothing for the silt, and why removing fines needs either a much larger tank or a
coagulant to clump them into bigger, faster-settling flocs. The example also reports the Reynolds
number to confirm both particles are safely in the creeping-flow regime where Stokes' law holds.

Run it directly (``python examples/clarifier_particle_settling.py``);
:func:`settling_times` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import stokes_settling_velocity
from anvilate.units import Quantity

PARTICLE_DENSITY = Quantity.parse("2650 kg/m**3")  # quartz
WATER_DENSITY = Quantity.parse("1000 kg/m**3")
WATER_VISCOSITY = Quantity.parse("0.001 Pa*s")
TANK_DEPTH = Quantity.parse("2 m")


def _settle(diameter: Quantity) -> dict[str, float]:
    velocity = stokes_settling_velocity(
        particle_diameter=diameter,
        particle_density=PARTICLE_DENSITY,
        fluid_density=WATER_DENSITY,
        fluid_viscosity=WATER_VISCOSITY,
    )
    v = velocity.to("m/s").magnitude
    d = diameter.to("m").magnitude
    reynolds = WATER_DENSITY.to("kg/m**3").magnitude * v * d / WATER_VISCOSITY.to("Pa*s").magnitude
    return {
        "velocity_mm_s": velocity.to("mm/s").magnitude,
        "settle_minutes": TANK_DEPTH.to("m").magnitude / v / 60.0,
        "reynolds": reynolds,
    }


def settling_times() -> dict[str, dict[str, float]]:
    """Return the settling velocity, time, and Reynolds number for sand and silt."""
    return {
        "sand_100um": _settle(Quantity.parse("100 um")),
        "silt_10um": _settle(Quantity.parse("10 um")),
    }


def main() -> None:
    r = settling_times()
    for label, key in (("100 µm sand", "sand_100um"), ("10 µm silt", "silt_10um")):
        s = r[key]
        print(
            f"{label:12s}: {s['velocity_mm_s']:.3f} mm/s, "
            f"settles 2 m in {s['settle_minutes']:.0f} min (Re {s['reynolds']:.2g})"
        )
    ratio = r["silt_10um"]["settle_minutes"] / r["sand_100um"]["settle_minutes"]
    print(
        f"  -> the 10x smaller silt settles {ratio:.0f}x slower (the d^2 law); fines size the tank"
    )


if __name__ == "__main__":
    main()
