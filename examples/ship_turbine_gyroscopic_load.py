"""Worked example: the bearing load a ship's turbine feels every time the ship turns.

A large rotor stores angular momentum along its spin axis, and that stored momentum fights any
attempt to swing the axis. On a ship, the main turbine spins about the fore-aft axis; when the ship
turns, the hull forces that axis to swing with it, and the rotor answers with a gyroscopic couple —
a moment at right angles to both the spin and the turn — that the turbine bearings and mounts must
carry. It is easy to overlook because it appears only during maneuvers, but for a fast, heavy rotor
it can be a large, sudden load, and it scales with rotor speed and with how sharply the ship turns.

This example takes a turbine rotor of 500 kg·m² polar moment of inertia spinning at 3000 rpm. Its
stored spin angular momentum is about 157000 N·m·s — a large reservoir. When the ship puts on a
steady turn of 6°/s (a brisk maneuver), the rotor is forced to precess at the same rate, and reacts
with a gyroscopic couple of about 16.4 kN·m on its bearings. Read the other way, a 16.4 kN·m moment
across the spin axis would precess it at exactly that 6°/s. The example reports the spin angular
momentum, the reaction moment during the turn, and the precession rate it corresponds to, so the
maneuvering bearing load is explicit.

Run it directly (``python examples/ship_turbine_gyroscopic_load.py``);
:func:`turbine_gyro_load` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    gyroscopic_precession_rate,
    gyroscopic_reaction_moment,
    gyroscopic_spin_angular_momentum,
)
from anvilate.units import Quantity

POLAR_MOMENT_OF_INERTIA = Quantity.parse("500 kg*m**2")
SPIN_SPEED = Quantity.parse("3000 rpm")
SHIP_TURN_RATE = Quantity.parse("6 deg/s")


def turbine_gyro_load() -> dict[str, float]:
    """Return the spin angular momentum, the reaction couple in a turn, and its precession rate."""
    momentum = gyroscopic_spin_angular_momentum(
        polar_moment_of_inertia=POLAR_MOMENT_OF_INERTIA, spin_speed=SPIN_SPEED
    )
    reaction = gyroscopic_reaction_moment(
        polar_moment_of_inertia=POLAR_MOMENT_OF_INERTIA,
        spin_speed=SPIN_SPEED,
        precession_rate=SHIP_TURN_RATE,
    )
    precession = gyroscopic_precession_rate(
        applied_moment=reaction,
        polar_moment_of_inertia=POLAR_MOMENT_OF_INERTIA,
        spin_speed=SPIN_SPEED,
    )
    return {
        "spin_angular_momentum_nms": momentum.to("N*m*s").magnitude,
        "reaction_moment_kn_m": reaction.to("kN*m").magnitude,
        "precession_rate_deg_s": precession.to("deg/s").magnitude,
    }


def main() -> None:
    d = turbine_gyro_load()
    print(f"spin angular momentum: {d['spin_angular_momentum_nms']:.0f} N*m*s")
    print(f"gyroscopic couple in a 6 deg/s turn: {d['reaction_moment_kn_m']:.1f} kN*m")
    print(
        f"that couple precesses the axis at {d['precession_rate_deg_s']:.1f} deg/s "
        f"-> matches the ship's turn"
    )


if __name__ == "__main__":
    main()
