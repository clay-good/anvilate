"""Worked example: the cutoff and dispersion of a WR-90 X-band waveguide.

A rectangular waveguide only carries microwaves above a cutoff frequency fixed by its width, and
above that cutoff it is dispersive: the wavelength inside is longer than in free space and the phase
velocity exceeds the speed of light. Designing a waveguide run means checking that the operating
frequency clears cutoff with margin, and knowing the guide wavelength (which sets slot and iris
spacing) and the phase velocity. This example does so for the standard WR-90 X-band guide.

WR-90 has a broad inside dimension of 22.86 mm, giving a TE10 cutoff of about 6.56 GHz — so it runs
across roughly 8-12 GHz, comfortably above cutoff. At a 10 GHz operating point (free-space
wavelength 30 mm), the guide wavelength stretches to about 39.7 mm, and the phase velocity is 1.32x
the speed of light (the energy still travels slower, at the group velocity). The example reports the
cutoff frequency, the guide wavelength at 10 GHz, and the phase velocity as a multiple of c.

Run it directly (``python examples/wr90_waveguide.py``);
:func:`wr90_dispersion` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    rectangular_waveguide_cutoff_frequency,
    waveguide_guide_wavelength,
    waveguide_phase_velocity,
)
from anvilate.units import Quantity

BROAD_DIMENSION = Quantity.parse("22.86 mm")  # WR-90
OPERATING_FREQUENCY = Quantity(magnitude=10e9, unit="Hz")
SPEED_OF_LIGHT = 299792458.0


def wr90_dispersion() -> dict[str, float]:
    """Return the cutoff frequency, the guide wavelength at 10 GHz, and v_p as a multiple of c."""
    cutoff = rectangular_waveguide_cutoff_frequency(broad_dimension=BROAD_DIMENSION)
    guide_wl = waveguide_guide_wavelength(
        operating_frequency=OPERATING_FREQUENCY, cutoff_frequency=cutoff
    )
    v_p = waveguide_phase_velocity(operating_frequency=OPERATING_FREQUENCY, cutoff_frequency=cutoff)
    return {
        "cutoff_frequency_ghz": cutoff.to("GHz").magnitude,
        "guide_wavelength_mm": guide_wl.to("mm").magnitude,
        "phase_velocity_over_c": v_p.to("m/s").magnitude / SPEED_OF_LIGHT,
    }


def main() -> None:
    d = wr90_dispersion()
    print(f"TE10 cutoff frequency: {d['cutoff_frequency_ghz']:.2f} GHz")
    print(f"guide wavelength at 10 GHz: {d['guide_wavelength_mm']:.1f} mm")
    print(f"phase velocity: {d['phase_velocity_over_c']:.2f} c")


if __name__ == "__main__":
    main()
