"""T1 analytical acid-base buffer checks (Henderson-Hasselbalch, closed-form).

A buffer resists pH change because it holds a weak acid and its conjugate base together: add acid
and the base mops it up, add base and the acid neutralizes it. The Henderson-Hasselbalch equation
gives the pH of that mixture directly from the ratio of the two species,
pH = pKa + log₁₀([A⁻]/[HA]), where pKa is the acid's dissociation constant on a log scale, [A⁻] is
the conjugate-base concentration, and [HA] is the weak-acid concentration.

Two consequences fall straight out. When the two concentrations are equal the log term vanishes and
pH = pKa — the point of maximum buffering, which is why a buffer is chosen with a pKa near the
target pH. And inverting the relation gives the base-to-acid ratio a target pH demands,
[A⁻]/[HA] = 10^(pH − pKa), the recipe for mixing a buffer. Concentrations are dimension-checked
:class:`~anvilate.units.Quantity` values (only their ratio matters); pH, pKa, and the ratio are
plain floats.

Sources: Skoog, West & Holler, *Principles of Instrumental Analysis* (aqueous equilibria) — the
Henderson-Hasselbalch relation pH = pKa + log([A-]/[HA]) and the buffer ratio a target pH
requires.
"""

from __future__ import annotations

from math import log10

from ..units import Quantity

__all__ = [
    "buffer_ratio_for_ph",
    "henderson_hasselbalch_ph",
]


def henderson_hasselbalch_ph(
    *,
    pka: float,
    conjugate_base_concentration: Quantity,
    weak_acid_concentration: Quantity,
) -> float:
    """The buffer pH, pH = pKa + log₁₀([A⁻]/[HA]).

    The pH of a weak-acid buffer from the Henderson-Hasselbalch equation: the acid's ``pka`` plus
    the base-10 log of the ratio of the ``conjugate_base_concentration`` [A⁻] to the
    ``weak_acid_concentration`` [HA], pH = pKa + log₁₀([A⁻]/[HA]). Equal concentrations give
    pH = pKa (maximum buffering); more base raises the pH, more acid lowers it. Only the ratio of
    the two concentrations matters, so any consistent unit works. Returns the pH as a plain float.
    """
    _check(conjugate_base_concentration, "[substance]/[length]**3", "conjugate_base_concentration")
    _check(weak_acid_concentration, "[substance]/[length]**3", "weak_acid_concentration")
    base = conjugate_base_concentration.to("mol/L").magnitude
    acid = weak_acid_concentration.to("mol/L").magnitude
    if base <= 0:
        raise ValueError("conjugate_base_concentration must be positive")
    if acid <= 0:
        raise ValueError("weak_acid_concentration must be positive")
    return pka + log10(base / acid)


def buffer_ratio_for_ph(*, pka: float, ph: float) -> float:
    """The base-to-acid ratio for a target pH, [A⁻]/[HA] = 10^(pH − pKa).

    The ratio of conjugate base to weak acid a buffer needs to sit at a target ``ph``, inverting the
    Henderson-Hasselbalch equation (:func:`henderson_hasselbalch_ph`): [A⁻]/[HA] = 10^(``ph`` −
    ``pka``). A pH equal to the pKa needs a 1:1 ratio; each pH unit above multiplies the ratio by
    10. A buffer works well only within about ±1 pH unit of its pKa, where this ratio stays between
    ~0.1 and 10. Returns the dimensionless base-to-acid ratio as a plain float.
    """
    return 10.0 ** (ph - pka)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
