"""Worked example: special-relativity effects in two real systems — a fast electron and a muon.

Special relativity leaves everyday engineering untouched but dominates two regimes: particles pushed
near light speed, and precision timekeeping on fast platforms. This example shows both through the
Lorentz factor — the single number that scales every relativistic effect. It computes the energy an
accelerator must give a fast electron, and how much longer a fast muon's clock runs.

An electron driven to 0.9c has a Lorentz factor of about 2.29. Its kinetic energy is then about
0.66 MeV — far above the 0.13 MeV a classical (½mv²) estimate would give, because the relativistic
energy diverges near c. A muon streaking through the atmosphere at 0.99c has a Lorentz factor of
about 7.09, so its 2.2 microsecond proper lifetime is stretched to about 15.6 microseconds in ground
frame — long enough to reach the surface, which is how cosmic-ray muons are detected at all. The
example reports the electron's kinetic energy and the muon's dilated lifetime.

Run it directly (``python examples/gps_and_accelerator_relativity.py``);
:func:`relativistic_effects` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import lorentz_factor, relativistic_kinetic_energy, time_dilation
from anvilate.units import Quantity

SPEED_OF_LIGHT = Quantity(magnitude=299792458.0, unit="m/s")
ELECTRON_MASS = Quantity(magnitude=9.1093837015e-31, unit="kg")
ELECTRON_SPEED = Quantity(magnitude=0.9 * 299792458.0, unit="m/s")
MUON_SPEED = Quantity(magnitude=0.99 * 299792458.0, unit="m/s")
MUON_PROPER_LIFETIME = Quantity.parse("2.2 us")


def relativistic_effects() -> dict[str, float]:
    """Return the electron's kinetic energy (MeV) and the muon's dilated lifetime (us)."""
    ke = relativistic_kinetic_energy(mass=ELECTRON_MASS, velocity=ELECTRON_SPEED)
    muon_gamma = lorentz_factor(velocity=MUON_SPEED)
    dilated = time_dilation(proper_time=MUON_PROPER_LIFETIME, velocity=MUON_SPEED)
    return {
        "electron_kinetic_energy_mev": ke.to("J").magnitude / 1.602176634e-19 / 1e6,
        "muon_lorentz_factor": muon_gamma,
        "muon_dilated_lifetime_us": dilated.to("us").magnitude,
    }


def main() -> None:
    d = relativistic_effects()
    print(f"electron kinetic energy at 0.9c: {d['electron_kinetic_energy_mev']:.2f} MeV")
    print(f"muon Lorentz factor at 0.99c: {d['muon_lorentz_factor']:.2f}")
    print(f"muon dilated lifetime: {d['muon_dilated_lifetime_us']:.1f} us")


if __name__ == "__main__":
    main()
