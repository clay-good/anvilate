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

The field a real core carries follows the *magnetic circuit* — the magnetic analogue of Ohm's law
(Hopkinson's law). A coil provides a magnetomotive force MMF = N·I (the "voltage"), the core path
opposes flux with a reluctance R = l/(μ·A) (the "resistance"), and the flux that results is
Φ = MMF/R (the "current"). A high-permeability iron path has low reluctance, so a modest coil drives
a large flux — which is why transformers, motors, and relays are built around iron cores.

Sources: McLyman, *Transformer and Inductor Design Handbook*, for the
magnetic-circuit, core-loss and winding relations.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

VACUUM_PERMEABILITY = 4.0e-7 * pi  # μ₀, T·m/A

__all__ = [
    "coil_inductance",
    "electromagnet_holding_force",
    "magnetic_flux",
    "magnetic_pressure",
    "magnetic_reluctance",
    "magnetomotive_force",
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


def magnetomotive_force(*, turns: float, current: Quantity) -> Quantity:
    """The magnetomotive force of a coil, MMF = N·I.

    The magnetic "driving voltage" a coil of ``turns`` N carrying a ``current`` I applies to a
    magnetic circuit: MMF = N·I, in ampere-turns. It is what drives flux around the core against its
    reluctance (:func:`magnetic_reluctance`). Returns the magnetomotive force in A (ampere-turns).
    """
    _check(current, "[current]", "current")
    if turns <= 0:
        raise ValueError("turns must be positive")
    i = current.to("A").magnitude
    if i <= 0:
        raise ValueError("current must be positive")
    return Quantity(magnitude=turns * i, unit="A")


def magnetic_reluctance(
    *, path_length: Quantity, area: Quantity, relative_permeability: float = 1.0
) -> Quantity:
    """The magnetic reluctance of a core path, R = l/(μ₀·μ_r·A).

    The opposition a magnetic path presents to flux, the analogue of electrical resistance: from the
    ``path_length`` l, the cross-sectional ``area`` A, and the ``relative_permeability`` μ_r
    (defaulting to 1 for air), R = l/(μ₀·μ_r·A). A high-permeability iron path (large μ_r) has low
    reluctance, so it carries much more flux for the same drive. Returns the reluctance in 1/H
    (ampere-turns per weber).
    """
    _check(path_length, "[length]", "path_length")
    _check(area, "[area]", "area")
    ell = path_length.to("m").magnitude
    a = area.to("m**2").magnitude
    if ell <= 0:
        raise ValueError("path_length must be positive")
    if a <= 0:
        raise ValueError("area must be positive")
    if relative_permeability <= 0:
        raise ValueError("relative_permeability must be positive")
    r = ell / (VACUUM_PERMEABILITY * relative_permeability * a)
    return Quantity(magnitude=r, unit="1/H")


def magnetic_flux(*, magnetomotive_force: Quantity, reluctance: Quantity) -> Quantity:
    """The magnetic flux in a circuit, Φ = MMF/R (Hopkinson's law).

    The flux a magnetic circuit carries, the analogue of Ohm's-law current: the
    ``magnetomotive_force`` MMF over the ``reluctance`` R, Φ = MMF/R. Dividing by the core area
    gives the flux density B that the actuator and holding-force relations use. Returns the flux
    in Wb.
    """
    _check(magnetomotive_force, "[current]", "magnetomotive_force")
    _check(reluctance, "1/[inductance]", "reluctance")
    mmf = magnetomotive_force.to("A").magnitude
    r = reluctance.to("1/H").magnitude
    if mmf < 0:
        raise ValueError("magnetomotive_force must be non-negative")
    if r <= 0:
        raise ValueError("reluctance must be positive")
    return Quantity(magnitude=mmf / r, unit="Wb")


def coil_inductance(*, turns: float, reluctance: Quantity) -> Quantity:
    """The inductance of a coil on a magnetic circuit, L = N²/R.

    The inductance a winding presents follows from its magnetic circuit: each of the ``turns`` N
    links the flux the ampere-turns drive through the ``reluctance`` R
    (:func:`magnetic_reluctance`), and the flux linkage per amp works out to L = N²/R. It is the
    magnetic-circuit route to inductance — halve the reluctance (a better core, a shorter gap) and
    the inductance doubles; double the turns and it quadruples. Feed the result to
    ``reactive_circuit.inductor_stored_energy`` for the ½·L·I² the field holds. ``turns`` N is
    positive and ``reluctance`` R a positive magnetic reluctance (1/H). Returns the inductance in H.
    """
    _check(reluctance, "1/[inductance]", "reluctance")
    if turns <= 0:
        raise ValueError("turns must be positive")
    r = reluctance.to("1/H").magnitude
    if r <= 0:
        raise ValueError("reluctance must be positive")
    return Quantity(magnitude=turns**2 / r, unit="H")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
