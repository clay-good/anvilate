"""Worked example: sizing the air receiver that keeps a tool from starving the line.

A compressor rated for the *average* air demand still can't cover a *burst* — a die grinder or a
blow-off that briefly draws far more than the machine makes. The receiver tank bridges that gap,
giving up stored air while its pressure sags, and the design question is whether it holds enough
to ride out the burst before the pressure falls below what the tools need. This example takes a
1 m³ receiver working between 800 and 600 kPa and asks how long it covers a 10 L/s net burst — a
few minutes — then turns the question around and sizes the tank a five-minute burst would require.
It is the pneumatic version of a battery: how much energy is stored, and how long will it last.

Run it directly (``python examples/air_receiver_sizing.py``);
:func:`receiver_sizing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import air_receiver_holdup_time, air_receiver_volume_for_demand
from anvilate.units import Quantity

RECEIVER_VOLUME = Quantity.parse("1 m**3")
MAX_PRESSURE = Quantity.parse("800 kPa")  # compressor cut-out
MIN_PRESSURE = Quantity.parse("600 kPa")  # minimum useful line pressure
NET_DEMAND = Quantity.parse("0.01 m**3/s")  # 10 L/s free air beyond compressor output
ATMOSPHERIC = Quantity.parse("101.325 kPa")
REQUIRED_HOLDUP = Quantity.parse("300 s")  # ride out a 5-minute burst


def receiver_sizing() -> dict[str, float]:
    """Return the hold-up time (s) of the 1 m³ tank and the volume a 5-minute burst needs (m³)."""
    holdup = (
        air_receiver_holdup_time(
            receiver_volume=RECEIVER_VOLUME,
            max_pressure=MAX_PRESSURE,
            min_pressure=MIN_PRESSURE,
            net_demand=NET_DEMAND,
            atmospheric_pressure=ATMOSPHERIC,
        )
        .to("s")
        .magnitude
    )
    volume = (
        air_receiver_volume_for_demand(
            net_demand=NET_DEMAND,
            holdup_time=REQUIRED_HOLDUP,
            max_pressure=MAX_PRESSURE,
            min_pressure=MIN_PRESSURE,
            atmospheric_pressure=ATMOSPHERIC,
        )
        .to("m**3")
        .magnitude
    )
    return {
        "holdup_s": holdup,
        "volume_for_5min_m3": volume,
    }


def main() -> None:
    r = receiver_sizing()
    holdup = r["holdup_s"]
    print(f"1 m3 tank holds up : {holdup:.0f} s ({holdup / 60:.1f} min) at 10 L/s net draw")
    print(f"to ride a 5-min burst : need a {r['volume_for_5min_m3']:.2f} m3 receiver")
    print("  -> the tank is a pneumatic battery; a bigger burst wants a bigger tank")


if __name__ == "__main__":
    main()
