"""Worked example: energy methods on a roller-coaster car.

Energy methods sidestep force-versus-time bookkeeping: count the kinetic energy a moving car holds,
the potential energy stored by lifting it, and the work a force does, and conservation of energy
ties them together.

A 1,000 kg car moving at 20 m/s carries 200 kJ of kinetic energy. Lifting it 10 m up the first hill
stores about 98 kJ of gravitational potential energy — energy that returns as speed on the way down.
A constant 500 N drive force pushing it 3 m along the track does 1.5 kJ of work, which by the
work-energy theorem shows up as a change in its kinetic energy. This example reports the kinetic
energy, the potential energy at the top of the hill, and the work the drive force does.

Run it directly (``python examples/roller_coaster_energy.py``);
:func:`coaster_energy` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    gravitational_potential_energy,
    kinetic_energy,
    work_done,
)
from anvilate.units import Quantity

CAR_MASS = Quantity(magnitude=1000.0, unit="kg")
SPEED = Quantity(magnitude=20.0, unit="m/s")
HILL_HEIGHT = Quantity(magnitude=10.0, unit="m")
DRIVE_FORCE = Quantity(magnitude=500.0, unit="N")
PUSH_DISTANCE = Quantity(magnitude=3.0, unit="m")


def coaster_energy() -> dict[str, float]:
    """Return the kinetic energy, the hilltop potential energy, and the drive work."""
    ke = kinetic_energy(mass=CAR_MASS, velocity=SPEED)
    pe = gravitational_potential_energy(mass=CAR_MASS, height=HILL_HEIGHT)
    work = work_done(force=DRIVE_FORCE, distance=PUSH_DISTANCE)
    return {
        "kinetic_energy_kj": ke.to("J").magnitude / 1000.0,
        "potential_energy_kj": pe.to("J").magnitude / 1000.0,
        "drive_work_kj": work.to("J").magnitude / 1000.0,
    }


def main() -> None:
    d = coaster_energy()
    print(f"kinetic energy at 20 m/s: {d['kinetic_energy_kj']:.0f} kJ")
    print(f"potential energy at 10 m: {d['potential_energy_kj']:.1f} kJ")
    print(f"work by a 500 N drive over 3 m: {d['drive_work_kj']:.1f} kJ")


if __name__ == "__main__":
    main()
