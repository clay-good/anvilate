"""Worked example: setting an LED's operating point with the Shockley diode equation.

A diode's current climbs exponentially with its forward voltage, so its operating point can't be set
by voltage alone — a few tens of millivolts swing the current tenfold. Instead the current is fixed
externally (by a series resistor) and the diode settles at whatever forward voltage passes it. This
example uses the Shockley equation both ways: what voltage a target current needs, and how sharply
the current responds to small voltage changes around it.

The diode is a silicon junction (saturation current 1 pA, ideality factor 1) at room temperature
(300 K), where the thermal voltage is about 25.9 mV. To pass 1 mA it needs about 0.536 V — the
familiar sub-volt forward drop. Nudging the drive to 0.6 V does not raise the current a little but
to about 12 mA, a twelvefold jump, which is exactly why a bare diode cannot be current-controlled by
voltage and needs a ballast resistor. The example reports the thermal voltage, the forward voltage
for 1 mA, and the current that flows at 0.6 V.

Run it directly (``python examples/led_operating_point.py``);
:func:`operating_point` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import diode_current, diode_voltage, thermal_voltage
from anvilate.units import Quantity

SATURATION_CURRENT = Quantity.parse("1 pA")
TEMPERATURE = Quantity(magnitude=300.0, unit="K")
TARGET_CURRENT = Quantity.parse("1 mA")
OVERDRIVE_VOLTAGE = Quantity.parse("0.6 V")


def operating_point() -> dict[str, float]:
    """Return the thermal voltage, the forward voltage for 1 mA, and the current at 0.6 V."""
    v_t = thermal_voltage(temperature=TEMPERATURE)
    forward_voltage = diode_voltage(
        current=TARGET_CURRENT, saturation_current=SATURATION_CURRENT, temperature=TEMPERATURE
    )
    current_at_overdrive = diode_current(
        saturation_current=SATURATION_CURRENT, voltage=OVERDRIVE_VOLTAGE, temperature=TEMPERATURE
    )
    return {
        "thermal_voltage_mv": v_t.to("mV").magnitude,
        "forward_voltage_for_1ma_v": forward_voltage.to("V").magnitude,
        "current_at_0p6v_ma": current_at_overdrive.to("mA").magnitude,
    }


def main() -> None:
    d = operating_point()
    print(f"thermal voltage at 300 K: {d['thermal_voltage_mv']:.1f} mV")
    print(f"forward voltage for 1 mA: {d['forward_voltage_for_1ma_v']:.3f} V")
    print(f"current at 0.6 V: {d['current_at_0p6v_ma']:.1f} mA")


if __name__ == "__main__":
    main()
