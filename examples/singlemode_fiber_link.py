"""Worked example: the dispersion limit of a single-mode fiber link.

A single-mode fiber carries a light pulse, but chromatic dispersion spreads that pulse as it goes,
and once the spreading fills a bit slot the link can go no faster. The pulse broadening, the bit
rate it allows, and the reach for a target rate are the three numbers that size a fiber span.

Standard single-mode fiber at 1550 nm has a dispersion parameter of about 17 ps/(nm·km). Over a
100 km span, a source with a 0.1 nm spectral width spreads each pulse by about 170 ps, which caps
the line at roughly 1.47 Gbit/s. Turned around, holding a 2.5 Gbit/s line with that source limits an
uncompensated span to about 59 km — beyond that the link needs dispersion compensation or a narrower
source. This example reports the pulse broadening, the dispersion-limited bit rate, and the reach at
2.5 Gbit/s.

Run it directly (``python examples/singlemode_fiber_link.py``);
:func:`fiber_dispersion_limits` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    chromatic_dispersion_broadening,
    dispersion_limited_bit_rate,
    dispersion_limited_distance,
)
from anvilate.units import Quantity

DISPERSION_PARAMETER = Quantity(magnitude=17.0, unit="ps/(nm*km)")  # SMF at 1550 nm
LENGTH = Quantity(magnitude=100.0, unit="km")
SPECTRAL_WIDTH = Quantity(magnitude=0.1, unit="nm")
TARGET_BIT_RATE = Quantity(magnitude=2.5e9, unit="1/s")  # 2.5 Gbit/s


def fiber_dispersion_limits() -> dict[str, float]:
    """Return the pulse broadening, the dispersion-limited bit rate, and the 2.5 Gbit/s reach."""
    broadening = chromatic_dispersion_broadening(
        dispersion_parameter=DISPERSION_PARAMETER,
        length=LENGTH,
        spectral_width=SPECTRAL_WIDTH,
    )
    bit_rate = dispersion_limited_bit_rate(pulse_broadening=broadening)
    reach = dispersion_limited_distance(
        bit_rate=TARGET_BIT_RATE,
        dispersion_parameter=DISPERSION_PARAMETER,
        spectral_width=SPECTRAL_WIDTH,
    )
    return {
        "pulse_broadening_ps": broadening.to("s").magnitude * 1e12,
        "bit_rate_gbit_s": bit_rate.to("1/s").magnitude / 1e9,
        "reach_at_2p5g_km": reach.to("m").magnitude / 1000.0,
    }


def main() -> None:
    d = fiber_dispersion_limits()
    print(f"pulse broadening over 100 km: {d['pulse_broadening_ps']:.0f} ps")
    print(f"dispersion-limited bit rate: {d['bit_rate_gbit_s']:.2f} Gbit/s")
    print(f"reach at 2.5 Gbit/s: {d['reach_at_2p5g_km']:.0f} km")


if __name__ == "__main__":
    main()
