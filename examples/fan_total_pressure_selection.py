"""Worked example: the pressure a supply fan actually has to make.

A fan is not selected against the resistance of the ductwork alone. It has to supply two pressures:
the static pressure that forces air through the filters, coils, and duct friction, and the velocity
pressure that carries the air's kinetic energy out the end — and a fan curve is drawn against their
sum, the fan total pressure Pt = Ps + Pv.

This example takes a supply system with 250 Pa of static resistance moving standard air (1.2 kg/m³)
at a 10 m/s duct velocity. The velocity pressure is the dynamic pressure ½·ρ·V² = 60 Pa, so the fan
total pressure is 250 + 60 = 310 Pa — the number to read a fan curve at, not the 250 Pa static.
The example also closes the loop the other way: fed that same 60 Pa back through the pitot relation
√(2·Δp/ρ) recovers the 10 m/s, the measurement a balancing technician makes with a pitot tube in
the running duct. The lesson is that velocity pressure is not a rounding term to drop: on a
high-velocity system it is a real slice of the fan's duty, and the bridge between the air speed
in the duct and the pressure the fan is rated for.

Run it directly (``python examples/fan_total_pressure_selection.py``);
:func:`fan_duty` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import dynamic_pressure, fan_total_pressure, pitot_velocity
from anvilate.units import Quantity

STATIC_PRESSURE = Quantity.parse("250 Pa")
DUCT_VELOCITY = Quantity.parse("10 m/s")
AIR_DENSITY = Quantity.parse("1.2 kg/m**3")


def fan_duty() -> dict[str, float]:
    """Return the velocity pressure, the fan total pressure, and the pitot-recovered velocity."""
    velocity_pressure = dynamic_pressure(velocity=DUCT_VELOCITY, density=AIR_DENSITY)
    total = fan_total_pressure(static_pressure=STATIC_PRESSURE, velocity_pressure=velocity_pressure)
    recovered = pitot_velocity(dynamic_pressure=velocity_pressure, density=AIR_DENSITY)
    return {
        "velocity_pressure_pa": velocity_pressure.to("Pa").magnitude,
        "fan_total_pressure_pa": total.to("Pa").magnitude,
        "recovered_velocity_ms": recovered.to("m/s").magnitude,
    }


def main() -> None:
    d = fan_duty()
    print(f"static pressure : {STATIC_PRESSURE.to('Pa').magnitude:.0f} Pa")
    print(f"velocity pressure (1/2 rho V^2) : {d['velocity_pressure_pa']:.0f} Pa")
    print(f"fan total pressure : {d['fan_total_pressure_pa']:.0f} Pa (read the fan curve here)")
    print(f"pitot recovers velocity : {d['recovered_velocity_ms']:.1f} m/s (round-trip)")
    print("  -> velocity pressure is a real slice of the fan duty, not a term to drop")


if __name__ == "__main__":
    main()
