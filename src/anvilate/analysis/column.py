"""T1 analytical column-buckling checks (Euler + Johnson, closed-form).

A slender compression member fails by elastic buckling well below its yield
load. The Euler critical load ``P_cr = π²·E·I/(K·L)²`` is the classic screening
check (Roark / Shigley): ``E`` the Young's modulus, ``I`` the least section
second moment, ``L`` the unbraced length, and ``K`` the effective-length factor
set by the end conditions. Intermediate (stubbier) columns, below the transition
slenderness λ₁, fail inelastically and are screened with the J. B. Johnson
parabola instead. As with the beam checks, inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values and the arithmetic
runs through Pint.

These are screening checks — they assume an ideal, initially-straight,
concentrically-loaded prismatic column.
"""

from __future__ import annotations

from enum import StrEnum
from math import cos, pi, sqrt

from ..units import Quantity

__all__ = [
    "ColumnEnd",
    "euler_buckling_load",
    "radius_of_gyration",
    "slenderness_ratio",
    "euler_critical_stress",
    "transition_slenderness",
    "johnson_critical_stress",
    "secant_column_max_stress",
]


class ColumnEnd(StrEnum):
    """Standard end-condition cases and their theoretical effective-length factor
    K, exposed via :meth:`factor`."""

    PINNED_PINNED = "pinned_pinned"
    FIXED_FIXED = "fixed_fixed"
    FIXED_PINNED = "fixed_pinned"
    FIXED_FREE = "fixed_free"

    def factor(self) -> float:
        """The theoretical effective-length factor K for this end condition."""
        return {
            ColumnEnd.PINNED_PINNED: 1.0,
            ColumnEnd.FIXED_FIXED: 0.5,
            ColumnEnd.FIXED_PINNED: 0.7,
            ColumnEnd.FIXED_FREE: 2.0,
        }[self]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def euler_buckling_load(
    *,
    elastic_modulus: Quantity,
    second_moment: Quantity,
    length: Quantity,
    effective_length_factor: float = 1.0,
) -> Quantity:
    """The Euler critical buckling load P_cr = π²·E·I/(K·L)².

    ``elastic_modulus`` is Young's modulus, ``second_moment`` the least section
    second moment I (buckling occurs about the weak axis), ``length`` the unbraced
    length L, and ``effective_length_factor`` the end-condition factor K (1.0 for
    pinned-pinned; see :class:`ColumnEnd` for the standard cases). Returns the
    critical load as a force. Every quantity argument is dimension-checked and
    ``effective_length_factor`` must be positive.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(second_moment, "[length]**4", "second_moment")
    _require(length, "[length]", "length")
    if effective_length_factor <= 0:
        raise ValueError(f"effective_length_factor must be positive; got {effective_length_factor}")

    e = elastic_modulus.pint
    inertia = second_moment.pint
    effective_length = effective_length_factor * length.pint
    p_cr = pi**2 * e * inertia / effective_length**2
    converted = p_cr.to("N")
    return Quantity(magnitude=float(converted.magnitude), unit="N")


def radius_of_gyration(*, second_moment: Quantity, area: Quantity) -> Quantity:
    """The radius of gyration r = √(I/A) of a section — the length that governs
    slenderness. ``second_moment`` is the least I; ``area`` the cross-section."""
    _require(second_moment, "[length]**4", "second_moment")
    _require(area, "[length]**2", "area")
    r = (second_moment.pint / area.pint) ** 0.5
    converted = r.to("mm")
    return Quantity(magnitude=float(converted.magnitude), unit="mm")


def slenderness_ratio(*, effective_length: Quantity, radius_of_gyration: Quantity) -> float:
    """The slenderness ratio λ = K·L/r (dimensionless).

    ``effective_length`` is the already-factored length K·L; ``radius_of_gyration``
    is r. A high λ marks a long column that fails by Euler buckling; a low λ a
    stubby one where inelastic (Johnson) failure governs instead.
    """
    _require(effective_length, "[length]", "effective_length")
    _require(radius_of_gyration, "[length]", "radius_of_gyration")
    return effective_length.to("mm").magnitude / radius_of_gyration.to("mm").magnitude


def euler_critical_stress(*, elastic_modulus: Quantity, slenderness_ratio: float) -> Quantity:
    """The Euler critical (buckling) stress σ_cr = π²·E/λ².

    The critical load divided by the section area, expressed through the
    slenderness ratio λ. ``slenderness_ratio`` must be positive. Returns a stress.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if slenderness_ratio <= 0:
        raise ValueError(f"slenderness_ratio must be positive; got {slenderness_ratio}")
    sigma = pi**2 * elastic_modulus.pint / slenderness_ratio**2
    converted = sigma.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def transition_slenderness(*, yield_strength: Quantity, elastic_modulus: Quantity) -> float:
    """The Euler–Johnson transition slenderness λ₁ = π·√(2E/S_y).

    Columns with slenderness above λ₁ buckle elastically (Euler); shorter ones
    fail inelastically and are screened with the Johnson parabola
    (:func:`johnson_critical_stress`). At λ₁ the two curves meet at σ = S_y/2.
    """
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    sy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if sy <= 0:
        raise ValueError(f"yield_strength must be positive; got {yield_strength}")
    return pi * (2 * e / sy) ** 0.5


