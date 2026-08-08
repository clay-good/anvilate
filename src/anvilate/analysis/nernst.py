"""T1 analytical Nernst-equation electrochemistry checks (closed-form).

The voltage of an electrochemical cell shifts from its standard value as the reactant and product
activities move away from unity — the Nernst equation. It sets the open-circuit voltage of a battery
as it discharges, the reading of a pH or ion-selective electrode, and the driving potential of a
corrosion cell. It complements the mass-transport side of the library — the Faraday deposition of
:mod:`anvilate.analysis.electroplating` and the metal loss of :mod:`anvilate.analysis.corrosion` —
with the potential that drives those currents.

The cell potential is E = E0 - (R*T/(n*F)) * ln(Q), from the standard potential E0, the absolute
temperature T, the number of electrons transferred n, the Faraday constant F, and the reaction
quotient Q (the activity ratio of products to reactants). Written per decade of Q it becomes the
Nernst slope 2.303*R*T/(n*F) — about 59 mV per decade for a one-electron reaction at 25 C, the
sensitivity of a potentiometric sensor. Inverting the relation recovers the reaction quotient (and
hence a concentration) a measured potential implies, Q = exp(n*F*(E0 - E)/(R*T)).

Temperatures are absolute (kelvin).
"""

from __future__ import annotations

from math import exp, log

from ..units import Quantity

_GAS_CONSTANT = 8.314462618  # J/(mol*K)
_FARADAY = 96485.33212  # C/mol
_LN10 = 2.302585092994046

__all__ = [
    "nernst_potential",
    "nernst_reaction_quotient",
    "nernst_slope",
]


def nernst_potential(
    *,
    standard_potential: Quantity,
    temperature: Quantity,
    electrons_transferred: int,
    reaction_quotient: float,
) -> Quantity:
    """The Nernst cell potential, E = E0 - (R*T/(n*F)) * ln(Q).

    The actual potential of a cell away from standard conditions: the ``standard_potential`` E0 less
    the Nernst term in the ``reaction_quotient`` Q at absolute ``temperature`` T, with
    ``electrons_transferred`` n. Q < 1 (excess reactant) raises the potential; Q > 1 lowers it. This
    is the open-circuit voltage of a cell at a given state of charge. Returns the potential in V.
    """
    _check(standard_potential, "[electric_potential]", "standard_potential")
    _check(temperature, "[temperature]", "temperature")
    e0 = standard_potential.to("V").magnitude
    t = temperature.to("K").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if electrons_transferred <= 0:
        raise ValueError("electrons_transferred must be a positive integer")
    if reaction_quotient <= 0:
        raise ValueError("reaction_quotient must be positive")
    e = e0 - (_GAS_CONSTANT * t / (electrons_transferred * _FARADAY)) * log(reaction_quotient)
    return Quantity(magnitude=e, unit="V")


def nernst_slope(*, temperature: Quantity, electrons_transferred: int) -> Quantity:
    """The Nernst slope per decade, 2.303*R*T/(n*F).

    The change in cell potential per tenfold change in the reaction quotient: 2.303*R*T/(n*F), from
    the absolute ``temperature`` T and ``electrons_transferred`` n. It is about 59 mV/decade for a
    one-electron reaction at 25 C — the calibration slope of a pH or ion-selective electrode, the
    sensitivity a potentiometric sensor achieves. Returns the slope in V (per decade).
    """
    _check(temperature, "[temperature]", "temperature")
    t = temperature.to("K").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if electrons_transferred <= 0:
        raise ValueError("electrons_transferred must be a positive integer")
    return Quantity(
        magnitude=_LN10 * _GAS_CONSTANT * t / (electrons_transferred * _FARADAY), unit="V"
    )


def nernst_reaction_quotient(
    *,
    standard_potential: Quantity,
    potential: Quantity,
    temperature: Quantity,
    electrons_transferred: int,
) -> float:
    """The reaction quotient from a measured potential, Q = exp(n*F*(E0 - E)/(R*T)).

    The sensor inverse of :func:`nernst_potential`: the ``reaction_quotient`` Q (an activity ratio,
    and hence a concentration) implied by a measured ``potential`` E relative to the
    ``standard_potential`` E0, at absolute ``temperature`` T with ``electrons_transferred`` n,
    Q = exp(n*F*(E0 - E)/(R*T)). It is how a potentiometric electrode turns a voltage into a
    concentration. Returns the reaction quotient as a plain float.
    """
    _check(standard_potential, "[electric_potential]", "standard_potential")
    _check(potential, "[electric_potential]", "potential")
    _check(temperature, "[temperature]", "temperature")
    e0 = standard_potential.to("V").magnitude
    e = potential.to("V").magnitude
    t = temperature.to("K").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if electrons_transferred <= 0:
        raise ValueError("electrons_transferred must be a positive integer")
    return exp(electrons_transferred * _FARADAY * (e0 - e) / (_GAS_CONSTANT * t))


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
