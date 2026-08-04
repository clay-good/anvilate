"""Worked example: sizing a relief valve, where the flow refuses to go any faster.

A pressure-relief valve has one job: pass enough gas to keep a vessel from over-pressurizing in an
upset. Sizing it turns on a quirk of compressible flow — once the pressure ratio across the valve
falls below the critical value (about 0.528 for air), the flow at the throat reaches the speed of
sound and *chokes*. Past that point, opening up the downstream side does nothing; the mass flow is
capped by the upstream vessel conditions alone. That is actually a gift to the designer: the
worst-case discharge is a single number that doesn't depend on the messy downstream piping. This
example takes a vessel at 10 bar and 300 K venting air through a 3 cm² nozzle, confirms the flow is
choked, and computes the certain-to-be-relieved mass flow the valve delivers — the number checked
against the vessel's required relief capacity.

Run it directly (``python examples/relief_valve_choked_flow.py``);
:func:`relief_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import choked_mass_flow_rate, critical_pressure_ratio
from anvilate.units import Quantity

VESSEL_PRESSURE = Quantity.parse("1000 kPa")  # 10 bar (absolute)
VESSEL_TEMPERATURE = Quantity.parse("300 K")
ATMOSPHERIC = Quantity.parse("101.325 kPa")
ORIFICE_AREA = Quantity.parse("3e-4 m**2")  # 3 cm^2 nozzle
DISCHARGE_COEFFICIENT = 0.85
HEAT_CAPACITY_RATIO = 1.4  # air
GAS_CONSTANT = Quantity.parse("287 J/(kg*K)")


def relief_capacity() -> dict[str, float]:
    """Return the critical and actual pressure ratios and the choked mass flow (kg/s)."""
    critical = critical_pressure_ratio(heat_capacity_ratio=HEAT_CAPACITY_RATIO)
    actual = ATMOSPHERIC.to("Pa").magnitude / VESSEL_PRESSURE.to("Pa").magnitude
    mass_flow = (
        choked_mass_flow_rate(
            stagnation_pressure=VESSEL_PRESSURE,
            stagnation_temperature=VESSEL_TEMPERATURE,
            orifice_area=ORIFICE_AREA,
            discharge_coefficient=DISCHARGE_COEFFICIENT,
            heat_capacity_ratio=HEAT_CAPACITY_RATIO,
            specific_gas_constant=GAS_CONSTANT,
        )
        .to("kg/s")
        .magnitude
    )
    return {
        "critical_ratio": critical,
        "actual_ratio": actual,
        "is_choked": actual < critical,
        "mass_flow_kgs": mass_flow,
    }


def main() -> None:
    r = relief_capacity()
    choked = "choked" if r["is_choked"] else "subsonic"
    print(f"critical pressure ratio : {r['critical_ratio']:.3f}")
    print(f"actual ratio (atm/vessel) : {r['actual_ratio']:.3f}  -> {choked}")
    print(f"relieved mass flow      : {r['mass_flow_kgs'] * 1000:.0f} g/s (capped by upstream)")
    print(
        "  -> once choked, the downstream piping can't change the capacity — a clean design number"
    )


if __name__ == "__main__":
    main()
