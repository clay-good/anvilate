"""Worked example: splitting a rocket engine's performance into chamber and nozzle.

A rocket engine's performance divides neatly in two: the combustion chamber sets the characteristic
velocity c*, and the nozzle sets the thrust coefficient C_F. Measuring thrust, chamber pressure, and
propellant flow on a test stand lets you pin a shortfall on one or the other.

An engine running at 7 MPa chamber pressure with a 0.01 m^2 throat flows 40 kg/s of propellant,
giving a characteristic velocity of 1,750 m/s — the chamber's figure of merit. It produces 100 kN of
thrust, so its thrust coefficient is about 1.43, a typical value for a moderately expanded nozzle.
Turned around, that coefficient and chamber pressure size the throat to deliver the 100 kN. This
example reports the characteristic velocity, the thrust coefficient, and the thrust the coefficient
reproduces.

Run it directly (``python examples/rocket_engine_performance.py``);
:func:`engine_performance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    characteristic_velocity,
    thrust_coefficient,
    thrust_from_coefficient,
)
from anvilate.units import Quantity

CHAMBER_PRESSURE = Quantity(magnitude=7e6, unit="Pa")
THROAT_AREA = Quantity(magnitude=0.01, unit="m**2")
MASS_FLOW_RATE = Quantity(magnitude=40.0, unit="kg/s")
THRUST = Quantity(magnitude=1e5, unit="N")


def engine_performance() -> dict[str, float]:
    """Return the characteristic velocity, the thrust coefficient, and the reproduced thrust."""
    c_star = characteristic_velocity(
        chamber_pressure=CHAMBER_PRESSURE,
        throat_area=THROAT_AREA,
        mass_flow_rate=MASS_FLOW_RATE,
    )
    c_f = thrust_coefficient(
        thrust=THRUST, chamber_pressure=CHAMBER_PRESSURE, throat_area=THROAT_AREA
    )
    thrust = thrust_from_coefficient(
        thrust_coefficient=c_f, chamber_pressure=CHAMBER_PRESSURE, throat_area=THROAT_AREA
    )
    return {
        "characteristic_velocity_m_s": c_star.to("m/s").magnitude,
        "thrust_coefficient": c_f,
        "thrust_kn": thrust.to("N").magnitude / 1000.0,
    }


def main() -> None:
    d = engine_performance()
    print(f"characteristic velocity c*: {d['characteristic_velocity_m_s']:.0f} m/s")
    print(f"thrust coefficient C_F: {d['thrust_coefficient']:.3f}")
    print(f"thrust from coefficient: {d['thrust_kn']:.0f} kN")


if __name__ == "__main__":
    main()
