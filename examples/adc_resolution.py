"""Worked example: the resolution of a 12-bit analog-to-digital converter.

An ADC turns a continuous voltage into a finite set of codes, and the rounding it does sets both a
noise floor and a smallest resolvable step. The ideal SNR says how clean the conversion can be, the
quantization step says how fine it is, and the effective number of bits says how much of that ideal
a real part actually achieves.

An ideal 12-bit converter reaches a signal-to-noise ratio of 74.0 dB — the "6 dB per bit" rule. On a
10 V full-scale range each code spans a quantization step of about 2.44 mV. If a real 12-bit part is
measured at only 68 dB SNR, its effective number of bits is about 11.0 — it is really delivering
11-bit performance, a bit lost to noise and distortion. This example reports the ideal SNR, the
quantization step, and the effective number of bits from the measured SNR.

Run it directly (``python examples/adc_resolution.py``);
:func:`adc_resolution` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    effective_number_of_bits,
    quantization_snr,
    quantization_step,
)
from anvilate.units import Quantity

BITS = 12
FULL_SCALE = Quantity(magnitude=10.0, unit="V")
MEASURED_SNR_DB = 68.0


def adc_resolution() -> dict[str, float]:
    """Return the ideal SNR, the quantization step, and the ENOB from a measured SNR."""
    snr = quantization_snr(bits=BITS)
    step = quantization_step(full_scale_voltage=FULL_SCALE, bits=BITS)
    enob = effective_number_of_bits(snr_db=MEASURED_SNR_DB)
    return {
        "ideal_snr_db": snr,
        "quantization_step_mv": step.to("V").magnitude * 1000.0,
        "effective_number_of_bits": enob,
    }


def main() -> None:
    d = adc_resolution()
    print(f"ideal 12-bit SNR: {d['ideal_snr_db']:.1f} dB")
    print(f"quantization step: {d['quantization_step_mv']:.2f} mV")
    print(f"effective number of bits at 68 dB: {d['effective_number_of_bits']:.1f}")


if __name__ == "__main__":
    main()
