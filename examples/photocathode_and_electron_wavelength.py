"""Worked example: a photocathode's light threshold and an electron microscope's resolution.

Two quantum relations size two instruments. The photoelectric effect sets whether light of a given
color can eject electrons from a photocathode (and with how much energy), which decides what a
photomultiplier or night-vision tube can detect. The de Broglie relation sets the wavelength of a
moving electron, which fixes the finest detail an electron microscope can resolve. This example
applies both.

The photocathode has a 2.0 eV work function. Its threshold frequency is about 4.8e14 Hz — light
redder than that (lower frequency) ejects nothing, however bright. A 1e15 Hz (near-UV) photon clears
the threshold and gives each ejected electron up to about 2.14 eV of kinetic energy. Separately, an
electron moving at 1e6 m/s has a de Broglie wavelength of about 0.73 nm — hundreds of times shorter
than visible light, which is why an electron microscope resolves far finer than an optical one. The
example reports the threshold frequency, the photoelectron energy, and the electron wavelength.

Run it directly (``python examples/photocathode_and_electron_wavelength.py``);
:func:`quantum_instruments` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    de_broglie_wavelength,
    photoelectric_max_kinetic_energy,
    photoelectric_threshold_frequency,
)
from anvilate.units import Quantity

WORK_FUNCTION = Quantity.parse("2.0 eV")
LIGHT_FREQUENCY = Quantity(magnitude=1e15, unit="Hz")
ELECTRON_MASS = Quantity(magnitude=9.1093837015e-31, unit="kg")
ELECTRON_SPEED = Quantity.parse("1e6 m/s")


def quantum_instruments() -> dict[str, float]:
    """Return the threshold frequency, the photoelectron energy, and the electron wavelength."""
    threshold = photoelectric_threshold_frequency(work_function=WORK_FUNCTION)
    kinetic_energy = photoelectric_max_kinetic_energy(
        frequency=LIGHT_FREQUENCY, work_function=WORK_FUNCTION
    )
    wavelength = de_broglie_wavelength(mass=ELECTRON_MASS, velocity=ELECTRON_SPEED)
    return {
        "threshold_frequency_thz": threshold.to("THz").magnitude,
        "photoelectron_energy_ev": kinetic_energy.to("eV").magnitude,
        "electron_wavelength_nm": wavelength.to("nm").magnitude,
    }


def main() -> None:
    d = quantum_instruments()
    print(f"photocathode threshold frequency: {d['threshold_frequency_thz']:.0f} THz")
    print(f"photoelectron kinetic energy at 1e15 Hz: {d['photoelectron_energy_ev']:.2f} eV")
    print(f"de Broglie wavelength of a 1e6 m/s electron: {d['electron_wavelength_nm']:.2f} nm")


if __name__ == "__main__":
    main()
