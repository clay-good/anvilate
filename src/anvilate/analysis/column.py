"""T1 analytical column-buckling check (Euler, closed-form).

A slender compression member fails by elastic buckling well below its yield
load. The Euler critical load ``P_cr = π²·E·I/(K·L)²`` is the classic screening
check (Roark / Shigley): ``E`` the Young's modulus, ``I`` the least section
second moment, ``L`` the unbraced length, and ``K`` the effective-length factor
set by the end conditions. As with the beam checks, inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values and the arithmetic
runs through Pint.

This is a screening check — it assumes an ideal, initially-straight, concentrically-
loaded prismatic column in the elastic range, and does not cover inelastic
(Johnson) buckling of stubbier columns.
"""

from __future__ import annotations

from enum import StrEnum
from math import pi

from ..units import Quantity

__all__ = [
    "ColumnEnd",
    "euler_buckling_load",
    "radius_of_gyration",
    "slenderness_ratio",
    "euler_critical_stress",
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
