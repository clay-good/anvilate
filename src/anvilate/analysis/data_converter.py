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
ENOB = (SNR − 1.76)/6.02 — the resolution the part actually delivers. Bit counts and dB figures are
plain floats; the full-scale voltage and step are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "effective_number_of_bits",
    "quantization_snr",
    "quantization_step",
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


def effective_number_of_bits(*, snr_db: float) -> float:
    """The effective number of bits, ENOB = (SNR − 1.76)/6.02.

    The real resolution a converter delivers, from a measured signal-to-noise-and-distortion ratio
    ``snr_db`` in dB, by inverting the ideal SNR rule: ENOB = (SNR − 1.76)/6.02. A part quoted at N
    bits with an ENOB well below N is dominated by noise and distortion, not quantization. Returns
    the effective number of bits as a plain float.
    """
    return (snr_db - 1.76) / 6.02


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
