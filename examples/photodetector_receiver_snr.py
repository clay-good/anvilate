"""Worked example: the shot-noise-limited signal-to-noise of a fiber receiver.

An optical receiver's reach comes down to a simple chain: light in, current out, noise floor. This
example runs that chain for a 1550 nm InGaAs photodiode (quantum efficiency 0.8) receiving 1 µW of
optical power over a 1 GHz bandwidth, and works out the shot-noise-limited signal-to-noise ratio.

The diode's responsivity is about 1 A/W, so 1 µW makes 1 µA of photocurrent. The shot noise over the
full 1 GHz is about 18 nA, so the signal current sits roughly 56× above the shot-noise floor — about
35 dB of electrical SNR, enough to recover the bit stream at this wide bandwidth. Halve the received
power and the signal falls by 2× while the shot noise falls only by √2, so the SNR degrades: the
square-root growth of shot noise is exactly why receiver sensitivity has a floor.

Run it directly (``python examples/photodetector_receiver_snr.py``);
:func:`receiver_snr` is also exercised in the test suite.
"""

from __future__ import annotations

from math import log10

from anvilate.analysis import (
    photodiode_current,
    photodiode_responsivity,
    shot_noise_current,
)
from anvilate.units import Quantity

QUANTUM_EFFICIENCY = 0.8
WAVELENGTH = Quantity.parse("1550 nm")
OPTICAL_POWER = Quantity.parse("1 uW")
BANDWIDTH = Quantity.parse("1 GHz")


def receiver_snr() -> dict[str, float]:
    """Return the responsivity (A/W), photocurrent (uA), shot noise (pA), and SNR (dB)."""
    r = photodiode_responsivity(quantum_efficiency=QUANTUM_EFFICIENCY, wavelength=WAVELENGTH)
    i = photodiode_current(responsivity=r, optical_power=OPTICAL_POWER)
    i_noise = shot_noise_current(current=i, bandwidth=BANDWIDTH)
    ratio = i.to("A").magnitude / i_noise.to("A").magnitude
    return {
        "responsivity_a_w": r.to("A/W").magnitude,
        "photocurrent_ua": i.to("uA").magnitude,
        "shot_noise_pa": i_noise.to("A").magnitude * 1e12,
        "snr_db": 20.0 * log10(ratio),
    }


def main() -> None:
    s = receiver_snr()
    print("1550 nm InGaAs receiver, 1 uW in, 1 GHz bandwidth:")
    print(f"  responsivity  : {s['responsivity_a_w']:.2f} A/W")
    print(f"  photocurrent  : {s['photocurrent_ua']:.2f} uA")
    print(f"  shot noise    : {s['shot_noise_pa']:.1f} pA")
    print(f"  -> shot-noise-limited SNR : {s['snr_db']:.0f} dB")


if __name__ == "__main__":
    main()
