"""Worked example: why a rocket engine makes more thrust in space — the pressure term grows.

A rocket engine's thrust has two parts. Most of it is momentum: propellant leaves the nozzle at high
speed, and its reaction pushes the vehicle forward. A smaller part is pressure thrust — if the
nozzle exit pressure does not exactly match the outside air, the mismatch acts over the exit area as
an extra (or reduced) push. At sea level the atmosphere pushes back on the exit plane and eats into
the thrust; in vacuum there is nothing pushing back, so the full exit pressure becomes forward push
and the engine gets stronger the higher it climbs. That is why first-stage nozzles are a compromise
and upper stages, which only ever fire in near-vacuum, carry huge bells.

This example fires an engine with 3000 K chamber gas at 5 MPa (γ = 1.2, gas constant 350 J/kg·K)
through a nozzle that expands to 0.1 MPa over a 0.3 m² exit, flowing 100 kg/s of propellant. The
ideal exhaust velocity works out to about 2457 m/s. At sea level (0.1 MPa ambient) the nozzle is
perfectly expanded, so thrust is pure momentum: about 246 kN. Take the same engine to vacuum and the
pressure term (0.1 MPa over 0.3 m²) adds 30 kN, lifting thrust to about 276 kN — and the specific
impulse rises with it from about 251 s to 281 s. The example reports the exhaust velocity, the sea-
level and vacuum thrust, and the sea-level specific impulse, so the altitude gain is explicit.

Run it directly (``python examples/rocket_engine_thrust.py``);
:func:`engine_performance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    rocket_exhaust_velocity,
    rocket_specific_impulse,
    rocket_thrust,
)
from anvilate.units import Quantity

CHAMBER_TEMPERATURE = Quantity.parse("3000 K")
CHAMBER_PRESSURE = Quantity.parse("5 MPa")
EXIT_PRESSURE = Quantity.parse("0.1 MPa")
SPECIFIC_GAS_CONSTANT = Quantity.parse("350 J/(kg*K)")
HEAT_CAPACITY_RATIO = 1.2
MASS_FLOW_RATE = Quantity.parse("100 kg/s")
EXIT_AREA = Quantity.parse("0.3 m**2")
SEA_LEVEL_PRESSURE = Quantity.parse("0.1 MPa")
VACUUM_PRESSURE = Quantity.parse("0 Pa")


def engine_performance() -> dict[str, float]:
    """Return the exhaust velocity, sea-level and vacuum thrust, and sea-level specific impulse."""
    v_e = rocket_exhaust_velocity(
        chamber_temperature=CHAMBER_TEMPERATURE,
        chamber_pressure=CHAMBER_PRESSURE,
        exit_pressure=EXIT_PRESSURE,
        specific_gas_constant=SPECIFIC_GAS_CONSTANT,
        heat_capacity_ratio=HEAT_CAPACITY_RATIO,
    )
    thrust_sea = rocket_thrust(
        mass_flow_rate=MASS_FLOW_RATE,
        exhaust_velocity=v_e,
        exit_pressure=EXIT_PRESSURE,
        ambient_pressure=SEA_LEVEL_PRESSURE,
        exit_area=EXIT_AREA,
    )
    thrust_vac = rocket_thrust(
        mass_flow_rate=MASS_FLOW_RATE,
        exhaust_velocity=v_e,
        exit_pressure=EXIT_PRESSURE,
        ambient_pressure=VACUUM_PRESSURE,
        exit_area=EXIT_AREA,
    )
    isp_sea = rocket_specific_impulse(thrust=thrust_sea, mass_flow_rate=MASS_FLOW_RATE)
    return {
        "exhaust_velocity_m_s": v_e.to("m/s").magnitude,
        "thrust_sea_level_kn": thrust_sea.to("kN").magnitude,
        "thrust_vacuum_kn": thrust_vac.to("kN").magnitude,
        "specific_impulse_sea_s": isp_sea.to("s").magnitude,
    }


def main() -> None:
    d = engine_performance()
    print(f"ideal exhaust velocity: {d['exhaust_velocity_m_s']:.0f} m/s")
    print(f"thrust at sea level: {d['thrust_sea_level_kn']:.0f} kN")
    print(
        f"thrust in vacuum: {d['thrust_vacuum_kn']:.0f} kN "
        f"-> +{d['thrust_vacuum_kn'] - d['thrust_sea_level_kn']:.0f} kN from the pressure term"
    )
    print(f"specific impulse (sea level): {d['specific_impulse_sea_s']:.0f} s")


if __name__ == "__main__":
    main()
