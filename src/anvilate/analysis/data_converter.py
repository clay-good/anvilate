"""T1 analytical data-converter (ADC quantization) checks (closed-form).

An analog-to-digital converter can only represent a signal to a finite number of levels, so it adds
quantization noise — the rounding error between the true value and the nearest code. For a
full-scale sine wave that error sets a hard ceiling on the signal-to-noise ratio, one that improves
by a fixed amount for every extra bit. This is the sampling-amplitude counterpart to the
sampling-rate limits of :mod:`anvilate.analysis.channel_capacity` (Nyquist and Shannon): those bound
how often you sample, this bounds how finely.

An ideal N-bit converter reaches SNR = 6.02·N + 1.76 dB — the famous "6 dB per bit" rule, so a
12-bit converter tops out near 74 dB. Each code spans one least-significant bit, the quantization
step LSB = V_FS/2^N, which is the finest voltage the converter resolves. Real converters fall short,
and inverting the SNR rule turns a measured SNR into the effective number of bits,
ENOB = (SNR − 1.76)/6.02 — the resolution the part actually delivers. Two effects move the SNR off
that ideal: the quantization error itself is a noise of RMS LSB/√12, oversampling by a ratio OSR
spreads it over a wider band and recovers 10·log10(OSR) dB (half a bit per doubling), and sampling a
fast input with a jittery clock caps the SNR at −20·log10(2π·f·t_j) regardless of resolution. Bit
counts and dB figures are plain floats; the full-scale voltage, step, and noise are
dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Kester, *The Data Conversion Handbook* (Analog Devices), and IEEE
Std 1241, for the resolution, SNR, ENOB and sampling relations.
"""

from __future__ import annotations

from math import log10, pi, sqrt

from ..units import Quantity
from ..units.rotation import count_rate_per_second

__all__ = [
    "effective_number_of_bits",
    "quantization_snr",
    "quantization_step",
    "quantization_noise_voltage",
    "oversampling_snr_gain",
    "oversampling_ratio_for_bits",
    "aperture_jitter_snr_limit",
]


def quantization_snr(*, bits: float) -> float:
    """The ideal quantization SNR, SNR = 6.02·N + 1.76 dB.

    The best signal-to-noise ratio an ideal N-bit converter can reach for a full-scale sine wave,
    from the resolution ``bits`` N: SNR = 6.02·N + 1.76 dB. Every extra bit buys about 6 dB. Returns
    the SNR in dB as a plain float.
    """
    if bits <= 0:
        raise ValueError("bits must be positive")
    return 6.02 * bits + 1.76


def quantization_step(*, full_scale_voltage: Quantity, bits: float) -> Quantity:
    """The quantization step (LSB voltage), LSB = V_FS/2^N.

    The voltage spanned by one code — the finest difference the converter resolves — from the
    ``full_scale_voltage`` V_FS and the resolution ``bits`` N: LSB = V_FS/2^N. Each added bit halves
    the step, resolving finer detail. Returns the step voltage in V.
    """
    _check(full_scale_voltage, "[electric_potential]", "full_scale_voltage")
    v_fs = full_scale_voltage.to("V").magnitude
    if v_fs <= 0:
        raise ValueError("full_scale_voltage must be positive")
    if bits <= 0:
        raise ValueError("bits must be positive")
    return Quantity(magnitude=v_fs / (2.0**bits), unit="V")


def quantization_noise_voltage(*, full_scale_voltage: Quantity, bits: float) -> Quantity:
    """The RMS quantization-noise voltage, q_rms = LSB/√12 = V_FS/(2^N·√12).

    Rounding to the nearest code leaves an error spread uniformly across one step, whose RMS value
    is LSB/√12 — the noise floor behind the 6-dB-per-bit rule. From the ``full_scale_voltage`` V_FS
    and the resolution ``bits`` N it is V_FS/(2^N·√12); dividing a full-scale sine's RMS by it gives
    back :func:`quantization_snr`. Returns the RMS noise voltage in V.
    """
    _check(full_scale_voltage, "[electric_potential]", "full_scale_voltage")
    v_fs = full_scale_voltage.to("V").magnitude
    if v_fs <= 0:
        raise ValueError("full_scale_voltage must be positive")
    if bits <= 0:
        raise ValueError("bits must be positive")
    return Quantity(magnitude=v_fs / (2.0**bits * sqrt(12.0)), unit="V")


