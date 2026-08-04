"""T1 analytical building code design loads (ASCE 7 wind and seismic, closed-form).

The rest of the library checks whether a member *resists* its load; this module supplies the
*load* itself from the two governing environmental hazards, following ASCE 7's closed forms. Every
site- and building-specific coefficient (exposure, topography, directionality, gust, pressure, and
seismic response factors) is a value the caller looks up in the standard's tables — this module does
the arithmetic that turns them into a pressure or a base shear, not the table lookups.

**Wind.** The velocity pressure is the wind's dynamic pressure with the air density folded into the
constant, qz = 0.613·Kz·Kzt·Kd·Ke·V² (SI, V in m/s → qz in Pa; the 0.613 is ½·ρ_air). The design
pressure on a surface is that velocity pressure scaled by the gust-effect factor and the surface's
pressure coefficient, p = qz·G·Cp.

**Seismic.** The equivalent lateral force method reduces the earthquake to a base shear V = Cs·W,
where the seismic weight W is resisted in proportion to the response coefficient Cs = SDS·Ie/R (the
design spectral acceleration, scaled up by importance and down by the system's ductility R). ASCE 7
also caps Cs above and below (by SD1/T and the 0.044·SDS·Ie floor) — those bounds need the building
period and are the caller's to apply; this is the base §12.8.1.1 value.

**Snow.** The flat-roof snow load is the ground snow discounted for the roof's exposure, warmth, and
occupancy, pf = 0.7·Ce·Ct·Is·pg, and a pitched roof sheds part of it through the slope factor,
ps = Cs·pf.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

from ..units import Quantity

__all__ = [
    "wind_velocity_pressure",
    "wind_design_pressure",
    "seismic_response_coefficient",
    "seismic_base_shear",
    "seismic_vertical_force_distribution",
    "seismic_design_story_drift",
    "allowable_story_drift",
    "seismic_stability_coefficient",
    "seismic_stability_coefficient_limit",
    "seismic_load_effect",
    "flat_roof_snow_load",
    "sloped_roof_snow_load",
    "reduced_live_load",
    "rain_load",
]

_LIVE_LOAD_REDUCTION_CONSTANT = 4.57  # ASCE 7 Eq 4.7-1 (SI), = 15/sqrt(0.0929 m^2/ft^2)
_LIVE_LOAD_REDUCTION_THRESHOLD = 37.16  # m^2 (= 400 ft^2); no reduction below this KLL*AT
_RAIN_LOAD_CONSTANT = 0.0098  # ASCE 7 Eq 8.3-1 (SI): unit weight of water in kPa per mm of head

_VELOCITY_PRESSURE_CONSTANT = 0.613  # = 1/2 * rho_air (1.225 kg/m^3), SI ASCE 7 form
_FLAT_ROOF_SNOW_CONSTANT = 0.7  # ASCE 7 Eq 7.3-1 exposure/thermal baseline


def wind_velocity_pressure(
    *,
    basic_wind_speed: Quantity,
    exposure_coefficient: float,
    topographic_factor: float = 1.0,
    directionality_factor: float = 0.85,
    ground_elevation_factor: float = 1.0,
) -> Quantity:
    """The ASCE 7 velocity pressure qz = 0.613·Kz·Kzt·Kd·Ke·V² (SI).

    The wind's dynamic pressure at height, with the air density folded into the 0.613 constant
    (½·ρ_air). ``basic_wind_speed`` V is the 3-second gust design speed, ``exposure_coefficient`` Kz
    the velocity-pressure exposure coefficient (from the terrain category and height),
    ``topographic_factor`` Kzt the speed-up over hills and escarpments (1 on flat ground),
    ``directionality_factor`` Kd the wind-direction factor (0.85 for buildings), and
    ``ground_elevation_factor`` Ke the elevation adjustment (1 at sea level). All are ASCE 7 table
    values. Scale the result by the gust factor and pressure coefficient with
    :func:`wind_design_pressure`. Returns the velocity pressure in Pa.
    """
    _check(basic_wind_speed, "[length]/[time]", "basic_wind_speed")
    v = basic_wind_speed.to("m/s").magnitude
    if v <= 0:
        raise ValueError("basic_wind_speed must be positive")
    for name, value in (
        ("exposure_coefficient", exposure_coefficient),
        ("topographic_factor", topographic_factor),
        ("directionality_factor", directionality_factor),
        ("ground_elevation_factor", ground_elevation_factor),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    qz = (
        _VELOCITY_PRESSURE_CONSTANT
        * exposure_coefficient
        * topographic_factor
        * directionality_factor
        * ground_elevation_factor
        * v**2
    )
    return Quantity(magnitude=qz, unit="Pa")


def wind_design_pressure(
    *,
    velocity_pressure: Quantity,
    gust_effect_factor: float,
    pressure_coefficient: float,
) -> Quantity:
    """The ASCE 7 design wind pressure on a surface, p = qz·G·Cp.

    The net pressure a surface actually feels: the ``velocity_pressure`` qz (from
    :func:`wind_velocity_pressure`) scaled by the ``gust_effect_factor`` G (0.85 for a rigid
    building) and the ``pressure_coefficient`` Cp for that surface (positive for a windward wall
    pushed in, negative for a leeward wall or roof sucked out — an ASCE 7 table value that carries
    its own sign). A negative result is a net suction. Returns the design pressure in Pa.
    """
    _check(velocity_pressure, "[pressure]", "velocity_pressure")
    qz = velocity_pressure.to("Pa").magnitude
    if qz <= 0:
        raise ValueError("velocity_pressure must be positive")
    if gust_effect_factor <= 0:
        raise ValueError(f"gust_effect_factor must be positive; got {gust_effect_factor}")
    return Quantity(magnitude=qz * gust_effect_factor * pressure_coefficient, unit="Pa")


def seismic_response_coefficient(
    *,
    design_spectral_acceleration: float,
    response_modification_factor: float,
    importance_factor: float = 1.0,
) -> float:
    """The ASCE 7 seismic response coefficient Cs = SDS·Ie/R (§12.8.1.1).

    The fraction of a structure's weight taken as an equivalent static earthquake force.
    ``design_spectral_acceleration`` SDS is the short-period design spectral acceleration (in g),
    ``response_modification_factor`` R the seismic system's ductility/overstrength factor (larger
    for a more ductile system, which is allowed to yield and so is designed for less force), and
    ``importance_factor`` Ie the occupancy importance factor. This is the base value; ASCE 7 caps it
    above (by SD1/(T·R/Ie)) and below (the 0.044·SDS·Ie floor), which need the building period and
    are the caller's to apply. Returns the dimensionless Cs.
    """
    if design_spectral_acceleration <= 0:
        raise ValueError("design_spectral_acceleration must be positive")
    if response_modification_factor <= 0:
        raise ValueError("response_modification_factor must be positive")
    if importance_factor <= 0:
        raise ValueError("importance_factor must be positive")
    return design_spectral_acceleration * importance_factor / response_modification_factor


def seismic_base_shear(
    *,
    seismic_weight: Quantity,
    response_coefficient: float,
) -> Quantity:
    """The ASCE 7 seismic base shear V = Cs·W (§12.8.1).

    The total equivalent lateral earthquake force at the base of a structure: its effective
    ``seismic_weight`` W (dead load plus the code's fraction of other loads) times the
    ``response_coefficient`` Cs from :func:`seismic_response_coefficient`. This shear is then
    distributed up the height to each level. Returns the base shear in kN.
    """
    _check(seismic_weight, "[force]", "seismic_weight")
    w = seismic_weight.to("kN").magnitude
    if w <= 0:
        raise ValueError("seismic_weight must be positive")
    if response_coefficient <= 0:
        raise ValueError(f"response_coefficient must be positive; got {response_coefficient}")
    return Quantity(magnitude=w * response_coefficient, unit="kN")


def seismic_vertical_force_distribution(
    *,
    base_shear: Quantity,
    story_weights: Sequence[Quantity],
    story_heights: Sequence[Quantity],
    distribution_exponent: float = 1.0,
) -> tuple[Quantity, ...]:
    """The ASCE 7 vertical distribution of base shear, Fx = V·wx·hx^k/Σ(wi·hi^k) (§12.8.3).

    The base shear from :func:`seismic_base_shear` is not applied at the base but shared out to the
    floors, each level x taking a fraction Cvx = wx·hx^k / Σ(wi·hi^k) of it. ``base_shear`` V is the
    total, ``story_weights`` wx and ``story_heights`` hx the effective weight and the height above
    the base of each level (same length, ordered consistently), and ``distribution_exponent`` k the
    period-dependent exponent (1 for a short-period T ≤ 0.5 s building, 2 for a long-period
    T ≥ 2.5 s one, interpolated between — the caller's from the period). The k > 1 exponent throws
    more of the force to the upper floors, where a tall building's whipping does the damage. The
    returned forces sum to the base shear. Returns a tuple of level forces in kN, one per story.
    """
    _check(base_shear, "[force]", "base_shear")
    v = base_shear.to("kN").magnitude
    if v <= 0:
        raise ValueError("base_shear must be positive")
    if len(story_weights) != len(story_heights):
        raise ValueError("story_weights and story_heights must have the same length")
    if len(story_weights) == 0:
        raise ValueError("at least one story is required")
    if distribution_exponent <= 0:
        raise ValueError("distribution_exponent must be positive")
    products = []
    for i, (w, h) in enumerate(zip(story_weights, story_heights, strict=True)):
        _check(w, "[force]", f"story_weights[{i}]")
        _check(h, "[length]", f"story_heights[{i}]")
        wm = w.to("kN").magnitude
        hm = h.to("m").magnitude
        if wm <= 0 or hm <= 0:
            raise ValueError("every story weight and height must be positive")
        products.append(wm * hm**distribution_exponent)
    total = sum(products)
    return tuple(Quantity(magnitude=v * p / total, unit="kN") for p in products)


def seismic_design_story_drift(
    *,
    elastic_story_drift: Quantity,
    deflection_amplification_factor: float,
    importance_factor: float = 1.0,
) -> Quantity:
    """The ASCE 7 design story drift Δ = Cd·δxe/Ie (§12.8.6).

    A seismic analysis is run with the *reduced* design forces (the base shear already divided by
    R), so the story deflections it produces, ``elastic_story_drift`` δxe, are only a fraction of
    what the structure will really sway when it yields. ASCE 7 recovers the expected inelastic drift
    by scaling that elastic value up by the ``deflection_amplification_factor`` Cd (a system trait,
    close to R) and down by the ``importance_factor`` Ie: Δ = Cd·δxe/Ie. This is the drift to check
    against :func:`allowable_story_drift` — using the raw elastic δxe understates the real sway by
    the factor Cd, a common and unconservative error. Returns the amplified design drift in mm.
    """
    _check(elastic_story_drift, "[length]", "elastic_story_drift")
    dxe = elastic_story_drift.to("mm").magnitude
    if dxe < 0:
        raise ValueError("elastic_story_drift must be non-negative")
    if deflection_amplification_factor <= 0:
        raise ValueError("deflection_amplification_factor must be positive")
    if importance_factor <= 0:
        raise ValueError("importance_factor must be positive")
    return Quantity(magnitude=deflection_amplification_factor * dxe / importance_factor, unit="mm")


def allowable_story_drift(
    *,
    story_height: Quantity,
    drift_limit_ratio: float,
) -> Quantity:
    """The ASCE 7 allowable story drift Δa = ratio·hsx (Table 12.12-1).

    The sway a story is permitted, as a fraction of its height: ``drift_limit_ratio`` (0.020·hsx for
    most buildings, tighter for brittle cladding or essential facilities, looser for low masonry)
    times the ``story_height`` hsx. Compare the design drift from :func:`seismic_design_story_drift`
    against this — a drift within the limit protects the cladding, partitions, and P-delta
    stability. Returns the allowable drift in mm.
    """
    _check(story_height, "[length]", "story_height")
    h = story_height.to("mm").magnitude
    if h <= 0:
        raise ValueError("story_height must be positive")
    if drift_limit_ratio <= 0:
        raise ValueError("drift_limit_ratio must be positive")
    return Quantity(magnitude=drift_limit_ratio * h, unit="mm")


def seismic_stability_coefficient(
    *,
    story_gravity_load: Quantity,
    design_story_drift: Quantity,
    story_shear: Quantity,
    story_height: Quantity,
    deflection_amplification_factor: float,
) -> float:
    """The ASCE 7 P-delta stability coefficient θ = Pₓ·Δ/(Vₓ·hsx·Cd) (§12.8.7).

    When a swaying story carries gravity load, that weight acting through the sway adds an
    overturning demand the first-order analysis missed — the P-delta effect. The stability
    coefficient measures how big it is: ``story_gravity_load`` Pₓ (the total weight above the
    story), the ``design_story_drift`` Δ (the amplified drift from
    :func:`seismic_design_story_drift`), the
    ``story_shear`` Vₓ, the ``story_height`` hsx, and the ``deflection_amplification_factor`` Cd.
    Below θ = 0.10 P-delta is negligible and may be ignored; above it the drift and forces must be
    amplified by 1/(1 − θ); above :func:`seismic_stability_coefficient_limit` the story is unstable.
    Returns the dimensionless θ.
    """
    _check(story_gravity_load, "[force]", "story_gravity_load")
    _check(design_story_drift, "[length]", "design_story_drift")
    _check(story_shear, "[force]", "story_shear")
    _check(story_height, "[length]", "story_height")
    px = story_gravity_load.to("kN").magnitude
    drift = design_story_drift.to("m").magnitude
    vx = story_shear.to("kN").magnitude
    h = story_height.to("m").magnitude
    if px <= 0 or vx <= 0 or h <= 0:
        raise ValueError("story_gravity_load, story_shear, and story_height must be positive")
    if drift < 0:
        raise ValueError("design_story_drift must be non-negative")
    if deflection_amplification_factor <= 0:
        raise ValueError("deflection_amplification_factor must be positive")
    return px * drift / (vx * h * deflection_amplification_factor)


def seismic_stability_coefficient_limit(
    *,
    deflection_amplification_factor: float,
    demand_capacity_ratio: float = 1.0,
) -> float:
    """The ASCE 7 maximum stability coefficient θ_max = 0.5/(β·Cd) ≤ 0.25 (§12.8.7).

    The ceiling on the P-delta stability coefficient above which a story is considered unstable and
    must be stiffened. ``deflection_amplification_factor`` Cd and ``demand_capacity_ratio`` β (the
    ratio of the story shear demand to its capacity, conservatively taken as 1.0 when unknown) set
    θ_max = 0.5/(β·Cd), but never more than 0.25. Compare the θ from
    :func:`seismic_stability_coefficient` against this. Returns the dimensionless θ_max.
    """
    if deflection_amplification_factor <= 0:
        raise ValueError("deflection_amplification_factor must be positive")
    if not 0 < demand_capacity_ratio <= 1.0:
        raise ValueError("demand_capacity_ratio must be in (0, 1]")
    return min(0.5 / (demand_capacity_ratio * deflection_amplification_factor), 0.25)


def seismic_load_effect(
    *,
    horizontal_effect: Quantity,
    dead_load_effect: Quantity,
    design_spectral_acceleration: float,
    redundancy_factor: float = 1.0,
    counteracting: bool = False,
) -> Quantity:
    """The ASCE 7 seismic load effect E = ρ·Q_E ± 0.2·SDS·D fed to the load combinations (§12.4.2).

    The earthquake force the strength combinations actually use is not the bare analysis result but
    a horizontal part and a vertical part combined. The horizontal effect ``horizontal_effect`` Q_E
    (the force, moment, or stress the seismic analysis produces in the element) is scaled by the
    ``redundancy_factor`` ρ (1.0 or 1.3, a penalty on systems with few lateral-load paths), and the
    vertical earthquake adds 0.2·SDS·D — a fraction of the ``dead_load_effect`` D set by the
    ``design_spectral_acceleration`` SDS: E = ρ·Q_E + 0.2·SDS·D. Pass ``counteracting=True`` for the
    load combinations where the vertical earthquake acts *upward* and relieves gravity (the 0.9D
    uplift cases), giving E = ρ·Q_E − 0.2·SDS·D. Feed the result as the seismic effect to
    :func:`~anvilate.analysis.asce7_lrfd_factored_load`. Returns E in the horizontal effect's units.
    """
    if not isinstance(horizontal_effect, Quantity):
        raise TypeError("horizontal_effect must be a Quantity load effect")
    if not dead_load_effect.has_dimension(horizontal_effect.dimensionality):
        raise ValueError(
            "dead_load_effect must share the horizontal effect's dimensionality "
            f"({horizontal_effect.dimensionality}); got {dead_load_effect.dimensionality}"
        )
    unit = horizontal_effect.unit
    qe = horizontal_effect.to(unit).magnitude
    d = dead_load_effect.to(unit).magnitude
    if qe < 0 or d < 0:
        raise ValueError("horizontal_effect and dead_load_effect must be non-negative")
    if design_spectral_acceleration <= 0:
        raise ValueError("design_spectral_acceleration must be positive")
    if redundancy_factor <= 0:
        raise ValueError("redundancy_factor must be positive")
    vertical = 0.2 * design_spectral_acceleration * d
    horizontal = redundancy_factor * qe
    e = horizontal - vertical if counteracting else horizontal + vertical
    return Quantity(magnitude=e, unit=unit)


def flat_roof_snow_load(
    *,
    ground_snow_load: Quantity,
    exposure_factor: float = 1.0,
    thermal_factor: float = 1.0,
    importance_factor: float = 1.0,
) -> Quantity:
    """The ASCE 7 flat-roof snow load pf = 0.7·Ce·Ct·Is·pg (§7.3).

    The design snow on a flat (or nearly flat) roof: the site's ``ground_snow_load`` pg discounted
    by the 0.7 baseline and three table factors — ``exposure_factor`` Ce (wind exposure, <1 for a
    windswept roof that blows clear, >1 for a sheltered one), ``thermal_factor`` Ct (roof warmth, <1
    for a heated building whose roof melts snow, >1 for a cold/freezer roof), and
    ``importance_factor`` Is (occupancy). All three are ASCE 7 table values. Reduce it for a pitched
    roof with :func:`sloped_roof_snow_load`. Returns the flat-roof snow load in kPa.
    """
    _check(ground_snow_load, "[pressure]", "ground_snow_load")
    pg = ground_snow_load.to("kPa").magnitude
    if pg <= 0:
        raise ValueError("ground_snow_load must be positive")
    for name, value in (
        ("exposure_factor", exposure_factor),
        ("thermal_factor", thermal_factor),
        ("importance_factor", importance_factor),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    pf = _FLAT_ROOF_SNOW_CONSTANT * exposure_factor * thermal_factor * importance_factor * pg
    return Quantity(magnitude=pf, unit="kPa")


def sloped_roof_snow_load(
    *,
    flat_roof_snow_load: Quantity,
    slope_factor: float,
) -> Quantity:
    """The ASCE 7 sloped-roof snow load ps = Cs·pf (§7.4).

    A pitched roof holds less snow than a flat one, because some slides off: the
    ``flat_roof_snow_load`` pf (from :func:`flat_roof_snow_load`) scaled by the ``slope_factor`` Cs,
    which falls from 1 toward 0 as the roof steepens and its surface grows more slippery (an ASCE 7
    value from the pitch and the roof's slipperiness). Returns the sloped-roof snow load in kPa.
    """
    _check(flat_roof_snow_load, "[pressure]", "flat_roof_snow_load")
    pf = flat_roof_snow_load.to("kPa").magnitude
    if pf <= 0:
        raise ValueError("flat_roof_snow_load must be positive")
    if not 0 <= slope_factor <= 1:
        raise ValueError(f"slope_factor must lie in [0, 1]; got {slope_factor}")
    return Quantity(magnitude=slope_factor * pf, unit="kPa")


def reduced_live_load(
    *,
    unreduced_live_load: Quantity,
    live_load_element_factor: float,
    tributary_area: Quantity,
    supports_multiple_floors: bool = False,
) -> Quantity:
    """The ASCE 7 reduced design live load L = L0·(0.25 + 4.57/√(KLL·AT)) (§4.7.2).

    A large floor area is unlikely to ever carry its full design live load everywhere at once, so
    ASCE 7 lets a member collecting a big tributary area design for less. ``unreduced_live_load`` L0
    is the tabulated design live load, ``live_load_element_factor`` KLL the element factor (4 for an
    interior column, 2 for an interior beam, etc.), and ``tributary_area`` AT the area the member
    supports. The reduction applies only when KLL·AT reaches 37.16 m² (400 ft²) — below that the
    full L0 is returned — and is floored at 0.50·L0 for a member supporting one floor or 0.40·L0 for
    one supporting two or more (``supports_multiple_floors``). Returns the reduced live load in kPa.
    """
    _check(unreduced_live_load, "[pressure]", "unreduced_live_load")
    _check(tributary_area, "[area]", "tributary_area")
    l0 = unreduced_live_load.to("kPa").magnitude
    at = tributary_area.to("m**2").magnitude
    if l0 <= 0 or at <= 0:
        raise ValueError("unreduced_live_load and tributary_area must be positive")
    if live_load_element_factor <= 0:
        raise ValueError("live_load_element_factor must be positive")
    influence = live_load_element_factor * at
    if influence < _LIVE_LOAD_REDUCTION_THRESHOLD:
        return Quantity(magnitude=l0, unit="kPa")
    reduced = l0 * (0.25 + _LIVE_LOAD_REDUCTION_CONSTANT / sqrt(influence))
    floor = (0.40 if supports_multiple_floors else 0.50) * l0
    return Quantity(magnitude=max(reduced, floor), unit="kPa")


def rain_load(*, static_head: Quantity, hydraulic_head: Quantity) -> Quantity:
    """The ASCE 7 rain load R = 0.0098·(ds + dh) — the weight of ponded water on a roof (§8.3).

    A roof must be designed for the water that stands on it when its primary drain is blocked and
    flow backs up to the secondary (overflow) drainage. The load is just the hydrostatic weight of
    that pond: ``static_head`` ds (the depth of water at the secondary drain's inlet when the
    primary is blocked) plus ``hydraulic_head`` dh (the extra depth needed to drive the design flow
    through the secondary drainage), times water's unit weight — R = 0.0098·(ds + dh), heads in mm
    and R in kPa. The heads come from the drainage layout and the design rainfall; a small secondary
    drain (large dh) is what makes rain govern. Returns the rain load in kPa.
    """
    _check(static_head, "[length]", "static_head")
    _check(hydraulic_head, "[length]", "hydraulic_head")
    ds = static_head.to("mm").magnitude
    dh = hydraulic_head.to("mm").magnitude
    if ds < 0 or dh < 0:
        raise ValueError("static_head and hydraulic_head must be non-negative")
    return Quantity(magnitude=_RAIN_LOAD_CONSTANT * (ds + dh), unit="kPa")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
