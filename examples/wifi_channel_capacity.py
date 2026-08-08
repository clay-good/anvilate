"""Worked example: how much data a Wi-Fi channel can carry, and the bandwidth a target rate needs.

The data rate of a radio link is capped by two things: its bandwidth and its signal-to-noise ratio.
The Shannon-Hartley theorem gives the absolute ceiling no coding can beat, and inverting it tells a
system designer how much spectrum a target throughput demands. The noiseless Nyquist relation adds
the other side — how many signal levels a clean channel would need to hit a rate. This example runs
all three for a 20 MHz Wi-Fi channel.

At a 20 dB signal-to-noise ratio (a linear ratio of 100), a 20 MHz channel has a Shannon capacity of
about 133 Mbit/s — the most it can ever carry. To instead guarantee 100 Mbit/s at that same SNR, the
link needs about 15 MHz of bandwidth, comfortably inside the 20 MHz channel. On a noiseless channel,
reaching 80 Mbit/s over 20 MHz would take a 4-level (2 bit/symbol) scheme by the Nyquist relation.
The example reports the Shannon capacity, the bandwidth for 100 Mbit/s, and the Nyquist rate.

Run it directly (``python examples/wifi_channel_capacity.py``);
:func:`link_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    nyquist_channel_capacity,
    shannon_capacity,
    shannon_required_bandwidth,
)
from anvilate.units import Quantity

CHANNEL_BANDWIDTH = Quantity(magnitude=20e6, unit="Hz")
SIGNAL_TO_NOISE = 100.0  # 20 dB, linear
TARGET_CAPACITY = 100e6  # 100 Mbit/s
SIGNAL_LEVELS = 4


def link_capacity() -> dict[str, float]:
    """Return the Shannon capacity, the bandwidth for 100 Mbit/s, and the 4-level Nyquist rate."""
    capacity = shannon_capacity(bandwidth=CHANNEL_BANDWIDTH, signal_to_noise_ratio=SIGNAL_TO_NOISE)
    required_bw = shannon_required_bandwidth(
        capacity=TARGET_CAPACITY, signal_to_noise_ratio=SIGNAL_TO_NOISE
    )
    nyquist = nyquist_channel_capacity(bandwidth=CHANNEL_BANDWIDTH, signal_levels=SIGNAL_LEVELS)
    return {
        "shannon_capacity_mbit_s": capacity / 1e6,
        "bandwidth_for_100mbit_mhz": required_bw.to("MHz").magnitude,
        "nyquist_4level_mbit_s": nyquist / 1e6,
    }


def main() -> None:
    d = link_capacity()
    print(f"Shannon capacity (20 MHz, 20 dB): {d['shannon_capacity_mbit_s']:.0f} Mbit/s")
    print(f"bandwidth for 100 Mbit/s: {d['bandwidth_for_100mbit_mhz']:.0f} MHz")
    print(f"noiseless 4-level Nyquist rate: {d['nyquist_4level_mbit_s']:.0f} Mbit/s")


if __name__ == "__main__":
    main()
