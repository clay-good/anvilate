"""Worked example: the Johnson-noise floor of an amplifier front end.

Every resistor generates thermal noise, and that noise sets the smallest signal an amplifier or
sensor can resolve. Designing a low-noise front end means knowing three things: the noise voltage a
source resistance contributes, the fundamental noise power floor (independent of R), and how cooling
or narrowing the bandwidth helps. This example works them for a room-temperature front end.

A 1 kohm source resistance at 290 K, measured over a 10 kHz bandwidth, contributes about 0.40
microvolts rms of Johnson noise — the floor a signal must clear. The available noise power over that
band is about 4e-17 W, or -134 dBm, which is the -174 dBm/Hz reference floor plus 40 dB for the
10 kHz bandwidth. Cooling the same resistor to 77 K (liquid nitrogen) drops the noise voltage to
about 0.21 microvolts — nearly halving it — which is why sensitive front ends are cooled. It reports
the room-temperature noise voltage and power and the cooled noise voltage.

Run it directly (``python examples/amplifier_noise_floor.py``);
:func:`noise_floor` is also exercised in the test suite.
"""

from __future__ import annotations

from math import log10

from anvilate.analysis import johnson_noise_power, johnson_noise_voltage
from anvilate.units import Quantity

SOURCE_RESISTANCE = Quantity.parse("1 kohm")
ROOM_TEMPERATURE = Quantity(magnitude=290.0, unit="K")
CRYO_TEMPERATURE = Quantity(magnitude=77.0, unit="K")
BANDWIDTH = Quantity(magnitude=1e4, unit="Hz")


def noise_floor() -> dict[str, float]:
    """Return the room-temp noise voltage, the noise power (dBm), and the 77 K noise voltage."""
    v_room = johnson_noise_voltage(
        resistance=SOURCE_RESISTANCE, temperature=ROOM_TEMPERATURE, bandwidth=BANDWIDTH
    )
    power = johnson_noise_power(temperature=ROOM_TEMPERATURE, bandwidth=BANDWIDTH)
    v_cryo = johnson_noise_voltage(
        resistance=SOURCE_RESISTANCE, temperature=CRYO_TEMPERATURE, bandwidth=BANDWIDTH
    )
    return {
        "room_noise_voltage_uv": v_room.to("uV").magnitude,
        "noise_power_dbm": 10 * log10(power.to("W").magnitude / 1e-3),
        "cryo_noise_voltage_uv": v_cryo.to("uV").magnitude,
    }


def main() -> None:
    d = noise_floor()
    print(f"noise voltage at 290 K: {d['room_noise_voltage_uv']:.2f} uV")
    print(f"available noise power: {d['noise_power_dbm']:.0f} dBm")
    print(f"noise voltage cooled to 77 K: {d['cryo_noise_voltage_uv']:.2f} uV")


if __name__ == "__main__":
    main()
