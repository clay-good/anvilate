"""Worked example: a cyclotron-resonance mass spectrometer weighing a proton.

A charged particle in a magnetic field orbits at a frequency fixed by its charge-to-mass ratio and
the field, independent of how fast it moves. That speed-independence is what makes the cyclotron
work with a fixed drive frequency, and it lets a mass spectrometer weigh an ion by measuring its
orbit frequency. This example runs both directions for a proton in a 1 tesla field.

A proton (charge 1.602e-19 C, mass 1.673e-27 kg) in a 1 T field orbits at a cyclotron frequency of
about 15.2 MHz. Moving at 1e6 m/s, its Larmor orbit radius is about 1.04 cm — a compact circle that
sets the size of the trap. Reading it the other way, an ion measured at that 15.2 MHz in the same
1 T field weighs back to the proton mass, which is how an ion-cyclotron-resonance mass spectrometer
identifies a species. The example reports the cyclotron frequency, the Larmor radius, and the mass
recovered from the frequency.

Run it directly (``python examples/cyclotron_mass_spectrometer.py``);
:func:`mass_spectrometry` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    cyclotron_frequency,
    cyclotron_mass_from_frequency,
    larmor_radius,
)
from anvilate.units import Quantity

PROTON_CHARGE = Quantity(magnitude=1.602176634e-19, unit="C")
PROTON_MASS = Quantity(magnitude=1.67262192369e-27, unit="kg")
FIELD = Quantity.parse("1 T")
PROTON_SPEED = Quantity.parse("1e6 m/s")


def mass_spectrometry() -> dict[str, float]:
    """Return the cyclotron frequency, the Larmor radius, and the mass from the frequency."""
    frequency = cyclotron_frequency(
        charge=PROTON_CHARGE, magnetic_flux_density=FIELD, mass=PROTON_MASS
    )
    radius = larmor_radius(
        mass=PROTON_MASS, speed=PROTON_SPEED, charge=PROTON_CHARGE, magnetic_flux_density=FIELD
    )
    recovered_mass = cyclotron_mass_from_frequency(
        charge=PROTON_CHARGE, magnetic_flux_density=FIELD, frequency=frequency
    )
    return {
        "cyclotron_frequency_mhz": frequency.to("MHz").magnitude,
        "larmor_radius_cm": radius.to("cm").magnitude,
        "recovered_mass_kg": recovered_mass.to("kg").magnitude,
    }


def main() -> None:
    d = mass_spectrometry()
    print(f"cyclotron frequency: {d['cyclotron_frequency_mhz']:.1f} MHz")
    print(f"Larmor radius at 1e6 m/s: {d['larmor_radius_cm']:.2f} cm")
    print(f"mass recovered from frequency: {d['recovered_mass_kg']:.3e} kg")


if __name__ == "__main__":
    main()