def johnson_critical_stress(
    *,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
    slenderness_ratio: float,
) -> Quantity:
    """The J. B. Johnson critical stress σ_cr = S_y·[1 − S_y·λ²/(4π²·E)] for an
    intermediate column.

    The parabolic inelastic-buckling curve tangent to the Euler curve at the
    transition slenderness λ₁ (:func:`transition_slenderness`). Valid for
    ``slenderness_ratio`` up to λ₁; above it, use :func:`euler_critical_stress`.
    ``slenderness_ratio`` must be positive.
    """
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if slenderness_ratio <= 0:
        raise ValueError(f"slenderness_ratio must be positive; got {slenderness_ratio}")
    sy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    sigma = sy * (1 - sy * slenderness_ratio**2 / (4 * pi**2 * e))
    return Quantity(magnitude=sigma, unit="MPa")


def secant_column_max_stress(
    *,
    load: Quantity,
    eccentricity: Quantity,
    area: Quantity,
    second_moment: Quantity,
    extreme_fiber: Quantity,
    length: Quantity,
    elastic_modulus: Quantity,
    effective_length_factor: float = 1.0,
) -> Quantity:
    """The secant-formula peak stress of an eccentrically loaded column.

    A pin-ended column whose axial ``load`` P acts at ``eccentricity`` e from
    the centroid bends as it compresses, and the bending feeds back: the exact
    beam-column solution is σ_max = (P/A)·[1 + (e·c/r²)·sec((KL/2r)·√(P/(E·A)))]
    — the P-δ amplified counterpart of the naive P/A + P·e·c/I, which it
    recovers as P → 0 and exceeds at any real load (verified against an
    independent finite-difference beam-column solve). The secant blows up at
    the Euler load, so P must sit below P_cr for the effective length — a
    load at or beyond it raises rather than returning a meaningless number.
    Every quantity argument is dimension-checked and must be positive.
    """
    _require(load, "[force]", "load")
    _require(eccentricity, "[length]", "eccentricity")
    _require(area, "[length]**2", "area")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fiber, "[length]", "extreme_fiber")
    _require(length, "[length]", "length")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if effective_length_factor <= 0:
        raise ValueError(f"effective_length_factor must be positive; got {effective_length_factor}")
    p = load.to("N").magnitude
    e_ecc = eccentricity.to("m").magnitude
    a = area.to("m**2").magnitude
    inertia = second_moment.to("m**4").magnitude
    c = extreme_fiber.to("m").magnitude
    modulus = elastic_modulus.to("Pa").magnitude
    kl = effective_length_factor * length.to("m").magnitude
    if min(p, e_ecc, a, inertia, c, kl, modulus) <= 0:
        raise ValueError("every secant-formula input must be positive")

    p_euler = pi**2 * modulus * inertia / kl**2
    if p >= p_euler:
        raise ValueError(
            f"load ({load}) is at or beyond the Euler critical load "
            f"({p_euler / 1000:.2f} kN for this effective length) — the secant "
            "amplification diverges; treat this as a buckling failure, not a stress"
        )
    r_sq = inertia / a
    secant = 1 / cos(kl / 2 * sqrt(p / (modulus * inertia)))
    sigma = p / a * (1 + e_ecc * c / r_sq * secant)
    return Quantity(magnitude=sigma / 1e6, unit="MPa")
