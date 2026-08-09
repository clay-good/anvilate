"""Worked example: a Pt100 RTD and an NTC thermistor reading the same 60 °C.

RTDs and thermistors both turn temperature into resistance, but in opposite characters — and this
example makes the difference concrete by reading both at 60 °C. The Pt100 RTD climbs gently and
linearly to about 123 Ω; the 10 kΩ NTC thermistor plunges to about 2.5 kΩ. It then converts the
Pt100 resistance back to temperature to confirm the round-trip.

The takeaway a designer wants: the RTD moves ~0.385 Ω/°C — small, steady, and easy to linearize over
a wide span (why RTDs win on accuracy and range). The thermistor's resistance more than quartered
from its 25 °C value over the same 35 °C rise — huge sensitivity, but exponential and confined to a
narrow band. The choice is linearity-and-range (RTD) versus resolution-in-a-window (thermistor).

Run it directly (``python examples/temperature_sensor_pt100_vs_thermistor.py``);
:func:`sensor_readings` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rtd_resistance, rtd_temperature, thermistor_resistance
from anvilate.units import Quantity

MEASURED = Quantity.parse("333.15 K")  # 60 C
PT100_R0 = Quantity.parse("100 ohm")
PT100_T0 = Quantity.parse("273.15 K")  # 0 C
PT100_ALPHA = 0.00385  # /K, industrial platinum
NTC_R0 = Quantity.parse("10 kohm")
NTC_T0 = Quantity.parse("298.15 K")  # 25 C
NTC_BETA = Quantity.parse("3950 K")


def sensor_readings() -> dict[str, float]:
    """Return the Pt100 and thermistor resistances at 60 C, and the Pt100 temperature round-trip."""
    r_rtd = rtd_resistance(
        reference_resistance=PT100_R0,
        temperature_coefficient=PT100_ALPHA,
        temperature=MEASURED,
        reference_temperature=PT100_T0,
    )
    r_ntc = thermistor_resistance(
        reference_resistance=NTC_R0,
        beta_constant=NTC_BETA,
        temperature=MEASURED,
        reference_temperature=NTC_T0,
    )
    t_back = rtd_temperature(
        resistance=r_rtd,
        reference_resistance=PT100_R0,
        temperature_coefficient=PT100_ALPHA,
        reference_temperature=PT100_T0,
    )
    return {
        "pt100_ohm": r_rtd.to("ohm").magnitude,
        "thermistor_kohm": r_ntc.to("kohm").magnitude,
        "pt100_temperature_c": t_back.to("K").magnitude - 273.15,
    }


def main() -> None:
    s = sensor_readings()
    print("both sensors at 60 C:")
    print(f"  Pt100 RTD       : {s['pt100_ohm']:.1f} ohm (linear, gentle climb)")
    print(
        f"  NTC thermistor  : {s['thermistor_kohm']:.2f} kohm (from 10 kohm at 25 C — a big drop)"
    )
    print(f"  Pt100 round-trip: {s['pt100_temperature_c']:.1f} C (resistance back to temperature)")


if __name__ == "__main__":
    main()
