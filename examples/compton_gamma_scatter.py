"""Worked example: a gamma ray Compton-scattering off an electron.

When an X-ray or gamma photon scatters off a loosely-bound electron, its wavelength lengthens by an
amount that depends only on the scattering angle — not on the photon's energy. That angle-only shift
is the fingerprint of the photon's particle-like momentum, and it drives the dominant interaction of
medium-energy gamma rays with matter. This example follows a 124 keV X-ray photon scattering through
90 degrees.

At 90 degrees the Compton shift is one electron Compton wavelength, about 2.43 pm. Added to the
photon's incident 10 pm (0.01 nm, a ~124 keV X-ray), the scattered wavelength grows to about 12.4
pm, and the energy handed to the recoiling electron is about 24 keV — which a Compton-camera
detector measures to reconstruct the scattering geometry. The example reports the wavelength shift,
the scattered wavelength, and the recoil electron energy.

Run it directly (``python examples/compton_gamma_scatter.py``);
:func:`gamma_scatter` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    compton_electron_energy,
    compton_scattered_wavelength,
    compton_wavelength_shift,
)
from anvilate.units import Quantity

INCIDENT_WAVELENGTH = Quantity(magnitude=1e-11, unit="m")  # 0.01 nm, ~124 keV
SCATTERING_ANGLE = 90.0


def gamma_scatter() -> dict[str, float]:
    """Return the Compton wavelength shift, the scattered wavelength, and the electron energy."""
    shift = compton_wavelength_shift(scattering_angle=SCATTERING_ANGLE)
    scattered = compton_scattered_wavelength(
        incident_wavelength=INCIDENT_WAVELENGTH, scattering_angle=SCATTERING_ANGLE
    )
    electron_energy = compton_electron_energy(
        incident_wavelength=INCIDENT_WAVELENGTH, scattering_angle=SCATTERING_ANGLE
    )
    return {
        "wavelength_shift_pm": shift.to("pm").magnitude,
        "scattered_wavelength_pm": scattered.to("pm").magnitude,
        "electron_energy_kev": electron_energy.to("J").magnitude / 1.602176634e-19 / 1e3,
    }


def main() -> None:
    d = gamma_scatter()
    print(f"Compton wavelength shift at 90 deg: {d['wavelength_shift_pm']:.2f} pm")
    print(f"scattered photon wavelength: {d['scattered_wavelength_pm']:.1f} pm")
    print(f"recoil electron energy: {d['electron_energy_kev']:.0f} keV")


if __name__ == "__main__":
    main()
