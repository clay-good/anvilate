"""The geotechnical discipline pack: declare a footing, get a bearing scorecard.

The geotechnical pack serves the foundation engineer's shallow-footing check the way
:mod:`anvilate.packs.structural` serves AISC members and :mod:`anvilate.packs.industrial` serves
flat covers. A :class:`ShallowFooting` declares a footing's plan size, embedment, applied load, and
the supporting soil; :func:`screen_shallow_footing` builds the full Terzaghi bearing capacity —
corrected by the Vesić shape and depth factors for the real (rectangular, embedded) footing — and
screens it against the applied bearing pressure with a global factor of safety. "No silent green"
carries through: the entry is ``NOT_EVALUATED`` if the capacity cannot be found, and it cites the
theory it implements. Bearing capacity is a screening estimate from classical soil mechanics, not a
building-code check — the geotechnical engineer of record owns the design.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from ..analysis import (
    bearing_capacity_factors,
    bearing_depth_factors,
    bearing_shape_factors,
    terzaghi_bearing_capacity,
)
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity

__all__ = [
    "ShallowFooting",
    "screen_shallow_footing",
]

_BEARING_REFERENCE = "Terzaghi bearing capacity with Vesić shape/depth factors"


class ShallowFooting(BaseModel):
    """A rectangular shallow spread footing on c-φ soil, and what its bearing screen needs.

    ``width`` B (the shorter plan side) and ``length`` L set the footing plan; ``embedment_depth``
    D_f is its founding depth below grade (which supplies the surcharge q = γ·D_f and the depth
    factors). ``applied_load`` is the total vertical service load it carries. The soil is described
    by its ``friction_angle`` φ (degrees), ``cohesion`` c, and ``unit_weight`` γ. A validator keeps
    the width from exceeding the length.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    width: Quantity
    length: Quantity
    embedment_depth: Quantity
    applied_load: Quantity
    friction_angle: float
    cohesion: Quantity
    unit_weight: Quantity

    @model_validator(mode="after")
    def _check_geometry(self) -> ShallowFooting:
        b = self.width.to("m").magnitude
        lo = self.length.to("m").magnitude
        if b <= 0 or lo <= 0:
            raise ValueError("width and length must be positive")
        if b > lo:
            raise ValueError("width must be the shorter side (B <= L)")
        return self


def screen_shallow_footing(
    footing: ShallowFooting,
    *,
    required_safety_factor: float = 3.0,
) -> Scorecard:
    """Screen a :class:`ShallowFooting` for bearing capacity and return its scorecard.

    Builds the shape/depth-corrected Terzaghi ultimate bearing pressure q_ult, computes the applied
    contact pressure q = P/(B·L), and screens their ratio against ``required_safety_factor`` (3 is
    the usual value for shallow foundations). Returns a :class:`~anvilate.scorecard.Scorecard` with
    one bearing-capacity entry — ``PASS``/``FAIL`` with no silent green — citing the theory.
    """
    b = footing.width.to("m").magnitude
    lo = footing.length.to("m").magnitude
    load = footing.applied_load.to("kN").magnitude
    gamma = footing.unit_weight.to("kN/m**3").magnitude
    depth = footing.embedment_depth.to("m").magnitude

    factors = bearing_capacity_factors(friction_angle=footing.friction_angle)
    shape = bearing_shape_factors(
        footing_width=footing.width,
        footing_length=footing.length,
        friction_angle=footing.friction_angle,
        bearing_factor_nq=factors["N_q"],
        bearing_factor_nc=factors["N_c"],
    )
    depth_factors = bearing_depth_factors(
        footing_width=footing.width,
        embedment_depth=footing.embedment_depth,
        friction_angle=footing.friction_angle,
    )
    surcharge = Quantity(magnitude=gamma * depth, unit="kPa")  # q = γ·D_f
    q_ult = (
        terzaghi_bearing_capacity(
            cohesion=footing.cohesion,
            surcharge=surcharge,
            unit_weight=footing.unit_weight,
            width=footing.width,
            bearing_factor_c=factors["N_c"] * shape["s_c"] * depth_factors["d_c"],
            bearing_factor_q=factors["N_q"] * shape["s_q"] * depth_factors["d_q"],
            bearing_factor_gamma=factors["N_gamma"] * shape["s_gamma"] * depth_factors["d_gamma"],
        )
        .to("kPa")
        .magnitude
    )

    applied_pressure = load / (b * lo)  # kN/m^2 = kPa
    safety_factor = q_ult / applied_pressure if applied_pressure > 0 else None
    entry = ScorecardEntry.from_safety_factor(
        "bearing capacity",
        computed=safety_factor,
        required=required_safety_factor,
    )
    entry = entry.model_copy(update={"reference": _BEARING_REFERENCE})
    return Scorecard(entries=(entry,))
