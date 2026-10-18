"""T1 thin-cylinder buckling with the NASA SP-8007 empirical knockdown factor.

A thin cylinder in axial compression buckles far below its classical stress — tests from
the 1930s to the 1960s fell to 15–60% of it, because a dimple a fraction of the wall
thick is enough to trigger collapse. NASA SP-8007 (*Buckling of Thin-Walled Circular
Cylinders*, 1965, revised 1968, and NASA/SP-8007-2020/REV 2) closes the gap with a
correlation factor γ fitted as a lower bound to that test data:

    axial compression   γ = 1 − 0.901·(1 − e^−φ)        (1968 Eq. 5; 2020 Eq. 9)
    bending             γ = 1 − 0.731·(1 − e^−φ)        (1968 Eq. 9; 2020 Eq. 14)
    with                φ = (1/16)·√(r/t),   r/t < 1500 (1968 Eq. 6; 2020 Eq. 10)

and the design buckling stress of a moderately long cylinder is γ times the classical
E·(t/r)/√(3(1 − ν²)) (1968 Eq. 4; 2020 Eq. 8), which
:func:`~anvilate.analysis.pressure_vessel.cylinder_axial_buckling_stress` computes.

The 2020 revision keeps these factors as its Empirical Approach, "likely to bound what is
expected in the design of aerospace-quality cylinders", and adds less conservative
semi-empirical and analysis-based approaches this module does not implement. Neither
edition attaches a probability to γ: it is a lower bound, not a statistical basis.

Ranges, as the documents state them. r/t ≥ 1500 is refused, because φ is defined only
below it and the bending data stop there. The fit's data spanned r/t from about 80 to
4150 and L/r from 0.5 to 5; above L/r of about 5 the documents say to use γ with
caution and to check column buckling and its interaction with the shell, which this
module leaves to the caller. Plasticity (1968 Eqs. 7–8) is not applied: the stress is
elastic, and above the proportional limit it is not the answer.
"""

from __future__ import annotations

from enum import StrEnum
from math import exp, sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from .pressure_vessel import cylinder_axial_buckling_stress

__all__ = [
    "CylinderLoading",
    "sp8007_knockdown_factor",
    "cylinder_design_buckling_stress",
]

_GEOMETRY_SOURCE = "the cylinder's drawing: mean radius and wall thickness"
_KNOCKDOWN = {"axial_compression": 0.901, "bending": 0.731}
_RT_LIMIT = 1500.0


class _ShellBucklingInputError(RefusalError, ValueError):
    """A shell-buckling input that cannot be used without correction."""


class CylinderLoading(StrEnum):
    """The two loadings NASA SP-8007 §4.2.1 and §4.2.2 give a knockdown factor for."""

    AXIAL_COMPRESSION = "axial_compression"
    BENDING = "bending"


def sp8007_knockdown_factor(*, radius_to_thickness: float, loading: CylinderLoading) -> float:
    """The NASA SP-8007 correlation factor γ for an unpressurized isotropic cylinder.

    γ = 1 − c·(1 − e^−φ), φ = √(r/t)/16, with c = 0.901 in axial compression and 0.731 in
    bending (1968 Eqs. 5, 6 and 9). ``radius_to_thickness`` is r/t; it must be positive
    and below 1500, where φ stops being defined. Returns γ, which falls from 1 toward 0.179
    (axial) and 0.334 (bending) as r/t approaches 1500.
    """
    if not isinstance(loading, CylinderLoading):
        raise _ShellBucklingInputError(
            f"loading must be a CylinderLoading; got {loading!r}",
            remedies=(Remedy(action="replace", subject="loading",
                             source="axial compression or bending"),),
        )  # fmt: skip
    ratio = require_finite(radius_to_thickness, name="radius_to_thickness")
    if not 0 < ratio < _RT_LIMIT:
        raise _ShellBucklingInputError(
            f"r/t = {ratio:g} is outside NASA SP-8007's knockdown, which defines φ = √(r/t)/16 "
            f"only for 0 < r/t < {_RT_LIMIT:g} (1968 Eq. 6); a thinner wall has no test data "
            "behind any knockdown here",
            remedies=(Remedy(action="replace", subject="radius_to_thickness",
                             source=_GEOMETRY_SOURCE),),
        )  # fmt: skip
    phi = sqrt(ratio) / 16.0
    return 1.0 - _KNOCKDOWN[loading.value] * (1.0 - exp(-phi))


def cylinder_design_buckling_stress(
    *,
    elastic_modulus: Quantity,
    wall_thickness: Quantity,
    mean_radius: Quantity,
    poisson: float,
    loading: CylinderLoading,
) -> Quantity:
    """The knocked-down elastic buckling stress of a thin cylinder (NASA SP-8007 §4.2.1).

    σ = γ·E·(t/r)/√(3(1 − ν²)): the classical stress of
    :func:`~anvilate.analysis.pressure_vessel.cylinder_axial_buckling_stress` (which
    refuses a wall too thick for shell buckling) times :func:`sp8007_knockdown_factor`.
    In bending this is the peak compressive fibre stress at buckling. Returned in MPa.
    """
    classical = cylinder_axial_buckling_stress(
        elastic_modulus=elastic_modulus,
        wall_thickness=wall_thickness,
        mean_radius=mean_radius,
        poisson=poisson,
    )
    ratio = mean_radius.to("mm").magnitude / wall_thickness.to("mm").magnitude
    gamma = sp8007_knockdown_factor(radius_to_thickness=ratio, loading=loading)
    return Quantity(magnitude=gamma * classical.to("MPa").magnitude, unit="MPa")
