"""Worked example: a 2.4 GHz Wi-Fi link budget — received power and maximum range.

Whether a wireless link works comes down to one comparison: does the power the receiver captures
stay above the power it needs to decode? The Friis equation gives the first, from the transmit
power, the two antenna gains, and how the signal spreads over distance and wavelength. Turning it
around gives the reach — how far a link holds before the signal drops below the receiver's floor.

This example is a 2.4 GHz link (wavelength about 0.125 m) with a 100 mW transmitter and modest 1.64
(2.15 dBi) antennas at both ends. Over 100 m of clear line of sight the free-space path loss is
about 80 dB, and the receiver captures about 2.7e-9 W — roughly -55.8 dBm, comfortably above a
-85 dBm Wi-Fi sensitivity. Solving for that -85 dBm floor instead, the link reaches about 2.9 km in
free space (real indoor range is far shorter once walls and interference are added). The example
reports the received power at 100 m and the free-space range to a -85 dBm receiver.

Run it directly (``python examples/wifi_link_budget.py``);
:func:`link_budget` is also exercised in the test suite.
"""

from __future__ import annotations

from math import log10

from anvilate.analysis import max_line_of_sight_range, received_power
from anvilate.units import Quantity

WAVELENGTH = Quantity.parse("0.12491 m")  # 2.4 GHz
TRANSMIT_POWER = Quantity.parse("100 mW")
TX_GAIN = 1.64  # ~2.15 dBi dipole
RX_GAIN = 1.64
RANGE = Quantity.parse("100 m")
RECEIVER_SENSITIVITY = Quantity(magnitude=10 ** (-85 / 10) * 1e-3, unit="W")  # -85 dBm


def link_budget() -> dict[str, float]:
    """Return the received power at 100 m (dBm) and the free-space range to a -85 dBm receiver."""
    p_r = received_power(
        transmit_power=TRANSMIT_POWER,
        transmit_gain=TX_GAIN,
        receive_gain=RX_GAIN,
        distance=RANGE,
        wavelength=WAVELENGTH,
    )
    p_r_dbm = 10 * log10(p_r.to("W").magnitude / 1e-3)
    reach = max_line_of_sight_range(
        transmit_power=TRANSMIT_POWER,
        transmit_gain=TX_GAIN,
        receive_gain=RX_GAIN,
        receiver_sensitivity=RECEIVER_SENSITIVITY,
        wavelength=WAVELENGTH,
    )
    return {
        "received_power_dbm_at_100m": p_r_dbm,
        "max_range_km": reach.to("km").magnitude,
    }


def main() -> None:
    d = link_budget()
    print(f"received power at 100 m: {d['received_power_dbm_at_100m']:.1f} dBm")
    print(f"free-space range to -85 dBm receiver: {d['max_range_km']:.1f} km")


if __name__ == "__main__":
    main()
