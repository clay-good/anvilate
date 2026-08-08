"""Worked example: momentum and impulse in a car crash.

Momentum methods explain why a crumple zone saves lives: a car carries momentum, stopping it takes
an impulse, and the same impulse spread over a longer time means a smaller force. This example works
the momentum, an impulse, and the crash force for two stopping times.

A 1,000 kg car at 20 m/s carries 20,000 kg·m/s of momentum. A steady 500 N thrust for 3 s delivers
an impulse of 1,500 N·s. Stopping the car from 20 m/s in a rigid 0.1 s crash needs an average force
of 200 kN — brutal — while a crumple zone stretching the stop to 0.5 s cuts that to 40 kN, a fifth
as much. This example reports the car's momentum, the 3 s impulse, and the crash force for a 0.1 s
stop.

Run it directly (``python examples/car_crash_impulse.py``);
:func:`crash_dynamics` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    average_impact_force,
    impulse,
    linear_momentum,
)
from anvilate.units import Quantity

CAR_MASS = Quantity(magnitude=1000.0, unit="kg")
SPEED = Quantity(magnitude=20.0, unit="m/s")
THRUST = Quantity(magnitude=500.0, unit="N")
THRUST_TIME = Quantity(magnitude=3.0, unit="s")
CRASH_TIME = Quantity(magnitude=0.1, unit="s")


def crash_dynamics() -> dict[str, float]:
    """Return the car's momentum, a 3 s impulse, and the crash force for a 0.1 s stop."""
    p = linear_momentum(mass=CAR_MASS, velocity=SPEED)
    j = impulse(force=THRUST, time_interval=THRUST_TIME)
    force = average_impact_force(mass=CAR_MASS, velocity_change=SPEED, time_interval=CRASH_TIME)
    return {
        "momentum_kg_m_s": p.to("kg*m/s").magnitude,
        "impulse_n_s": j.to("N*s").magnitude,
        "crash_force_kn": force.to("N").magnitude / 1000.0,
    }


def main() -> None:
    d = crash_dynamics()
    print(f"car momentum at 20 m/s: {d['momentum_kg_m_s']:.0f} kg m/s")
    print(f"impulse of 500 N over 3 s: {d['impulse_n_s']:.0f} N s")
    print(f"average crash force (0.1 s stop): {d['crash_force_kn']:.0f} kN")


if __name__ == "__main__":
    main()
