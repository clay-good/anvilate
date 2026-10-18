"""T1 plasticity corrections for column and plate buckling, from a Ramberg-Osgood curve.

Above the proportional limit a buckling formula written with E overstates the stress,
because the material is softer there than E says. The NASA Astronautic Structures Manual
(NASA TM X-73306, Vol. II, Section C2, 1971) corrects it with the tangent modulus E_t and
the secant modulus E_s of a Ramberg-Osgood description of the stress-strain curve, fitted
by two points: F_0.7 and F_0.85, the stresses where secant lines of slope 0.7E and 0.85E
meet the curve,

    ε = f/E + (3/7)·(F_0.7/E)·(f/F_0.7)ⁿ,    n = 1 + ln(17/7)/ln(F_0.7/F_0.85).

The manual prints the strain equation without the 3/7. That is a misprint: its own
definition of F_0.7 needs ε = (1/0.7)·F_0.7/E at f = F_0.7, which only the 3/7 gives, and
its own expression for n follows only from the equation with it. The tests hold the curve
to both definitions.

A column of slenderness λ = L′/ρ buckles at the stress σ where σ = π²E_t(σ)/λ² (the
tangent-modulus column). A long plate buckles at σ = η(σ)·σ_e, with σ_e its elastic
buckling stress and η the manual's plasticity reduction factor:

    edges rotationally restrained (Fig. C2-10):
        η = (E_s/2E)·{1 + 0.5·[1 + 3E_t/E_s]^(1/2)}·(1 − ν_e²)/(1 − ν²)
    hinged flanges (Fig. C2-11):
        η = (E_s/E)·(1 − ν_e²)/(1 − ν²)

ν_e is the Poisson ratio at the buckling stress, which the manual does not give a formula
for; it is the caller's, and taken equal to the elastic ν when not declared, which makes
the last factor 1 and is said on the result. Both equations are solved by bisection: the
right-hand side falls as σ rises, so each has one root below its elastic value.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from math import log, pi, sqrt

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import RevalidatedModel
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "RambergOsgood",
    "PlateEdge",
    "PlasticBuckling",
    "plastic_column_buckling_stress",
    "plastic_plate_buckling_stress",
]

_CURVE_SOURCE = "the material's compressive stress-strain curve: E, F_0.7 and F_0.85"


class _PlasticityInputError(RefusalError, ValueError):
    """A plasticity input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str) -> _PlasticityInputError:
    return _PlasticityInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _mpa(value: Quantity, name: str, source: str) -> float:
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a stress quantity; got {value!r}", subject=name,
                       source=source)  # fmt: skip
    try:
        magnitude = value.to("MPa").magnitude
    except Exception as error:
        raise _refusal(f"{name} is {value}, which is not a stress", subject=name,
                       source=source) from error  # fmt: skip
    magnitude = require_finite(magnitude, name=name)
    if magnitude <= 0:
        raise _refusal(f"{name} must be positive; got {value}", subject=name, source=source)
    return magnitude


class RambergOsgood(RevalidatedModel):
    """A Ramberg-Osgood stress-strain curve by E, F_0.7 and n (NASA TM X-73306 §C2, Eq. 2).

    Build it with :meth:`from_secant_points` from F_0.7 and F_0.85, which is how the
    manual fits it. Stresses are in MPa.
    """

    model_config = ConfigDict(frozen=True)

    elastic_modulus: float
    f_07: float
    n: float

    @model_validator(mode="after")
    def _a_curve(self) -> RambergOsgood:
        for name in ("elastic_modulus", "f_07"):
            value = require_finite(getattr(self, name), name=name)
            if value <= 0:
                raise _refusal(f"{name} must be positive", subject=name, source=_CURVE_SOURCE)
        if not require_finite(self.n, name="n") > 1:
            raise _refusal(
                f"n is {self.n}; a Ramberg-Osgood exponent above 1 is what makes the curve "
                "bend over, and F_0.85 below F_0.7 is what gives one",
                subject="n",
                source=_CURVE_SOURCE,
            )
        return self

    @classmethod
    def from_secant_points(
        cls, *, elastic_modulus: Quantity, f_07: Quantity, f_085: Quantity
    ) -> RambergOsgood:
        """The curve through the 0.7E and 0.85E secant points: n = 1 + ln(17/7)/ln(F_0.7/F_0.85)."""
        e = _mpa(elastic_modulus, "elastic_modulus", _CURVE_SOURCE)
        a = _mpa(f_07, "f_07", _CURVE_SOURCE)
        b = _mpa(f_085, "f_085", _CURVE_SOURCE)
        if not b < a:
            raise _refusal(
                f"F_0.85 = {b:g} MPa is not below F_0.7 = {a:g} MPa; the steeper secant meets "
                "the curve at the lower stress",
                subject="f_085",
                source=_CURVE_SOURCE,
            )
        return cls(elastic_modulus=e, f_07=a, n=1 + log(17 / 7) / log(a / b))

    def strain(self, stress: float) -> float:
        """ε at ``stress`` MPa: f/E + (3/7)(F_0.7/E)(f/F_0.7)ⁿ."""
        e, a = self.elastic_modulus, self.f_07
        return stress / e + (3 / 7) * (a / e) * float((stress / a) ** self.n)

    def secant_modulus(self, stress: float) -> float:
        """E_s = f/ε, in MPa."""
        return stress / self.strain(stress)

    def tangent_modulus(self, stress: float) -> float:
        """E_t = 1/(dε/df) = E/(1 + (3/7)·n·(f/F_0.7)^(n−1)), in MPa."""
        hardening = float((stress / self.f_07) ** (self.n - 1))
        return self.elastic_modulus / (1 + (3 / 7) * self.n * hardening)


