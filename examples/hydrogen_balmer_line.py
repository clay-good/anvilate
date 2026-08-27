"""Worked example: the red Balmer line of hydrogen (Bohr model).

Hydrogen glows red in a discharge tube because its electron, dropping from the third energy level to
the second, emits light at a single sharp wavelength. The Bohr model gives the whole picture: the
energy of each level, how far out the electron orbits, and the wavelength of the jump between them.

For the n = 3 -> 2 transition (the Balmer-alpha line), the electron falls from -1.512 eV to
-3.401 eV, releasing about 1.89 eV. That photon has a wavelength of about 656 nm — the deep red line
that gives hydrogen discharge tubes and many nebulae their color. The n = 2 orbit sits about 212 pm
from the nucleus. This example reports the n = 2 energy level, the n = 2 orbit radius, and the
Balmer-alpha wavelength.

Run it directly (``python examples/hydrogen_balmer_line.py``);
:func:`balmer_alpha_line` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bohr_energy_level,
    bohr_orbit_radius,
    rydberg_transition_wavelength,
)


def balmer_alpha_line() -> dict[str, float]:
    """Return the n=2 energy level, the n=2 orbit radius, and the Balmer-alpha wavelength."""
    e2 = bohr_energy_level(principal_quantum_number=2)
    r2 = bohr_orbit_radius(principal_quantum_number=2)
    wavelength = rydberg_transition_wavelength(lower_level=2, upper_level=3)
    return {
        "energy_n2_ev": e2.to("eV").magnitude,
        "radius_n2_pm": r2.to("m").magnitude * 1e12,
        "balmer_alpha_nm": wavelength.to("m").magnitude * 1e9,
    }


def main() -> None:
    d = balmer_alpha_line()
    print(f"n=2 energy level: {d['energy_n2_ev']:.3f} eV")
    print(f"n=2 orbit radius: {d['radius_n2_pm']:.0f} pm")
    print(f"Balmer-alpha wavelength: {d['balmer_alpha_nm']:.0f} nm")


if __name__ == "__main__":
    main()
