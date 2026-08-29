"""T1 analytical cyclotron-motion checks (closed-form).

A charged particle in a magnetic field is bent into a circle by the Lorentz force, orbiting at a
frequency that depends only on its charge-to-mass ratio and the field — not on its speed. This is
the physics of the cyclotron accelerator, the mass spectrometer, magnetic confinement of plasmas of
:mod:`anvilate.analysis.plasma`, and the gyration of cosmic rays. It complements the magnetostatics
of :mod:`anvilate.analysis.magnetics` (which makes the field) with the motion a field imposes on a
moving charge.

The cyclotron frequency is f_c = q*B/(2*pi*m), from the particle's charge q, the magnetic flux
density B, and the mass m — remarkably independent of speed, which is what let the classical
cyclotron use a fixed drive frequency. The orbit radius (Larmor or gyro-radius) is r = m*v/(q*B),
growing with the particle's speed, so a faster particle spirals wider at the same frequency.
Inverting the frequency relation recovers the mass from a measured cyclotron frequency,
m = q*B/(2*pi*f_c) — the principle of the cyclotron-resonance mass spectrometer.

Sources: Chen, *Introduction to Plasma Physics and Controlled Fusion* — the cyclotron frequency
of a charged particle in a magnetic field, the Larmor radius of its gyration, and the mass a
measured frequency implies.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity
from ..units.rotation import count_rate_per_second

__all__ = [
    "cyclotron_frequency",
    "cyclotron_mass_from_frequency",
    "larmor_radius",
]


def cyclotron_frequency(
    *, charge: Quantity, magnetic_flux_density: Quantity, mass: Quantity
) -> Quantity:
    """The cyclotron frequency, f_c = q*B/(2*pi*m).

    The orbital frequency of a particle of ``charge`` q and ``mass`` m in a
    ``magnetic_flux_density`` B, f_c = q*B/(2*pi*m). It depends only on the charge-to-mass ratio and
    the field, not on the
    particle's speed — the property a cyclotron exploits with a fixed drive frequency. Returns the
    cyclotron frequency in Hz.
    """
    _check(charge, "[current]*[time]", "charge")
    _check(magnetic_flux_density, "[magnetic_field]", "magnetic_flux_density")
    _check(mass, "[mass]", "mass")
    q = charge.to("C").magnitude
    b = magnetic_flux_density.to("T").magnitude
    m = mass.to("kg").magnitude
    if q <= 0:
        raise ValueError("charge must be positive")
    if b <= 0:
        raise ValueError("magnetic_flux_density must be positive")
    if m <= 0:
        raise ValueError("mass must be positive")
    return Quantity(magnitude=q * b / (2.0 * pi * m), unit="Hz")


def larmor_radius(
    *, mass: Quantity, speed: Quantity, charge: Quantity, magnetic_flux_density: Quantity
) -> Quantity:
    """The Larmor (gyro) radius, r = m*v/(q*B).

    The radius of the circular orbit a particle of ``mass`` m and ``speed`` v (perpendicular to the
    field) makes with ``charge`` q in a ``magnetic_flux_density`` B, r = m*v/(q*B). It grows with
    the particle's momentum, so at fixed frequency a faster particle circles wider — the radius that
    sets the size of a cyclotron or the confinement scale of a plasma. Returns the radius in m.
    """
    _check(mass, "[mass]", "mass")
    _check(speed, "[length]/[time]", "speed")
    _check(charge, "[current]*[time]", "charge")
    _check(magnetic_flux_density, "[magnetic_field]", "magnetic_flux_density")
    m = mass.to("kg").magnitude
    v = speed.to("m/s").magnitude
    q = charge.to("C").magnitude
    b = magnetic_flux_density.to("T").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    if v < 0:
        raise ValueError("speed must be non-negative")
    if q <= 0:
        raise ValueError("charge must be positive")
    if b <= 0:
        raise ValueError("magnetic_flux_density must be positive")
    return Quantity(magnitude=m * v / (q * b), unit="m")


def cyclotron_mass_from_frequency(
    *, charge: Quantity, magnetic_flux_density: Quantity, frequency: Quantity
) -> Quantity:
    """The particle mass from a cyclotron frequency, m = q*B/(2*pi*f_c).

    The mass-spectrometry inverse of :func:`cyclotron_frequency`: the ``mass`` of an ion of
    ``charge`` q orbiting at a measured cyclotron ``frequency`` f_c in a known
    ``magnetic_flux_density`` B,
    m = q*B/(2*pi*f_c). It is how a cyclotron-resonance (or FT-ICR) mass spectrometer weighs an ion
    from its orbit frequency. Returns the mass in kg.
    """
    _check(charge, "[current]*[time]", "charge")
    _check(magnetic_flux_density, "[magnetic_field]", "magnetic_flux_density")
    _check(frequency, "1/[time]", "frequency")
    q = charge.to("C").magnitude
    b = magnetic_flux_density.to("T").magnitude
    f = count_rate_per_second(frequency, name="frequency")
    if q <= 0:
        raise ValueError("charge must be positive")
    if b <= 0:
        raise ValueError("magnetic_flux_density must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    return Quantity(magnitude=q * b / (2.0 * pi * f), unit="kg")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
