"""Worked example: the air condition a cooling coil actually sees, after mixing.

An air handler rarely cools the outdoor air it brings in. It cools a *mixture*: most of the air is
recirculated room return, and a minority fraction is fresh outdoor air blended in for ventilation.
The coil has to be sized for the mixed condition, and because mixing is adiabatic the mix is the
mass-weighted average of the two streams — the mixed point lies on the line between them on a
psychrometric chart, nearer the bigger flow.

This example blends 3 kg/s of cool, dry return air (24 °C, humidity ratio 0.010) with 1 kg/s of hot,
humid outdoor air (35 °C, 0.018) in a summer air handler. The mixed air comes out at 26.75 °C and a
humidity ratio of 0.012 — much closer to the return than to the outdoor air, because the return is
three times the flow. That mixed 26.75 °C / 0.012 condition, not the 35 °C outdoor air, is what the
cooling coil is sized to bring down to supply. The lesson is that the coil's design point
is set in the mixing box: get the outdoor fraction or the return condition wrong and the coil is
sized for a load that never arrives, or misses the one that does.

Run it directly (``python examples/ahu_mixed_air.py``);
:func:`mixed_air` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    adiabatic_mixing_humidity_ratio,
    adiabatic_mixing_temperature,
)
from anvilate.units import Quantity

RETURN_FLOW = Quantity.parse("3 kg/s")
RETURN_TEMPERATURE = Quantity(magnitude=24.0, unit="degC")
RETURN_HUMIDITY_RATIO = 0.010
OUTDOOR_FLOW = Quantity.parse("1 kg/s")
OUTDOOR_TEMPERATURE = Quantity(magnitude=35.0, unit="degC")
OUTDOOR_HUMIDITY_RATIO = 0.018


def mixed_air() -> dict[str, float]:
    """Return the mixed-air temperature (°C) and humidity ratio of the return/outdoor blend."""
    temperature = adiabatic_mixing_temperature(
        mass_flow_1=RETURN_FLOW,
        temperature_1=RETURN_TEMPERATURE,
        mass_flow_2=OUTDOOR_FLOW,
        temperature_2=OUTDOOR_TEMPERATURE,
    )
    humidity = adiabatic_mixing_humidity_ratio(
        mass_flow_1=RETURN_FLOW,
        humidity_ratio_1=RETURN_HUMIDITY_RATIO,
        mass_flow_2=OUTDOOR_FLOW,
        humidity_ratio_2=OUTDOOR_HUMIDITY_RATIO,
    )
    return {
        "mixed_temperature_c": temperature.to("degC").magnitude,
        "mixed_humidity_ratio": humidity,
    }


def main() -> None:
    m = mixed_air()
    print("return 24.0 C / 0.010  (3 kg/s)  +  outdoor 35.0 C / 0.018  (1 kg/s)")
    print(f"mixed air : {m['mixed_temperature_c']:.2f} C / {m['mixed_humidity_ratio']:.4f} kg/kg")
    print(
        "  -> the coil is sized for the mixed condition, not the outdoor air it never treats alone"
    )


if __name__ == "__main__":
    main()
