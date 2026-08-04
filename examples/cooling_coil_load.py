"""Worked example: sizing a cooling coil, and the latent load a temperature drop hides.

A cooling coil does two jobs at once: it lowers the air temperature (sensible cooling) and it
wrings water out of it (latent cooling), and a coil sized on temperature alone will be too small.
The honest way to size it is by enthalpy, which rolls both into one number — the coil's total load
is simply the air mass flow times the drop in moist-air enthalpy across it. This example takes
1.2 kg/s of dry air entering warm and humid (28 °C, 60% RH) and leaving cool and drier (14 °C,
90% RH) and computes the total load, then splits out how much of it is the temperature change
alone. The latent share — the heat of condensing the moisture out — is a large fraction that a
dry-bulb calculation would have missed entirely, which is why humid climates need so much more
cooling capacity than the thermometer suggests.

Run it directly (``python examples/cooling_coil_load.py``);
:func:`coil_load` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    cooling_coil_load,
    humidity_ratio,
    moist_air_enthalpy,
    saturation_vapor_pressure,
)
from anvilate.units import Quantity

AIR_MASS_FLOW = Quantity.parse("1.2 kg/s")  # dry air
TOTAL_PRESSURE = Quantity.parse("101325 Pa")
INLET_TEMP = Quantity.parse("301.15 K")  # 28 deg C
INLET_RH = 0.60
OUTLET_TEMP = Quantity.parse("287.15 K")  # 14 deg C
OUTLET_RH = 0.90


def _state(temperature: Quantity, rh: float) -> tuple[Quantity, float]:
    p_ws = saturation_vapor_pressure(temperature=temperature)
    p_w = Quantity(magnitude=rh * p_ws.to("Pa").magnitude, unit="Pa")
    w = humidity_ratio(vapor_pressure=p_w, total_pressure=TOTAL_PRESSURE)
    return moist_air_enthalpy(temperature=temperature, humidity_ratio=w), w


def coil_load() -> dict[str, float]:
    """Return the total load (kW), the sensible-only load (kW), and the latent fraction."""
    h_in, w_in = _state(INLET_TEMP, INLET_RH)
    h_out, _ = _state(OUTLET_TEMP, OUTLET_RH)
    total = (
        cooling_coil_load(dry_air_mass_flow=AIR_MASS_FLOW, enthalpy_in=h_in, enthalpy_out=h_out)
        .to("kW")
        .magnitude
    )
    # Sensible-only: hold the humidity ratio at the inlet value across the temperature drop.
    h_out_sensible = moist_air_enthalpy(temperature=OUTLET_TEMP, humidity_ratio=w_in)
    sensible = (
        cooling_coil_load(
            dry_air_mass_flow=AIR_MASS_FLOW, enthalpy_in=h_in, enthalpy_out=h_out_sensible
        )
        .to("kW")
        .magnitude
    )
    return {
        "total_kw": total,
        "sensible_kw": sensible,
        "latent_fraction": (total - sensible) / total,
    }


def main() -> None:
    c = coil_load()
    print(f"total cooling load : {c['total_kw']:.1f} kW (sensible + latent)")
    print(f"sensible only      : {c['sensible_kw']:.1f} kW (the temperature drop)")
    print(f"  -> {c['latent_fraction']:.0%} of the load is latent — drying the air, not cooling it")


if __name__ == "__main__":
    main()
