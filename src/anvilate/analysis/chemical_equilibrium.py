"""T1 analytical chemical-equilibrium thermodynamics checks (closed-form).

Whether a reaction runs forward, and how far, is decided by the Gibbs free energy: the balance of
the enthalpy released against the entropy gained. A negative change means the reaction is
spontaneous, and its magnitude fixes the equilibrium constant — how lopsided the mix is at balance.
These are the thermodynamic partners to the reaction-rate view of
:mod:`anvilate.analysis.arrhenius` (which sets how *fast* equilibrium is reached) and the
electrochemical potential of :mod:`anvilate.analysis.nernst`.

The Gibbs free-energy change is ΔG = ΔH − T·ΔS, from the reaction enthalpy ΔH, the absolute
temperature T, and the reaction entropy ΔS. It ties to the equilibrium constant through
ΔG° = −R·T·ln(K), so K = exp(−ΔG/(R·T)) — a large negative ΔG gives a product-favored K ≫ 1. How K
shifts with temperature follows the van 't Hoff equation, K₂/K₁ = exp(−(ΔH/R)·(1/T₂ − 1/T₁)):
heating drives an endothermic reaction forward and an exothermic one back, as Le Chatelier's
principle requires. Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity`.

Sources: Smith, Van Ness & Abbott, *Introduction to Chemical Engineering Thermodynamics* — the
Gibbs free-energy change of a reaction, the equilibrium constant K = exp(-dG/RT) it gives, and
the van 't Hoff ratio between two temperatures.
"""

from __future__ import annotations

from math import exp

from ..units import Quantity

_GAS_CONSTANT = 8.314462618  # J/(mol*K), universal

__all__ = [
    "equilibrium_constant",
    "gibbs_free_energy_change",
    "vant_hoff_constant_ratio",
]


def gibbs_free_energy_change(
    *, enthalpy_change: Quantity, temperature: Quantity, entropy_change: Quantity
) -> Quantity:
    """The Gibbs free-energy change, ΔG = ΔH − T*ΔS.

    The driving force of a reaction, from the ``enthalpy_change`` ΔH, the absolute ``temperature``
    T, and the ``entropy_change`` ΔS: ΔG = ΔH − T*ΔS. A negative ΔG means the reaction is
    spontaneous forward; the entropy term grows with temperature, so heating can flip the sign.
    Returns the Gibbs free-energy change in J/mol.
    """
    _check(enthalpy_change, "[energy]/[substance]", "enthalpy_change")
    _check(temperature, "[temperature]", "temperature")
    _check(entropy_change, "[energy]/[substance]/[temperature]", "entropy_change")
    dh = enthalpy_change.to("J/mol").magnitude
    t = temperature.to("K").magnitude
    ds = entropy_change.to("J/(mol*K)").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    return Quantity(magnitude=dh - t * ds, unit="J/mol")


def equilibrium_constant(*, gibbs_free_energy_change: Quantity, temperature: Quantity) -> float:
    """The equilibrium constant, K = exp(-ΔG/(R*T)).

    The reaction's equilibrium constant, from the standard ``gibbs_free_energy_change`` ΔG° and the
    absolute ``temperature`` T, through ΔG° = −R*T*ln(K): K = exp(-ΔG/(R*T)). A negative ΔG gives
    K > 1 (products favored); a positive ΔG gives K < 1 (reactants favored). Returns the
    dimensionless equilibrium constant as a plain float.
    """
    _check(gibbs_free_energy_change, "[energy]/[substance]", "gibbs_free_energy_change")
    _check(temperature, "[temperature]", "temperature")
    dg = gibbs_free_energy_change.to("J/mol").magnitude
    t = temperature.to("K").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    return exp(-dg / (_GAS_CONSTANT * t))


def vant_hoff_constant_ratio(
    *, enthalpy_change: Quantity, temperature_low: Quantity, temperature_high: Quantity
) -> float:
    """The van 't Hoff constant ratio, K₂/K₁ = exp(-(ΔH/R)*(1/T₂ - 1/T₁)).

    How the equilibrium constant shifts between two temperatures, from the reaction
    ``enthalpy_change`` ΔH and the absolute ``temperature_low`` T₁ and ``temperature_high`` T₂:
    K₂/K₁ = exp(-(ΔH/R)*(1/T₂ - 1/T₁)). For an endothermic reaction (ΔH > 0) the ratio exceeds 1
    (heating favors products); for an exothermic one it drops below 1. Returns the K₂/K₁ ratio as a
    plain float.
    """
    _check(enthalpy_change, "[energy]/[substance]", "enthalpy_change")
    _check(temperature_low, "[temperature]", "temperature_low")
    _check(temperature_high, "[temperature]", "temperature_high")
    dh = enthalpy_change.to("J/mol").magnitude
    t1 = temperature_low.to("K").magnitude
    t2 = temperature_high.to("K").magnitude
    if t1 <= 0 or t2 <= 0:
        raise ValueError("temperatures must be positive (absolute temperature)")
    if t2 <= t1:
        raise ValueError("temperature_high must exceed temperature_low")
    return exp(-(dh / _GAS_CONSTANT) * (1.0 / t2 - 1.0 / t1))


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
