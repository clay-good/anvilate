"""Worked example: the thrust on a solar sail at Earth's distance from the Sun.

Sunlight carries momentum, so it pushes on a sail — feebly per square metre, but enough to move a
large, reflective sail with no propellant at all. The photon momentum sets the scale, the radiation
pressure is that momentum flux, and multiplying by the sail area gives the usable thrust.

In full sunlight (the solar constant, 1361 W/m^2), a single 500 nm photon carries about 1.3e-27
kg·m/s of momentum. A perfectly reflecting surface feels a radiation pressure of about 9.1
micropascals — twice what an absorber feels, because it also recoils the reflected light. A 100 m^2
reflective sail therefore gets about 0.9 mN of thrust: tiny, but relentless and free. This example
reports the photon momentum, the radiation pressure on a mirror, and the force on the sail.

Run it directly (``python examples/solar_sail_thrust.py``);
:func:`solar_sail_thrust` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    photon_momentum,
    radiation_force,
    radiation_pressure_from_intensity,
)
from anvilate.units import Quantity

SOLAR_CONSTANT = Quantity(magnitude=1361.0, unit="W/m**2")
SAIL_AREA = Quantity(magnitude=100.0, unit="m**2")
WAVELENGTH = Quantity(magnitude=500e-9, unit="m")
REFLECTIVITY = 1.0  # perfect mirror


def solar_sail_thrust() -> dict[str, float]:
    """Return the photon momentum, the mirror radiation pressure, and the sail force."""
    momentum = photon_momentum(wavelength=WAVELENGTH)
    pressure = radiation_pressure_from_intensity(
        intensity=SOLAR_CONSTANT, reflectivity=REFLECTIVITY
    )
    force = radiation_force(intensity=SOLAR_CONSTANT, area=SAIL_AREA, reflectivity=REFLECTIVITY)
    return {
        "photon_momentum_kg_m_s": momentum.to("kg*m/s").magnitude,
        "radiation_pressure_upa": pressure.to("Pa").magnitude * 1e6,
        "sail_force_mn": force.to("N").magnitude * 1e3,
    }


def main() -> None:
    d = solar_sail_thrust()
    print(f"photon momentum (500 nm): {d['photon_momentum_kg_m_s']:.3e} kg m/s")
    print(f"radiation pressure (mirror): {d['radiation_pressure_upa']:.2f} uPa")
    print(f"force on 100 m^2 sail: {d['sail_force_mn']:.2f} mN")


if __name__ == "__main__":
    main()
