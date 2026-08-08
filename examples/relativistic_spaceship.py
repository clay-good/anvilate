"""Worked example: relativistic effects aboard a spaceship at 0.6c.

At six-tenths of light speed the classical world visibly bends: lengths shrink, momentum outruns
the classical estimate, and a signal beamed back to Earth reddens. All three follow from the same
Lorentz factor.

A ship travelling at 0.6c has a Lorentz factor of 1.25. A 100 m ship contracts to 80 m along its
direction of travel as measured from Earth. A 1,000 kg probe launched from it carries a relativistic
momentum of about 2.25e11 kg·m/s — a quarter more than the classical m·v. And a 100 MHz beacon on
the receding ship is redshifted to 50 MHz by the relativistic Doppler effect. This example reports
the contracted length, the relativistic momentum, and the received beacon frequency.

Run it directly (``python examples/relativistic_spaceship.py``);
:func:`spaceship_relativity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    length_contraction,
    relativistic_doppler_frequency,
    relativistic_momentum,
)
from anvilate.units import Quantity

SHIP_LENGTH = Quantity(magnitude=100.0, unit="m")
PROBE_MASS = Quantity(magnitude=1000.0, unit="kg")
VELOCITY = Quantity(magnitude=0.6 * 299792458.0, unit="m/s")
BEACON_FREQUENCY = Quantity(magnitude=100.0, unit="MHz")


def spaceship_relativity() -> dict[str, float]:
    """Return the contracted length, the relativistic momentum, and the received frequency."""
    length = length_contraction(proper_length=SHIP_LENGTH, velocity=VELOCITY)
    momentum = relativistic_momentum(mass=PROBE_MASS, velocity=VELOCITY)
    received = relativistic_doppler_frequency(
        source_frequency=BEACON_FREQUENCY, velocity=VELOCITY, approaching=False
    )
    return {
        "contracted_length_m": length.to("m").magnitude,
        "momentum_kg_m_s": momentum.to("kg*m/s").magnitude,
        "received_frequency_mhz": received.to("MHz").magnitude,
    }


def main() -> None:
    d = spaceship_relativity()
    print(f"contracted length: {d['contracted_length_m']:.1f} m")
    print(f"relativistic momentum: {d['momentum_kg_m_s']:.3e} kg m/s")
    print(f"received beacon frequency: {d['received_frequency_mhz']:.1f} MHz")


if __name__ == "__main__":
    main()
