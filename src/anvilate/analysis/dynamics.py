"""T1 analytical modal screening (fundamental frequency, closed-form).

Resonance is a screening concern: a part whose fundamental natural frequency sits
near an operating excitation amplifies vibration. Two closed forms cover the
common cases:

* a single-degree-of-freedom system (a mass ``m`` on a support of stiffness
  ``k``) resonates at ``f_n = (1/2π)·√(k/m)``;
* a structure that deflects ``δ`` under its own weight has a fundamental frequency
  estimated by the Rayleigh relation ``f_n = (1/2π)·√(g/δ)`` — no separate mass or
  stiffness needed.

Inputs are dimension-checked :class:`~anvilate.units.Quantity` values; results are
returned in hertz.
"""

from __future__ import annotations

from math import pi, sqrt

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity

__all__ = [
    "STANDARD_GRAVITY",
    "natural_frequency",
    "natural_frequency_from_deflection",
    "frequency_scorecard",
]

# Standard gravitational acceleration (m/s²), for the Rayleigh self-weight estimate.
STANDARD_GRAVITY = Quantity(magnitude=9.80665, unit="m/s**2")


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def natural_frequency(*, stiffness: Quantity, mass: Quantity) -> Quantity:
    """The undamped natural frequency f_n = (1/2π)·√(k/m) of a mass-on-spring system.

    ``stiffness`` is the support stiffness k (force per unit length, e.g. a beam's
    load over its deflection); ``mass`` the supported mass m. Both must be
    positive. Returns the frequency in hertz.
    """
    _require(stiffness, "[force] / [length]", "stiffness")
    _require(mass, "[mass]", "mass")
    k = stiffness.to("N/m").magnitude
    m = mass.to("kg").magnitude
    if k <= 0 or m <= 0:
        raise ValueError("stiffness and mass must be positive")
    return Quantity(magnitude=sqrt(k / m) / (2 * pi), unit="Hz")


def natural_frequency_from_deflection(
    static_deflection: Quantity,
    *,
    gravity: Quantity = STANDARD_GRAVITY,
) -> Quantity:
    """The Rayleigh fundamental-frequency estimate f_n = (1/2π)·√(g/δ).

    ``static_deflection`` δ is the deflection the structure takes under its own
    weight; ``gravity`` defaults to standard g. Returns the frequency in hertz.
    The deflection must be positive.
    """
    _require(static_deflection, "[length]", "static_deflection")
    _require(gravity, "[acceleration]", "gravity")
    delta = static_deflection.to("m").magnitude
    g = gravity.to("m/s**2").magnitude
    if delta <= 0:
        raise ValueError(f"static_deflection must be positive; got {static_deflection}")
    return Quantity(magnitude=sqrt(g / delta) / (2 * pi), unit="Hz")


def frequency_scorecard(
    name: str,
    *,
    frequency: Quantity,
    min_frequency: Quantity | None,
) -> ScorecardEntry:
    """Screen a fundamental ``frequency`` against a required minimum for resonance.

    To avoid resonance a part's fundamental frequency should sit above the highest
    operating excitation, so this is ``PASS`` when ``frequency`` is at least
    ``min_frequency`` and ``FAIL`` below it. When ``min_frequency`` is ``None`` — no
    excitation requirement was declared — the entry is ``NOT_EVALUATED`` rather than
    a silent pass. Both quantities must be frequencies.
    """
    _require(frequency, "[frequency]", "frequency")
    if min_frequency is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — minimum frequency unavailable",
        )
    _require(min_frequency, "[frequency]", "min_frequency")
    fn = frequency.to("Hz").magnitude
    floor = min_frequency.to("Hz").magnitude
    status = CheckStatus.PASS if fn >= floor else CheckStatus.FAIL
    return ScorecardEntry(
        name=name,
        status=status,
        detail=f"fundamental {fn:.1f} Hz vs required minimum {floor:.1f} Hz",
    )
