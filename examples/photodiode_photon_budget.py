"""Worked example: photon energy and count for a photodiode — and the band-gap wavelength limit.

Detecting light quantum by quantum turns on two numbers: how much energy each photon carries, and
how many arrive per second. The first says whether a photon can be detected at all — it must carry
at least the detector's band-gap energy — and the second sets the signal (and the shot-noise floor)
at low light. This example works both for a green (500 nm) source and checks a silicon detector's
long-wavelength cutoff.

A 500 nm green photon carries about 2.48 eV. A 1 mW green beam therefore delivers about 2.5e15
photons per second — the count a photodiode converts to current. Silicon has a 1.12 eV band gap, so
the longest wavelength it detects is the wavelength whose photon energy just equals that gap: about
1107 nm, in the near infrared. A photon beyond that (say 1550 nm telecom light) carries too little
energy and passes through silicon unseen, which is why long-haul detectors use germanium or InGaAs.
The example reports the green photon energy, the 1 mW photon flux, and silicon's cutoff wavelength.

Run it directly (``python examples/photodiode_photon_budget.py``);
:func:`photon_budget` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    photon_energy,
    photon_flux,
    photon_wavelength_from_energy,
)
from anvilate.units import Quantity

GREEN_WAVELENGTH = Quantity.parse("500 nm")
BEAM_POWER = Quantity.parse("1 mW")
SILICON_BAND_GAP = Quantity.parse("1.12 eV")


def photon_budget() -> dict[str, float]:
    """Return the green photon energy, the 1 mW photon flux, and silicon's cutoff wavelength."""
    energy = photon_energy(wavelength=GREEN_WAVELENGTH)
    flux = photon_flux(optical_power=BEAM_POWER, wavelength=GREEN_WAVELENGTH)
    cutoff = photon_wavelength_from_energy(energy=SILICON_BAND_GAP)
    return {
        "green_photon_energy_ev": energy.to("eV").magnitude,
        "photon_flux_per_s": flux.to("1/s").magnitude,
        "silicon_cutoff_nm": cutoff.to("nm").magnitude,
    }


def main() -> None:
    d = photon_budget()
    print(f"green (500 nm) photon energy: {d['green_photon_energy_ev']:.2f} eV")
    print(f"photon flux of a 1 mW green beam: {d['photon_flux_per_s']:.2e} /s")
    print(f"silicon (1.12 eV) cutoff wavelength: {d['silicon_cutoff_nm']:.0f} nm")


if __name__ == "__main__":
    main()
