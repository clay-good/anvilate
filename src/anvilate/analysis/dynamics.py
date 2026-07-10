"""T1 analytical modal screening (fundamental frequency, closed-form).

Resonance is a screening concern: a part whose fundamental natural frequency sits
near an operating excitation amplifies vibration. The closed forms cover the
common cases:

* a single-degree-of-freedom system (a mass ``m`` on a support of stiffness
  ``k``) resonates at ``f_n = (1/2π)·√(k/m)``;
* a structure that deflects ``δ`` under its own weight has a fundamental frequency
  estimated by the Rayleigh relation ``f_n = (1/2π)·√(g/δ)`` — no separate mass or
  stiffness needed;
* a prismatic beam with distributed mass has the exact Euler-Bernoulli
  fundamental ``f₁ = (λ₁²/2π)·√(E·I/(m̄·L⁴))``, one eigenvalue λ₁ per support
  condition (Blevins/Roark).

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
    "cantilever_fundamental_frequency",
    "simply_supported_fundamental_frequency",
    "fixed_fixed_fundamental_frequency",
    "fixed_pinned_fundamental_frequency",
    "frequency_scorecard",
]

# Standard gravitational acceleration (m/s²), for the Rayleigh self-weight estimate.
STANDARD_GRAVITY = Quantity(magnitude=9.80665, unit="m/s**2")

# First-mode Euler-Bernoulli eigenvalues λ₁², one per support condition, each the
# first root of the characteristic transcendental equation (verified by bisection
# to machine precision): cantilever cos·cosh = −1, simply supported sin = 0 (π),
# fixed-fixed cos·cosh = 1, fixed-pinned tan = tanh.
_LAMBDA_SQ_CANTILEVER = 3.5160152685
_LAMBDA_SQ_SIMPLY_SUPPORTED = pi**2
_LAMBDA_SQ_FIXED_FIXED = 22.3732854481
_LAMBDA_SQ_FIXED_PINNED = 15.4182057170


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


def _beam_fundamental(
    lambda_sq: float,
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    _require(mass_per_length, "[mass] / [length]", "mass_per_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    m = mass_per_length.to("kg/m").magnitude
    length_m = length.to("m").magnitude
    inertia = second_moment.to("m**4").magnitude
    e = elastic_modulus.to("Pa").magnitude
    if m <= 0 or length_m <= 0 or inertia <= 0 or e <= 0:
        raise ValueError("mass_per_length, length, second_moment, and E must be positive")
    return Quantity(
        magnitude=lambda_sq * sqrt(e * inertia / (m * length_m**4)) / (2 * pi), unit="Hz"
    )


def cantilever_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a cantilever with distributed mass (Blevins).

    Exact Euler-Bernoulli first mode f₁ = (λ₁²/2π)·√(E·I/(m̄·L⁴)) with
    λ₁² = 3.51602 (the first root of cos λ·cosh λ = −1). ``mass_per_length``
    m̄ is the beam's mass per unit length, self-weight plus any smeared
    attachments. Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_CANTILEVER,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def simply_supported_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a simply-supported beam with distributed mass.

    Exact Euler-Bernoulli first mode f₁ = (π²/2π)·√(E·I/(m̄·L⁴)) — the one
    support with a clean closed-form eigenvalue (λ₁ = π). Exceeds the Rayleigh
    self-weight estimate from the mid-span deflection by exactly
    π²/√(384/5) ≈ 1.126. Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_SIMPLY_SUPPORTED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def fixed_fixed_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a fixed-fixed beam with distributed mass.

    Exact Euler-Bernoulli first mode with λ₁² = 22.37329 (the first root of
    cos λ·cosh λ = 1) — building in both ends raises the fundamental 2.27×
    over the simply-supported span. Returns hertz; every argument is
    dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_FIXED_FIXED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def fixed_pinned_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a propped cantilever with distributed mass.

    Exact Euler-Bernoulli first mode with λ₁² = 15.41821 (the first root of
    tan λ = tanh λ), between the simply-supported and fixed-fixed values.
    Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_FIXED_PINNED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


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