class PlateEdge(StrEnum):
    """The two long-plate edge conditions NASA TM X-73306 §C2 gives η for."""

    ROTATIONALLY_RESTRAINED = "rotationally_restrained"
    HINGED_FLANGE = "hinged_flange"


class PlasticBuckling(BaseModel):
    """A plasticity-corrected buckling stress (NASA TM X-73306 §C2) and the moduli at it.

    Stresses and moduli in MPa; ``reduction`` is the corrected stress over the elastic.
    ``poisson_term_taken_as_one`` records that no plastic Poisson ratio was declared.
    """

    model_config = ConfigDict(frozen=True)

    stress: float
    elastic_stress: float
    reduction: float
    tangent_modulus: float
    secant_modulus: float
    poisson_term_taken_as_one: bool

    def __str__(self) -> str:
        note = "; ν_e taken as ν" if self.poisson_term_taken_as_one else ""
        return (
            f"plastic buckling {self.stress:.4g} MPa = {self.reduction:.3f} × elastic "
            f"{self.elastic_stress:.4g} MPa (E_t {self.tangent_modulus:.4g}, E_s "
            f"{self.secant_modulus:.4g} MPa{note}; NASA TM X-73306 §C2)"
        )


def _root(residual: Callable[[float], float], high: float) -> float:
    low = 0.0
    for _ in range(200):
        mid = (low + high) / 2
        if residual(mid) > 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def _curve(curve: object) -> RambergOsgood:
    if not isinstance(curve, RambergOsgood):
        raise _refusal("curve must be a RambergOsgood", subject="curve", source=_CURVE_SOURCE)
    return curve


def plastic_column_buckling_stress(*, curve: RambergOsgood, slenderness: float) -> PlasticBuckling:
    """The tangent-modulus column buckling stress (NASA TM X-73306 §C2): σ = π²E_t(σ)/λ².

    ``slenderness`` is the effective slenderness λ = L′/ρ, positive. The elastic Euler
    stress π²E/λ² is the upper bound; the root is found below it by bisection.
    """
    ro = _curve(curve)
    lam = require_finite(slenderness, name="slenderness")
    if lam <= 0:
        raise _refusal(f"slenderness is {lam}; L′/ρ is positive", subject="slenderness",
                       source="the column's effective length and radius of gyration")  # fmt: skip
    elastic = pi**2 * ro.elastic_modulus / lam**2
    stress = _root(lambda s: s - pi**2 * ro.tangent_modulus(s) / lam**2, elastic)
    return PlasticBuckling(
        stress=stress,
        elastic_stress=elastic,
        reduction=stress / elastic,
        tangent_modulus=ro.tangent_modulus(stress),
        secant_modulus=ro.secant_modulus(stress),
        poisson_term_taken_as_one=False,
    )


def plastic_plate_buckling_stress(
    *,
    curve: RambergOsgood,
    elastic_stress: Quantity,
    edge: PlateEdge,
    poisson: float,
    plastic_poisson: float | None = None,
) -> PlasticBuckling:
    """A long plate's buckling stress corrected by η (NASA TM X-73306 Figs. C2-10, C2-11).

    ``elastic_stress`` is the plate's elastic buckling stress kπ²E(t/b)²/(12(1 − ν²));
    the corrected stress solves σ = η(σ)·σ_e. ``plastic_poisson`` ν_e is the Poisson ratio
    at the buckling stress; left out, it is taken equal to ``poisson`` and the result says
    so. The cutoffs of the manual's Table C2-2 are not applied: they are per alloy.
    """
    ro = _curve(curve)
    if not isinstance(edge, PlateEdge):
        raise _refusal(f"edge must be a PlateEdge; got {edge!r}", subject="edge",
                       source="the plate's edge support")  # fmt: skip
    sigma_e = _mpa(elastic_stress, "elastic_stress", "the plate's elastic buckling stress")
    nu = require_finite(poisson, name="poisson")
    nu_e = (
        nu if plastic_poisson is None else require_finite(plastic_poisson, name="plastic_poisson")
    )
    for name, value in (("poisson", nu), ("plastic_poisson", nu_e)):
        if not 0 <= value <= 0.5:
            raise _refusal(f"{name} is {value}; a Poisson ratio lies in [0, 0.5]", subject=name,
                           source=_CURVE_SOURCE)  # fmt: skip
    poisson_term = (1 - nu_e**2) / (1 - nu**2)
    e = ro.elastic_modulus

    def eta(s: float) -> float:
        es, et = ro.secant_modulus(s), ro.tangent_modulus(s)
        if edge is PlateEdge.ROTATIONALLY_RESTRAINED:
            shape = es / (2 * e) * (1 + 0.5 * sqrt(1 + 3 * et / es))
        else:
            shape = es / e
        return shape * poisson_term

    stress = _root(lambda s: s - eta(s) * sigma_e, sigma_e * max(1.0, poisson_term))
    return PlasticBuckling(
        stress=stress,
        elastic_stress=sigma_e,
        reduction=stress / sigma_e,
        tangent_modulus=ro.tangent_modulus(stress),
        secant_modulus=ro.secant_modulus(stress),
        poisson_term_taken_as_one=plastic_poisson is None,
    )
