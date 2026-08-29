"""T1 analytical electrochemical machining (ECM) checks (closed-form).

Electrochemical machining removes metal by anodic dissolution: the workpiece is the anode in a fast-
flowing electrolyte, a shaped tool the cathode, and the metal simply dissolves ion by ion where the
current flows. Because material comes off by Faraday's law and not by a cutting edge, ECM has a
signature no mechanical process shares — the removal rate depends on the *charge passed*, not on the
metal's hardness, so it cuts a hardened die as fast as annealed stock and leaves no burr, no tool
wear, and no heat-affected layer. It is the same electrochemistry as the slow corrosion of
:mod:`anvilate.analysis.corrosion`, run deliberately at thousands of times the current density.

Three numbers govern an ECM operation. The material removal rate Q = I·EW/(ρ·F) turns the total
current I into a volume per unit time through the metal's equivalent weight EW, density ρ, and the
Faraday constant F — the throughput of the cut. The feed rate f = J·EW/(ρ·F) is the same law per
unit area, the speed the tool can advance at a current density J. The equilibrium gap
g = κ·U·EW/(ρ·F·f) is where ECM regulates itself: the tool feeds at f, the gap settles until Ohm's
law across the electrolyte (of conductivity κ at voltage U) draws exactly the current that dissolves
metal at that speed. Feed too fast and the gap closes toward zero — the tool touches the work, the
electrolyte sparks, and the operation shorts out.
"""

from __future__ import annotations

from ..units import Quantity

# Faraday constant: charge per mole of electrons.
FARADAY_C_PER_MOL = 96485.332

__all__ = [
    "ecm_equilibrium_gap",
    "ecm_feed_rate",
    "ecm_material_removal_rate",
]


def ecm_material_removal_rate(
    *, current: Quantity, equivalent_weight: float, density: Quantity
) -> Quantity:
    """The ECM volumetric removal rate, Q = I·EW/(ρ·F).

    The volume of metal dissolved per unit time by Faraday's law: the ``current`` I times the
    ``equivalent_weight`` EW (atomic weight over electrons transferred, g/equiv) over the
    ``density`` ρ and the Faraday constant F, so Q = I·EW/(ρ·F). It depends only on the charge
    passed, not on the metal's hardness — the reason ECM cuts hardened tool steel as fast as soft
    iron. Returns the removal rate in cm**3/min.
    """
    _check(current, "[current]", "current")
    _check(density, "[mass]/[length]**3", "density")
    if equivalent_weight <= 0:
        raise ValueError("equivalent_weight must be positive")
    amps = current.to("A").magnitude
    rho = density.to("g/cm**3").magnitude
    if amps < 0:
        raise ValueError("current must be non-negative")
    if rho <= 0:
        raise ValueError("density must be positive")
    q_cm3_per_s = amps * equivalent_weight / (rho * FARADAY_C_PER_MOL)
    return Quantity(magnitude=q_cm3_per_s * 60.0, unit="cm**3/min")


def ecm_feed_rate(
    *, current_density: Quantity, equivalent_weight: float, density: Quantity
) -> Quantity:
    """The ECM tool feed (penetration) rate, f = J·EW/(ρ·F).

    The speed the tool can advance into the work, the removal rate per unit of frontal area: the
    ``current_density`` J times the ``equivalent_weight`` EW (g/equiv) over the ``density`` ρ and
    the Faraday constant F, f = J·EW/(ρ·F). It is what a current density buys in penetration, and it
    sets the equilibrium gap the operation runs at (:func:`ecm_equilibrium_gap`). Returns the feed
    rate in mm/min.
    """
    _check(current_density, "[current]/[length]**2", "current_density")
    _check(density, "[mass]/[length]**3", "density")
    if equivalent_weight <= 0:
        raise ValueError("equivalent_weight must be positive")
    j = current_density.to("A/cm**2").magnitude
    rho = density.to("g/cm**3").magnitude
    if j < 0:
        raise ValueError("current_density must be non-negative")
    if rho <= 0:
        raise ValueError("density must be positive")
    f_cm_per_s = j * equivalent_weight / (rho * FARADAY_C_PER_MOL)
    return Quantity(magnitude=f_cm_per_s * 10.0 * 60.0, unit="mm/min")


def ecm_equilibrium_gap(
    *,
    electrolyte_conductivity: Quantity,
    applied_voltage: Quantity,
    feed_rate: Quantity,
    equivalent_weight: float,
    density: Quantity,
) -> Quantity:
    """The self-regulating ECM gap, g = κ·U·EW/(ρ·F·f).

    The steady tool-to-work gap an ECM cut settles at: the tool feeds at ``feed_rate`` f, and the
    gap adjusts until Ohm's law across the electrolyte — of ``electrolyte_conductivity`` κ at the
    ``applied_voltage`` U — draws exactly the current density that dissolves metal at f. Combining
    J = κ·U/g with Faraday's law (:func:`ecm_feed_rate`) gives g = κ·U·EW/(ρ·F·f), from the
    ``equivalent_weight`` EW and the ``density`` ρ. It is the process's self-limit: a faster feed
    forces a smaller gap, and pushed too far the gap closes to zero, the tool touches the work, and
    the electrolyte sparks into a short circuit. Returns the equilibrium gap in mm.
    """
    _check(electrolyte_conductivity, "[conductance]/[length]", "electrolyte_conductivity")
    _check(applied_voltage, "[electric_potential]", "applied_voltage")
    _check(feed_rate, "[length]/[time]", "feed_rate")
    _check(density, "[mass]/[length]**3", "density")
    if equivalent_weight <= 0:
        raise ValueError("equivalent_weight must be positive")
    kappa = electrolyte_conductivity.to("S/cm").magnitude
    u = applied_voltage.to("V").magnitude
    f_cm_per_s = feed_rate.to("cm/s").magnitude
    rho = density.to("g/cm**3").magnitude
    if kappa <= 0:
        raise ValueError("electrolyte_conductivity must be positive")
    if u <= 0:
        raise ValueError("applied_voltage must be positive")
    if f_cm_per_s <= 0:
        raise ValueError("feed_rate must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    g_cm = kappa * u * equivalent_weight / (rho * FARADAY_C_PER_MOL * f_cm_per_s)
    return Quantity(magnitude=g_cm * 10.0, unit="mm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
