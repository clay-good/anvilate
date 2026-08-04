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
    infinite_slope_factor_of_safety,
    rankine_lateral_thrust,
    retaining_wall_overturning_factor,
    retaining_wall_sliding_factor,
    terzaghi_bearing_capacity,
)
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity

__all__ = [
    "InfiniteSlope",
    "RetainingWall",
    "ShallowFooting",
    "screen_infinite_slope",
    "screen_retaining_wall",
    "screen_shallow_footing",
]

_BEARING_REFERENCE = "Terzaghi bearing capacity with Vesić shape/depth factors"
_OVERTURNING_REFERENCE = "Rankine active thrust, moment balance about the toe"
_SLIDING_REFERENCE = "Rankine active thrust, base friction resistance"
_SLOPE_REFERENCE = "Infinite-slope limit equilibrium"


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


class RetainingWall(BaseModel):
    """A gravity/cantilever retaining wall and what its external-stability screen needs.

    The backfill is described by its ``retained_height`` H, ``backfill_unit_weight`` γ, and
    ``backfill_friction_angle`` φ, which set the Rankine active thrust (acting at H/3 above the
    base). The stabilizing side is given as a single resultant: the ``vertical_load`` V (the wall
    plus the soil on its heel, per unit length of wall) and its ``load_arm`` a to the toe, with the
    ``base_friction_coefficient`` μ between the base and the soil. Loads are per unit wall length.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    retained_height: Quantity
    backfill_unit_weight: Quantity
    backfill_friction_angle: float
    vertical_load: Quantity
    load_arm: Quantity
    base_friction_coefficient: float


def screen_retaining_wall(
    wall: RetainingWall,
    *,
    overturning_safety_factor: float = 2.0,
    sliding_safety_factor: float = 1.5,
) -> Scorecard:
    """Screen a :class:`RetainingWall` for external stability and return its scorecard.

    Computes the Rankine active thrust from the backfill, then screens the two classic
    external-stability limit states — overturning about the toe (against
    ``overturning_safety_factor``, usually 2.0) and sliding on the base (against
    ``sliding_safety_factor``, usually 1.5). Returns a :class:`~anvilate.scorecard.Scorecard` with a
    cited PASS/FAIL entry for each, no silent green.
    """
    thrust = rankine_lateral_thrust(
        unit_weight=wall.backfill_unit_weight,
        height=wall.retained_height,
        friction_angle=wall.backfill_friction_angle,
    )
    thrust_height = Quantity(
        magnitude=wall.retained_height.to("m").magnitude / 3.0, unit="m"
    )  # H/3 for the triangular pressure
    fs_overturning = retaining_wall_overturning_factor(
        lateral_thrust=thrust,
        thrust_height=thrust_height,
        vertical_load=wall.vertical_load,
        load_arm=wall.load_arm,
    )
    fs_sliding = retaining_wall_sliding_factor(
        lateral_thrust=thrust,
        vertical_load=wall.vertical_load,
        base_friction_coefficient=wall.base_friction_coefficient,
    )
    overturning = ScorecardEntry.from_safety_factor(
        "overturning", computed=fs_overturning, required=overturning_safety_factor
    ).model_copy(update={"reference": _OVERTURNING_REFERENCE})
    sliding = ScorecardEntry.from_safety_factor(
        "sliding", computed=fs_sliding, required=sliding_safety_factor
    ).model_copy(update={"reference": _SLIDING_REFERENCE})
    return Scorecard(entries=(overturning, sliding))


class InfiniteSlope(BaseModel):
    """A long, uniform (infinite) slope and what its stability screen needs.

    The failure plane runs parallel to the surface at ``depth`` z. The soil is described by its
    ``cohesion`` c, ``friction_angle`` φ (degrees), and ``unit_weight`` γ, and the ground by its
    ``slope_angle`` β (degrees). An optional ``pore_pressure`` u on the failure plane represents
    seepage after rain — the case that most often triggers failure; omit it for the dry slope.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    cohesion: Quantity
    friction_angle: float
    unit_weight: Quantity
    depth: Quantity
    slope_angle: float
    pore_pressure: Quantity | None = None


def screen_infinite_slope(
    slope: InfiniteSlope,
    *,
    required_safety_factor: float = 1.5,
) -> Scorecard:
    """Screen an :class:`InfiniteSlope` for sliding stability and return its scorecard.

    Computes the infinite-slope factor of safety (including any pore pressure) and screens it
    against ``required_safety_factor`` (1.5 is common for a permanent slope). Returns a
    :class:`~anvilate.scorecard.Scorecard` with a cited PASS/FAIL stability entry, no silent green.
    """
    factor_of_safety = infinite_slope_factor_of_safety(
        cohesion=slope.cohesion,
        friction_angle=slope.friction_angle,
        unit_weight=slope.unit_weight,
        depth=slope.depth,
        slope_angle=slope.slope_angle,
        pore_pressure=slope.pore_pressure,
    )
    entry = ScorecardEntry.from_safety_factor(
        "slope stability", computed=factor_of_safety, required=required_safety_factor
    ).model_copy(update={"reference": _SLOPE_REFERENCE})
    return Scorecard(entries=(entry,))
