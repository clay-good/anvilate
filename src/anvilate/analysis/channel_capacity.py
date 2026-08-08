"""T1 analytical communication-channel-capacity checks (closed-form, information theory).

How much data a link can carry is set by its bandwidth and its signal-to-noise ratio. The
Shannon-Hartley theorem gives the hard ceiling — no coding scheme can beat it — while the Nyquist
relation gives the rate a noiseless channel achieves with a chosen number of signal levels. Together
they size a radio or wireline link: the Shannon limit says whether the target throughput is even
possible over the available band and SNR, and Nyquist says how many levels a clean channel needs to
reach a rate. This completes the RF link work of :mod:`anvilate.analysis.antenna` — the antenna sets
the received SNR, and this sets the bits that SNR carries.

The Shannon capacity is C = B * log2(1 + SNR), from the bandwidth B and the linear signal-to-noise
ratio SNR (a power ratio, not dB). Inverting it gives the bandwidth a target capacity needs at a
given SNR, B = C / log2(1 + SNR). The noiseless Nyquist capacity of an M-level channel is
C = 2 * B * log2(M) — more levels pack more bits per symbol, but need a higher SNR to keep them
distinct, which is where the Shannon limit reasserts itself.

Capacities are counts of bits per second, returned (and taken) as plain floats.
"""

from __future__ import annotations

from math import log2

from ..units import Quantity

__all__ = [
    "nyquist_channel_capacity",
    "shannon_capacity",
    "shannon_required_bandwidth",
]


def shannon_capacity(*, bandwidth: Quantity, signal_to_noise_ratio: float) -> float:
    """The Shannon-Hartley channel capacity, C = B * log2(1 + SNR).

    The maximum error-free data rate a channel of ``bandwidth`` B can carry at a linear
    ``signal_to_noise_ratio`` SNR (a power ratio, not dB): C = B * log2(1 + SNR). No modulation or
    coding can exceed it. Doubling the bandwidth doubles it, but raising SNR only adds capacity
    logarithmically. Returns the capacity as a plain float in bit/s.
    """
    _check(bandwidth, "1/[time]", "bandwidth")
    b = bandwidth.to("Hz").magnitude
    if b < 0:
        raise ValueError("bandwidth must be non-negative")
    if signal_to_noise_ratio < 0:
        raise ValueError("signal_to_noise_ratio must be non-negative")
    return b * log2(1.0 + signal_to_noise_ratio)


def shannon_required_bandwidth(*, capacity: float, signal_to_noise_ratio: float) -> Quantity:
    """The bandwidth a target capacity needs, B = C / log2(1 + SNR).

    The inverse of :func:`shannon_capacity`: the bandwidth required to carry a target ``capacity`` C
    (bit/s) at a linear ``signal_to_noise_ratio`` SNR, B = C / log2(1 + SNR). It is how a link
    budget checks whether the allotted spectrum can support a data rate, or how much SNR would trade
    bandwidth. Returns the required bandwidth in Hz.
    """
    if capacity < 0:
        raise ValueError("capacity must be non-negative")
    if signal_to_noise_ratio <= 0:
        raise ValueError("signal_to_noise_ratio must be positive")
    return Quantity(magnitude=capacity / log2(1.0 + signal_to_noise_ratio), unit="Hz")


def nyquist_channel_capacity(*, bandwidth: Quantity, signal_levels: int) -> float:
    """The noiseless Nyquist capacity, C = 2 * B * log2(M).

    The maximum symbol-limited data rate of a noiseless channel of ``bandwidth`` B using
    ``signal_levels`` M distinct amplitude/phase levels: C = 2 * B * log2(M). More levels pack more
    bits per symbol, but a real (noisy) channel caps how many the SNR can keep distinct — where the
    Shannon limit of :func:`shannon_capacity` takes over. Returns the capacity as a float in bit/s.
    """
    _check(bandwidth, "1/[time]", "bandwidth")
    b = bandwidth.to("Hz").magnitude
    if b < 0:
        raise ValueError("bandwidth must be non-negative")
    if signal_levels < 2:
        raise ValueError("signal_levels must be at least 2")
    return 2.0 * b * log2(signal_levels)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
