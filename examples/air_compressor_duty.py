"""Worked example: why an air compressor takes more power — and runs hot — than the ideal.

Sizing a compressor is not one number but a bracket. Squeeze air slowly with perfect cooling and
the work is the isothermal minimum; squeeze it fast with no cooling and the air heats up and the
work is the adiabatic maximum. A real single-stage machine sits between them, closer to
adiabatic, so the isothermal figure alone undersizes the motor by a third. This example
compresses 1 m³/s of atmospheric air at a 7:1 ratio and shows both bounds — and the reason
high-ratio compressors are staged: taken from 15 °C to seven atmospheres in one shot, the air
leaves near 230 °C, far too hot for the oil and the downstream pipe, so an intercooler has to
pull the heat out between stages.

Run it directly (``python examples/air_compressor_duty.py``);
:func:`compressor_duty` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    adiabatic_compression_power,
    adiabatic_discharge_temperature,
    isothermal_compression_power,
)
from anvilate.units import Quantity

INLET_FLOW = Quantity.parse("1 m**3/s")
INLET_PRESSURE = Quantity.parse("101.325 kPa")
INLET_TEMPERATURE = Quantity.parse("288.15 K")  # 15 deg C
PRESSURE_RATIO = 7.0
HEAT_CAPACITY_RATIO = 1.4  # air


def compressor_duty() -> dict[str, float]:
    """Return the isothermal and adiabatic power (kW) and the adiabatic discharge (deg C)."""
    isothermal = (
        isothermal_compression_power(
            volumetric_flow=INLET_FLOW,
            inlet_pressure=INLET_PRESSURE,
            pressure_ratio=PRESSURE_RATIO,
        )
        .to("kW")
        .magnitude
    )
    adiabatic = (
        adiabatic_compression_power(
            volumetric_flow=INLET_FLOW,
            inlet_pressure=INLET_PRESSURE,
            pressure_ratio=PRESSURE_RATIO,
            heat_capacity_ratio=HEAT_CAPACITY_RATIO,
        )
        .to("kW")
        .magnitude
    )
    discharge = (
        adiabatic_discharge_temperature(
            inlet_temperature=INLET_TEMPERATURE,
            pressure_ratio=PRESSURE_RATIO,
            heat_capacity_ratio=HEAT_CAPACITY_RATIO,
        )
        .to("degC")
        .magnitude
    )
    return {
        "isothermal_kw": isothermal,
        "adiabatic_kw": adiabatic,
        "adiabatic_over_isothermal": adiabatic / isothermal,
        "discharge_degc": discharge,
    }


def main() -> None:
    d = compressor_duty()
    print(f"isothermal (cooled) power  : {d['isothermal_kw']:.0f} kW  (the ideal minimum)")
    over = d["adiabatic_over_isothermal"]
    print(f"adiabatic (uncooled) power : {d['adiabatic_kw']:.0f} kW  ({over:.0%} of isothermal)")
    print(f"adiabatic discharge temp   : {d['discharge_degc']:.0f} deg C from 15 deg C inlet")
    print("  -> real duty sits near adiabatic; the heat is why high ratios are staged/intercooled")


if __name__ == "__main__":
    main()
