"""T1 analytical magnetic-actuator checks (closed-form).

Electromagnets do mechanical work — lifting magnets, magnetic chucks and clamps, solenoid valves,
relays, and the bias magnets of magnetic bearings all turn current into force. The physics is a
short chain: a coil makes a field, the field carries a pressure, and that pressure over a pole face
is a force. Each step is closed-form, and together they size any simple magnetic actuator,
complementing the AC-circuit relations of :mod:`anvilate.analysis.reactive_circuit`.

A long solenoid of n turns per unit length carrying a current I makes an axial field B = μ₀·n·I
inside it. That field stores energy, and at a surface it presses with the Maxwell magnetic pressure
p = B²/(2·μ₀) — the pull a magnetic field exerts on iron, about 0.4 MPa at one tesla. Applied over a
pole face of area A, that pressure becomes the holding force F = B²·A/(2·μ₀) an electromagnet makes
across its gap. Because the force goes as the square of the field, a lifting magnet's grip falls off
sharply as an air gap or a rusty surface weakens the field it can drive.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

VACUUM_PERMEABILITY = 4.0e-7 * pi  # μ₀, T·m/A

__all__ = [
    "electromagnet_holding_force",
    "magnetic_pressure",
    "solenoid_magnetic_field",
]


def solenoid_magnetic_field(*, turns_per_length: Quantity, current: Quantity) -> Quantity:
    """The field inside a long solenoid, B = μ₀·n·I.

    The axial magnetic flux density deep inside a long air-cored solenoid: the vacuum permeability
    μ₀ times the ``turns_per_length`` n and the ``current`` I, B = μ₀·n·I. It is uniform along the
    bore and independent of the coil's diameter, and it is the field a solenoid actuator or an
    electromagnet's coil makes before any iron concentrates it. Returns the flux density in tesla.
    """
    _check(turns_per_length, "1/[length]", "turns_per_length")
    _check(current, "[current]", "current")
    n = turns_per_length.to("1/m").magnitude
    i = current.to("A").magnitude
    if n <= 0:
        raise ValueError("turns_per_length must be positive")
    if i <= 0:
        raise ValueError("current must be positive")
    return Quantity(magnitude=VACUUM_PERMEABILITY * n * i, unit="T")


def magnetic_pressure(*, magnetic_flux_density: Quantity) -> Quantity:
    """The Maxwell magnetic pressure, p = B²/(2·μ₀).

    The pressure a magnetic field exerts on a surface it acts across — the energy density of the
    field doubling as a stress: from the ``magnetic_flux_density`` B, p = B²/(2·μ₀), ~0.4 MPa at
    one tesla. It rises with the square of the field, so it is the holding pressure of a magnetic
    chuck and the force per unit area at the pole of any electromagnet
    (:func:`electromagnet_holding_force`). Returns the magnetic pressure in MPa.
    """
    _check(magnetic_flux_density, "[magnetic_field]", "magnetic_flux_density")
    b = magnetic_flux_density.to("T").magnitude
    if b <= 0:
        raise ValueError("magnetic_flux_density must be positive")
    return Quantity(magnitude=b * b / (2.0 * VACUUM_PERMEABILITY) / 1.0e6, unit="MPa")


def electromagnet_holding_force(
    *, magnetic_flux_density: Quantity, pole_area: Quantity
) -> Quantity:
    """The electromagnet holding force, F = B²·A/(2·μ₀).

    The force an electromagnet pulls with across its gap: the Maxwell magnetic pressure B²/(2·μ₀)
    (:func:`magnetic_pressure`) of the gap ``magnetic_flux_density`` B, over the ``pole_area`` A in
    contact, F = B²·A/(2·μ₀). Because it goes as the square of the field, a lifting magnet or clamp
    loses grip fast as an air gap, paint, or rust weakens the field — which is why holding force is
    quoted only against a clean, flat, thick keeper. Returns the holding force in kN.
    """
    _check(magnetic_flux_density, "[magnetic_field]", "magnetic_flux_density")
    _check(pole_area, "[area]", "pole_area")
    b = magnetic_flux_density.to("T").magnitude
    a = pole_area.to("m**2").magnitude
    if b <= 0:
        raise ValueError("magnetic_flux_density must be positive")
    if a <= 0:
        raise ValueError("pole_area must be positive")
    return Quantity(magnitude=b * b * a / (2.0 * VACUUM_PERMEABILITY) / 1000.0, unit="kN")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