def oversampling_snr_gain(*, oversampling_ratio: float) -> float:
    """The SNR gain from oversampling, ΔSNR = 10·log10(OSR) dB.

    Sampling faster than Nyquist spreads the same quantization noise power over a wider band, and
    filtering back to the signal band keeps only a fraction 1/OSR of it: the in-band SNR rises by
    10·log10(OSR) dB, or equivalently half a bit for every doubling of the ``oversampling_ratio``
    OSR (= f_s/2·BW ≥ 1). This is the principle behind sigma-delta converters. Returns the SNR gain
    in dB as a plain float.
    """
    if oversampling_ratio < 1:
        raise ValueError(f"oversampling_ratio must be at least 1; got {oversampling_ratio}")
    return 10.0 * log10(oversampling_ratio)


def oversampling_ratio_for_bits(*, extra_bits: float) -> float:
    """The oversampling ratio needed to gain a target resolution, OSR = 4^ΔN.

    The design inverse of :func:`oversampling_snr_gain` expressed in bits: because each doubling of
    the rate buys half a bit, gaining ``extra_bits`` ΔN of effective resolution needs
    OSR = 2^(2·ΔN) = 4^ΔN — the cost climbs steeply, so plain oversampling (without noise shaping)
    is expensive past a bit or two. ``extra_bits`` is non-negative. Returns the required OSR
    as a plain float.
    """
    if extra_bits < 0:
        raise ValueError(f"extra_bits must be non-negative; got {extra_bits}")
    return 2.0 ** (2.0 * extra_bits)


def aperture_jitter_snr_limit(*, input_frequency: Quantity, rms_jitter: Quantity) -> float:
    """The jitter-limited SNR ceiling, SNR = −20·log10(2π·f_in·t_j) dB.

    A sample taken t_j early or late on a signal of slope 2π·f_in·A misplaces the amplitude, and the
    resulting timing noise caps the SNR at −20·log10(2π·f_in·t_j) — independent of resolution, so it
    is the wall a high-resolution converter hits on a fast input. From the ``input_frequency`` f_in
    and the clock's ``rms_jitter`` t_j; halving the jitter or the input frequency buys 6 dB. Compare
    it with :func:`quantization_snr`: whichever is lower governs. Returns the SNR ceiling in dB as a
    plain float.
    """
    _check(input_frequency, "1/[time]", "input_frequency")
    _check(rms_jitter, "[time]", "rms_jitter")
    f_in = count_rate_per_second(input_frequency, name="input_frequency")
    t_j = rms_jitter.to("s").magnitude
    if f_in <= 0:
        raise ValueError("input_frequency must be positive")
    if t_j <= 0:
        raise ValueError("rms_jitter must be positive")
    return -20.0 * log10(2.0 * pi * f_in * t_j)


def effective_number_of_bits(*, snr_db: float) -> float:
    """The effective number of bits, ENOB = (SNR − 1.76)/6.02.

    The real resolution a converter delivers, from a measured signal-to-noise-and-distortion ratio
    ``snr_db`` in dB, by inverting the ideal SNR rule: ENOB = (SNR − 1.76)/6.02. A part quoted at N
    bits with an ENOB well below N is dominated by noise and distortion, not quantization. Returns
    the effective number of bits as a plain float.

    The relation inverts SNR = 6.02·N + 1.76 over N > 0, so its domain is ``snr_db`` > 1.76 dB.
    At 1.76 dB the converter resolves exactly one level; below it there is no physical inverse
    and this refuses, rather than handing back a negative "resolution" that every consumer of a
    bit count in this module (all three enforce bits > 0) would reject later under an unrelated
    message.
    """
    if snr_db <= 1.76:
        raise ValueError(
            f"snr_db must exceed 1.76 dB (one bit of resolution); got {snr_db} dB, which "
            f"inverts to {(snr_db - 1.76) / 6.02:.4g} bits"
        )
    return (snr_db - 1.76) / 6.02


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
