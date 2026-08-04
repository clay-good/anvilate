"""Worked example: why a high-ratio compressor is built in stages, not one big cylinder.

Compressing air to a high pressure ratio in a single stroke is doubly punishing: the work climbs
fast, and the discharge gets ferociously hot — air taken from atmospheric to 49:1 in one shot
would leave near 600 °C, past what the cylinder oil survives. Splitting the job into stages with
an intercooler between them fixes both. Cooling the gas back to inlet temperature before each
stage means every stage starts cold, so the discharge temperature resets to a modest per-stage
rise, and the total work drops toward the isothermal ideal. This example compresses 1 m³/s of air
at an overall 49:1 ratio in one, two, and three stages and shows the power falling and the
per-stage discharge temperature dropping with each split. The staging is not an efficiency luxury;
past a pressure ratio of a few, it is what keeps the machine from cooking itself.

Run it directly (``python examples/multistage_compressor_staging.py``);
:func:`staging_comparison` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    adiabatic_discharge_temperature,
    multistage_compression_power,
    optimal_stage_pressure_ratio,
)
from anvilate.units import Quantity

INLET_FLOW = Quantity.parse("1 m**3/s")
INLET_PRESSURE = Quantity.parse("101.325 kPa")
INLET_TEMPERATURE = Quantity.parse("288.15 K")  # 15 deg C
OVERALL_RATIO = 49.0
HEAT_CAPACITY_RATIO = 1.4  # air


def staging_comparison() -> dict[str, float]:
    """Return the power (kW) and per-stage discharge temp (deg C) for 1, 2, and 3 stages."""
    out: dict[str, float] = {}
    for n in (1, 2, 3):
        power = (
            multistage_compression_power(
                volumetric_flow=INLET_FLOW,
                inlet_pressure=INLET_PRESSURE,
                overall_pressure_ratio=OVERALL_RATIO,
                stages=n,
                heat_capacity_ratio=HEAT_CAPACITY_RATIO,
            )
            .to("kW")
            .magnitude
        )
        stage_ratio = optimal_stage_pressure_ratio(overall_pressure_ratio=OVERALL_RATIO, stages=n)
        discharge = (
            adiabatic_discharge_temperature(
                inlet_temperature=INLET_TEMPERATURE,
                pressure_ratio=stage_ratio,
                heat_capacity_ratio=HEAT_CAPACITY_RATIO,
            )
            .to("degC")
            .magnitude
        )
        out[f"power_{n}stage_kw"] = power
        out[f"discharge_{n}stage_degc"] = discharge
    return out


def main() -> None:
    s = staging_comparison()
    for n in (1, 2, 3):
        power = s[f"power_{n}stage_kw"]
        temp = s[f"discharge_{n}stage_degc"]
        print(f"{n} stage(s) : {power:5.0f} kW,  per-stage discharge {temp:4.0f} deg C")
    saved = (1 - s["power_3stage_kw"] / s["power_1stage_kw"]) * 100
    print(
        f"  -> 3 stages cut the power {saved:.0f}% and the discharge heat from ~600 to ~140 deg C"
    )


if __name__ == "__main__":
    main()
