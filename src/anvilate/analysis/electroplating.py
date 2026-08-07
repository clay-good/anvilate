"""T1 analytical electroplating checks (closed-form).

Electroplating deposits a metal coating by running current through a plating bath: the part is the
cathode, metal ions in solution reduce onto it, and the coating builds atom by atom. It is Faraday's
law run in reverse of the dissolution in :mod:`anvilate.analysis.ecm` and the metal loss in
:mod:`anvilate.analysis.corrosion` — the same electrochemistry, put to building a layer instead of
removing one. The engineering questions are correspondingly different: not a removal rate but a
*coating thickness*, and how long the tank must run to reach it.

The mass plated obeys Faraday's law directly, m = EW·I·t·η/F — the ``equivalent_weight`` EW and the
charge passed (current I over time t), scaled by the current efficiency η because some current
splits water into hydrogen instead of depositing metal, and divided by the Faraday constant F. That
mass over the plated area at the metal's density gives the coating thickness δ = EW·I·t·η/(F·ρ·A),
and inverting it gives the run time a target thickness needs, t = δ·F·ρ·A/(EW·I·η) — the number that
sets the tank's cycle time and, with it, the throughput of the plating line.
"""

from __future__ import annotations

from ..units import Quantity

# Faraday constant: charge per mole of electrons.
FARADAY_C_PER_MOL = 96485.332

__all__ = [
    "electroplating_deposition_thickness",
    "electroplating_mass_deposited",
    "electroplating_time_for_thickness",
]


def electroplating_mass_deposited(
    *,
    current: Quantity,
    plating_time: Quantity,
    equivalent_weight: float,
    current_efficiency: float,
) -> Quantity:
    """The mass plated by Faraday's law, m = EW·I·t·η/F.

    The mass of metal deposited on the cathode: the ``equivalent_weight`` EW (atomic weight over
    electrons transferred, g/equiv) times the charge passed — the ``current`` I over the
    ``plating_time`` t — scaled by the ``current_efficiency`` η (the fraction of current that
    actually deposits metal rather than evolving hydrogen) and divided by the Faraday constant F, so
    m = EW·I·t·η/F. Returns the deposited mass in g.
    """
    _check(current, "[current]", "current")
    _check(plating_time, "[time]", "plating_time")
    if equivalent_weight <= 0:
        raise ValueError("equivalent_weight must be positive")
    _fraction(current_efficiency, "current_efficiency")
    amps = current.to("A").magnitude
    t = plating_time.to("s").magnitude
    if amps <= 0:
        raise ValueError("current must be positive")
    if t < 0:
        raise ValueError("plating_time must be non-negative")
    m = equivalent_weight * amps * t * current_efficiency / FARADAY_C_PER_MOL
    return Quantity(magnitude=m, unit="g")


def electroplating_deposition_thickness(
    *,
    current: Quantity,
    plating_time: Quantity,
    plated_area: Quantity,
    equivalent_weight: float,
    density: Quantity,
    current_efficiency: float,
) -> Quantity:
    """The coating thickness, δ = EW·I·t·η/(F·ρ·A).

    The thickness of the plated layer: the Faraday mass (:func:`electroplating_mass_deposited`) laid
    over the ``plated_area`` A at the coating's ``density`` ρ, δ = EW·I·t·η/(F·ρ·A), from the
    ``equivalent_weight`` EW, the ``current`` I, the ``plating_time`` t, and the
    ``current_efficiency`` η. It is what a plating spec is written in — a few microns for decorative
    chrome, tens for hard or corrosion coatings — and it grows linearly with both current and time.
    Returns the coating thickness in micrometres.
    """
    _check(current, "[current]", "current")
    _check(plating_time, "[time]", "plating_time")
    _check(plated_area, "[area]", "plated_area")
    _check(density, "[mass]/[length]**3", "density")
    if equivalent_weight <= 0:
        raise ValueError("equivalent_weight must be positive")
    _fraction(current_efficiency, "current_efficiency")
    amps = current.to("A").magnitude
    t = plating_time.to("s").magnitude
    area_cm2 = plated_area.to("cm**2").magnitude
    rho = density.to("g/cm**3").magnitude
    if amps <= 0:
        raise ValueError("current must be positive")
    if t < 0:
        raise ValueError("plating_time must be non-negative")
    if area_cm2 <= 0:
        raise ValueError("plated_area must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    mass_g = equivalent_weight * amps * t * current_efficiency / FARADAY_C_PER_MOL
    thickness_cm = mass_g / (rho * area_cm2)
    return Quantity(magnitude=thickness_cm * 1.0e4, unit="micrometer")


def electroplating_time_for_thickness(
    *,
    target_thickness: Quantity,
    current: Quantity,
    plated_area: Quantity,
    equivalent_weight: float,
    density: Quantity,
    current_efficiency: float,
) -> Quantity:
    """The plating time for a target thickness, t = δ·F·ρ·A/(EW·I·η).

    Inverting the thickness relation (:func:`electroplating_deposition_thickness`) for time: how
    long the tank must run to build a ``target_thickness`` δ over the ``plated_area`` A at the
    ``current`` I, t = δ·F·ρ·A/(EW·I·η), from the ``equivalent_weight`` EW, the ``density`` ρ, and
    ``current_efficiency`` η. It sets the cycle time of the plating line — halving it means doubling
    the current (up to what the bath and finish allow). Returns the plating time in min.
    """
    _check(target_thickness, "[length]", "target_thickness")
    _check(current, "[current]", "current")
    _check(plated_area, "[area]", "plated_area")
    _check(density, "[mass]/[length]**3", "density")
    if equivalent_weight <= 0:
        raise ValueError("equivalent_weight must be positive")
    _fraction(current_efficiency, "current_efficiency")
    delta_cm = target_thickness.to("cm").magnitude
    amps = current.to("A").magnitude
    area_cm2 = plated_area.to("cm**2").magnitude
    rho = density.to("g/cm**3").magnitude
    if delta_cm <= 0:
        raise ValueError("target_thickness must be positive")
    if amps <= 0:
        raise ValueError("current must be positive")
    if area_cm2 <= 0:
        raise ValueError("plated_area must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    charge = delta_cm * FARADAY_C_PER_MOL * rho * area_cm2
    t_s = charge / (equivalent_weight * amps * current_efficiency)
    return Quantity(magnitude=t_s / 60.0, unit="min")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be a fraction in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
