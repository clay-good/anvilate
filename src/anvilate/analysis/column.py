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
