"""T1 analytical geotechnical checks (Rankine earth pressure, Terzaghi bearing, closed-form).

Two problems sit under almost every foundation and retaining wall, and both have clean
closed forms in terms of the soil's friction angle φ and unit weight γ.

*Lateral earth pressure* (Rankine): a wall retaining level cohesionless backfill feels a
pressure that grows linearly with depth. The coefficient is a pure function of φ —
K_a = tan²(45° − φ/2) when the soil is pushing the wall away (active) and
K_p = tan²(45° + φ/2) when the wall pushes into the soil (passive) — and the resultant
thrust on a wall of height H is the triangle's area, ½·K·γ·H² per unit length (plus a
K·q·H rectangle for any uniform surcharge q).

*Bearing capacity* (Terzaghi): the ultimate pressure a strip footing can carry before the
soil shears is q_ult = c·N_c + q·N_q + ½·γ·B·N_γ — a cohesion term, a surcharge (embedment)
term, and a self-weight term, each scaled by a dimensionless bearing-capacity factor that
depends only on φ. :func:`bearing_capacity_factors` returns N_c, N_q, N_γ from the standard
closed forms (N_q from Reissner, N_c from Prandtl, N_γ from Vesić's 2(N_q+1)·tanφ).

*Consolidation settlement* (Terzaghi 1D): a clay layer squeezed by an added stress Δσ gives up
pore water and settles by S = (C·H/(1+e₀))·log₁₀(σ_f/σ₀), the compressibility index C being the
virgin C_c above the preconsolidation stress σ_c and the stiffer recompression C_r below it —
:func:`consolidation_settlement` handles the normally-consolidated, recompression-only, and
crossing cases. How long it takes follows from the time factor T_v(U) and t = T_v·H_dr²/c_v.

Angles are passed in degrees (a bare float, as elsewhere in this library); other inputs and
all outputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import cos, exp, log10, pi, radians, sin, sqrt, tan

from ..units import Quantity

__all__ = [
    "bearing_capacity_factors",
    "bearing_depth_factors",
    "bearing_inclination_factors",
    "bearing_shape_factors",
    "consolidation_settlement",
    "consolidation_time",
    "consolidation_time_factor",
    "critical_hydraulic_gradient",
    "darcy_seepage_flow",
    "eccentric_base_pressure",
    "piping_factor_of_safety",
    "seepage_velocity",
    "infinite_slope_factor_of_safety",
    "pile_allowable_capacity",
    "pile_end_bearing_capacity",
    "pile_skin_friction_capacity",
    "rankine_active_pressure_cohesive",
    "rankine_earth_pressure_coefficient",
    "rankine_lateral_thrust",
    "rankine_sloped_backfill_coefficient",
    "tension_crack_depth",
    "retaining_wall_overturning_factor",
    "retaining_wall_sliding_factor",
    "terzaghi_bearing_capacity",
    "vertical_stress_increase_2to1",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _check_friction_angle(friction_angle: float) -> None:
    if not 0.0 <= friction_angle < 90.0:
        raise ValueError(f"friction_angle must be in [0, 90) degrees; got {friction_angle}")


def rankine_earth_pressure_coefficient(*, friction_angle: float, passive: bool = False) -> float:
    """The Rankine lateral earth-pressure coefficient for level cohesionless backfill.

    The ratio of horizontal to vertical effective stress behind a smooth wall retaining level
    granular soil, a pure function of the drained friction angle φ: the active coefficient
    K_a = tan²(45° − φ/2) governs when the soil yields and pushes the wall out, and the passive
    K_p = tan²(45° + φ/2) — its reciprocal — the much larger resistance the wall mobilizes
    pushing back into the soil. ``friction_angle`` φ is in degrees; set ``passive`` True for K_p.
    Returns the dimensionless coefficient.
    """
    _check_friction_angle(friction_angle)
    if passive:
        return tan(radians(45.0 + friction_angle / 2.0)) ** 2
    return tan(radians(45.0 - friction_angle / 2.0)) ** 2


def rankine_sloped_backfill_coefficient(*, friction_angle: float, backfill_slope: float) -> float:
    """The Rankine active earth-pressure coefficient for a sloped (inclined) backfill.

    When the retained soil surface slopes up behind the wall — an embankment, a terraced site — the
    active pressure is higher than for level ground, and the coefficient picks up the slope angle:
    K_a = cosβ·(cosβ − √(cos²β − cos²φ))/(cosβ + √(cos²β − cos²φ)). ``friction_angle`` φ and
    ``backfill_slope`` β are both in degrees, and the pressure acts parallel to the slope. The
    slope cannot be steeper than the friction angle (the soil would slide), so β < φ. At β = 0 this
    reduces to the level-ground tan²(45 − φ/2) of :func:`rankine_earth_pressure_coefficient`.
    Returns the dimensionless coefficient.
    """
    _check_friction_angle(friction_angle)
    if not 0.0 <= backfill_slope < friction_angle:
        raise ValueError(
            f"backfill_slope must be in [0, φ) — it cannot exceed the friction angle "
            f"{friction_angle}; got {backfill_slope}"
        )
    beta = radians(backfill_slope)
    phi = radians(friction_angle)
    root = sqrt(cos(beta) ** 2 - cos(phi) ** 2)
    return cos(beta) * (cos(beta) - root) / (cos(beta) + root)


def rankine_active_pressure_cohesive(
    *,
    depth: Quantity,
    unit_weight: Quantity,
    friction_angle: float,
    cohesion: Quantity,
) -> Quantity:
    """The Rankine active earth pressure in a cohesive (c-φ) soil, σ_a = K_a·γ·z − 2c·√K_a.

    A clay backfill holds itself together, so it presses on a wall less than a cohesionless soil —
    the cohesion subtracts a constant 2c·√K_a from the pressure: σ_a = K_a·γ·z − 2c·√K_a, from the
    ``depth`` z, ``unit_weight`` γ, ``friction_angle`` φ (degrees, giving K_a), and ``cohesion`` c.
    Near the surface this goes *negative* — the soil is in tension and simply cracks away from the
    wall, carrying no pressure down to the tension-crack depth (see :func:`tension_crack_depth`).
    Returns σ_a in kPa (a negative value marks the cracked, tension zone, taken as zero pressure in
    design).
    """
    _require(depth, "[length]", "depth")
    _require(unit_weight, "[force]/[length]**3", "unit_weight")
    _require(cohesion, "[pressure]", "cohesion")
    _check_friction_angle(friction_angle)
    z = depth.to("m").magnitude
    gamma = unit_weight.to("kN/m**3").magnitude
    c = cohesion.to("kPa").magnitude
    if z < 0 or gamma <= 0 or c < 0:
        raise ValueError("depth non-negative, unit_weight positive, cohesion non-negative")
    k_a = rankine_earth_pressure_coefficient(friction_angle=friction_angle)
    sigma_a = k_a * gamma * z - 2.0 * c * sqrt(k_a)
    return Quantity(magnitude=sigma_a, unit="kPa")


def tension_crack_depth(
    *,
    cohesion: Quantity,
    unit_weight: Quantity,
    friction_angle: float,
) -> Quantity:
    """The depth of the tension crack behind a wall in cohesive soil, z_c = 2c/(γ·√K_a).

    In a c-φ soil the active pressure is negative (tension) near the surface, so the soil pulls away
    from the wall and opens a crack down to where the pressure first becomes compressive:
    z_c = 2c/(γ·√K_a), from the ``cohesion`` c, ``unit_weight`` γ, and ``friction_angle`` φ. This is
    also how deep a temporary vertical cut in clay can stand unsupported (briefly), and the crack
    fills with water in rain — a worst case for wall design. Returns z_c in meters.
    """
    _require(cohesion, "[pressure]", "cohesion")
    _require(unit_weight, "[force]/[length]**3", "unit_weight")
    _check_friction_angle(friction_angle)
    c = cohesion.to("kPa").magnitude
    gamma = unit_weight.to("kN/m**3").magnitude
    if c <= 0 or gamma <= 0:
        raise ValueError("cohesion and unit_weight must be positive")
    k_a = rankine_earth_pressure_coefficient(friction_angle=friction_angle)
    return Quantity(magnitude=2.0 * c / (gamma * sqrt(k_a)), unit="m")


def rankine_lateral_thrust(
    *,
    unit_weight: Quantity,
    height: Quantity,
    friction_angle: float,
    passive: bool = False,
    surcharge: Quantity | None = None,
) -> Quantity:
    """The Rankine resultant lateral thrust on a wall of height H, per unit wall length.

    Integrating the Rankine pressure over the wall gives the horizontal force the backfill
    delivers: the soil's own triangular pressure contributes ½·K·γ·H² and any uniform surface
    ``surcharge`` q adds a rectangular K·q·H. ``unit_weight`` γ is the soil's total unit weight,
    ``height`` H the retained height, ``friction_angle`` φ (degrees) sets the coefficient via
    :func:`rankine_earth_pressure_coefficient`, and ``passive`` selects K_p over K_a. Returns the
    thrust per unit wall length in kN/m — multiply by the wall length for the total force, and
    note the soil triangle's resultant acts at H/3 above the base.
    """
    _require(unit_weight, "[force]/[length]**3", "unit_weight")
    _require(height, "[length]", "height")
    gamma = unit_weight.to("kN/m**3").magnitude
    h = height.to("m").magnitude
    if gamma <= 0 or h <= 0:
        raise ValueError("unit_weight and height must be positive")
    k = rankine_earth_pressure_coefficient(friction_angle=friction_angle, passive=passive)
    thrust = 0.5 * k * gamma * h**2
    if surcharge is not None:
        _require(surcharge, "[pressure]", "surcharge")
        q = surcharge.to("kPa").magnitude
        if q < 0:
            raise ValueError("surcharge must be non-negative")
        thrust += k * q * h
    return Quantity(magnitude=thrust, unit="kN/m")


def bearing_capacity_factors(*, friction_angle: float) -> dict[str, float]:
    """The Terzaghi/Vesić bearing-capacity factors N_c, N_q, N_γ from the friction angle.

    The three dimensionless multipliers in the bearing-capacity equation, each a function of the
    drained friction angle φ alone: N_q = e^(π·tanφ)·tan²(45° + φ/2) (Reissner's surcharge term),
    N_c = (N_q − 1)·cotφ (Prandtl, with the φ→0 limit N_c = π + 2 = 5.14), and
    N_γ = 2·(N_q + 1)·tanφ (Vesić). ``friction_angle`` φ is in degrees. Returns a dict with keys
    ``"N_c"``, ``"N_q"``, ``"N_gamma"`` — feed them to :func:`terzaghi_bearing_capacity`.
    """
    _check_friction_angle(friction_angle)
    phi = radians(friction_angle)
    n_q = exp(pi * tan(phi)) * tan(radians(45.0 + friction_angle / 2.0)) ** 2
    if friction_angle == 0.0:
        n_c = pi + 2.0  # Prandtl limit; (N_q - 1)/tan(phi) is 0/0 at phi = 0
    else:
        n_c = (n_q - 1.0) / tan(phi)
    n_gamma = 2.0 * (n_q + 1.0) * tan(phi)
    return {"N_c": n_c, "N_q": n_q, "N_gamma": n_gamma}


def bearing_shape_factors(
    *,
    footing_width: Quantity,
    footing_length: Quantity,
    friction_angle: float,
    bearing_factor_nq: float,
    bearing_factor_nc: float,
) -> dict[str, float]:
    """The Vesić shape factors that correct strip bearing capacity for a rectangular footing.

    Terzaghi's bearing equation is for an infinitely long strip; a real rectangular or square
    footing is stronger in the cohesion and surcharge terms but weaker in the self-weight term.
    The Vesić shape factors capture that from the width-to-length ratio B/L:
    s_c = 1 + (B/L)(N_q/N_c), s_q = 1 + (B/L)·tanφ, and s_γ = 1 − 0.4·(B/L). ``footing_width`` B
    (the shorter side),
    ``footing_length`` L, ``friction_angle`` φ (degrees), and the ``bearing_factor_nq``/``_nc`` from
    :func:`bearing_capacity_factors`. Multiply each term of the bearing capacity by its factor.
    Returns a dict with keys ``"s_c"``, ``"s_q"``, ``"s_gamma"``.
    """
    _require(footing_width, "[length]", "footing_width")
    _require(footing_length, "[length]", "footing_length")
    _check_friction_angle(friction_angle)
    b = footing_width.to("m").magnitude
    lo = footing_length.to("m").magnitude
    if b <= 0 or lo <= 0:
        raise ValueError("footing_width and footing_length must be positive")
    if b > lo:
        raise ValueError("footing_width must be the shorter side (B <= L)")
    if bearing_factor_nq <= 0 or bearing_factor_nc <= 0:
        raise ValueError("bearing_factor_nq and bearing_factor_nc must be positive")
    ratio = b / lo
    s_c = 1.0 + ratio * (bearing_factor_nq / bearing_factor_nc)
    s_q = 1.0 + ratio * tan(radians(friction_angle))
    s_gamma = 1.0 - 0.4 * ratio
    return {"s_c": s_c, "s_q": s_q, "s_gamma": s_gamma}


def bearing_depth_factors(
    *,
    footing_width: Quantity,
    embedment_depth: Quantity,
    friction_angle: float,
) -> dict[str, float]:
    """The Hansen/Vesić depth factors that credit a footing's embedment in bearing capacity.

    Soil beside an embedded footing adds shear resistance the surface bearing equation ignores, so
    depth factors raise the capacity. For a shallow footing (D ≤ B) the Hansen/Vesić forms are
    d_q = 1 + 2·tanφ·(1 − sinφ)²·(D/B), d_c = d_q − (1 − d_q)/(N_q·tanφ) (or 1 + 0.4·(D/B) when
    φ = 0), and d_γ = 1. ``footing_width`` B, ``embedment_depth`` D (founding depth below grade),
    and ``friction_angle`` φ (degrees). Multiply each bearing-capacity term by its factor. Returns a
    dict with keys ``"d_c"``, ``"d_q"``, ``"d_gamma"``.
    """
    _require(footing_width, "[length]", "footing_width")
    _require(embedment_depth, "[length]", "embedment_depth")
    _check_friction_angle(friction_angle)
    b = footing_width.to("m").magnitude
    d = embedment_depth.to("m").magnitude
    if b <= 0 or d < 0:
        raise ValueError("footing_width must be positive and embedment_depth non-negative")
    ratio = d / b
    phi = radians(friction_angle)
    if friction_angle == 0.0:
        return {"d_c": 1.0 + 0.4 * ratio, "d_q": 1.0, "d_gamma": 1.0}
    d_q = 1.0 + 2.0 * tan(phi) * (1.0 - sin(phi)) ** 2 * ratio
    d_c = d_q - (1.0 - d_q) / _nq_tan_phi(phi)
    return {"d_c": d_c, "d_q": d_q, "d_gamma": 1.0}


def _nq_tan_phi(phi_radians: float) -> float:
    """N_q·tanφ, the denominator in the Hansen/Vesić d_c depth factor."""
    n_q = exp(pi * tan(phi_radians)) * tan(pi / 4.0 + phi_radians / 2.0) ** 2
    return n_q * tan(phi_radians)


def bearing_inclination_factors(
    *,
    vertical_load: Quantity,
    horizontal_load: Quantity,
    friction_angle: float,
) -> dict[str, float]:
    """The Meyerhof inclination factors that derate bearing capacity for an inclined load.

    A load that is not purely vertical — a footing also carrying a horizontal thrust from wind,
    earth pressure, or a braced frame — mobilizes less bearing capacity, because part of the
    soil's strength is spent resisting sliding. Meyerhof's inclination factors depend on the load's
    angle from vertical α = arctan(H/V): i_c = i_q = (1 − α/90°)² and i_γ = (1 − α/φ)² (zero once α
    exceeds φ, where the γ-term vanishes). ``vertical_load`` V, ``horizontal_load`` H, and
    ``friction_angle`` φ (degrees). Multiply each bearing-capacity term by its factor, alongside the
    shape and depth factors. Returns a dict with keys ``"i_c"``, ``"i_q"``, ``"i_gamma"``.
    """
    _require(vertical_load, "[force]", "vertical_load")
    _require(horizontal_load, "[force]", "horizontal_load")
    _check_friction_angle(friction_angle)
    v = vertical_load.to("kN").magnitude
    h = horizontal_load.to("kN").magnitude
    if v <= 0:
        raise ValueError("vertical_load must be positive")
    if h < 0:
        raise ValueError("horizontal_load must be non-negative")
    from math import atan, degrees

    alpha = degrees(atan(h / v))
    i_cq = (1.0 - alpha / 90.0) ** 2
    if friction_angle == 0.0:
        i_gamma = 1.0 if alpha == 0.0 else 0.0
    elif alpha >= friction_angle:
        i_gamma = 0.0
    else:
        i_gamma = (1.0 - alpha / friction_angle) ** 2
    return {"i_c": i_cq, "i_q": i_cq, "i_gamma": i_gamma}


def terzaghi_bearing_capacity(
    *,
    cohesion: Quantity,
    surcharge: Quantity,
    unit_weight: Quantity,
    width: Quantity,
    bearing_factor_c: float,
    bearing_factor_q: float,
    bearing_factor_gamma: float,
) -> Quantity:
    """The Terzaghi ultimate bearing pressure of a strip footing, q_ult.

    The pressure at which the soil beneath a long footing shears and the footing plunges, summed
    from three mechanisms: q_ult = c·N_c + q·N_q + ½·γ·B·N_γ, a cohesion term, a surcharge term
    for the soil above founding level (``surcharge`` q = γ·D_f), and a self-weight term over the
    footing ``width`` B. ``cohesion`` c and ``surcharge`` q are pressures, ``unit_weight`` γ the
    soil unit weight, and the three ``bearing_factor_*`` are N_c, N_q, N_γ from
    :func:`bearing_capacity_factors` (or a table). Returns q_ult in kPa; divide by a factor of
    safety (typically 3) for the allowable bearing pressure.
    """
    _require(cohesion, "[pressure]", "cohesion")
    _require(surcharge, "[pressure]", "surcharge")
    _require(unit_weight, "[force]/[length]**3", "unit_weight")
    _require(width, "[length]", "width")
    c = cohesion.to("kPa").magnitude
    q = surcharge.to("kPa").magnitude
    gamma = unit_weight.to("kN/m**3").magnitude
    b = width.to("m").magnitude
    if c < 0 or q < 0:
        raise ValueError("cohesion and surcharge must be non-negative")
    if gamma <= 0 or b <= 0:
        raise ValueError("unit_weight and width must be positive")
    q_ult = c * bearing_factor_c + q * bearing_factor_q + 0.5 * gamma * b * bearing_factor_gamma
    return Quantity(magnitude=q_ult, unit="kPa")


def consolidation_settlement(
    *,
    compression_index: float,
    initial_void_ratio: float,
    layer_thickness: Quantity,
    initial_effective_stress: Quantity,
    stress_increment: Quantity,
    preconsolidation_stress: Quantity | None = None,
    recompression_index: float | None = None,
) -> Quantity:
    """The Terzaghi 1D primary consolidation settlement of a clay layer under an added stress.

    A saturated clay layer loaded by Δσ consolidates as its void ratio drops along the
    e–log σ' curve: S = (C·H/(1+e₀))·log₁₀(σ_f/σ₀). Which slope C applies depends on the
    preconsolidation stress σ_c. A normally consolidated clay (no ``preconsolidation_stress``, or
    σ_c ≤ σ₀) rides the virgin curve at ``compression_index`` C_c throughout. An overconsolidated
    clay uses the flatter ``recompression_index`` C_r while the stress stays below σ_c, and if the
    final stress σ₀ + Δσ crosses σ_c the settlement splits — C_r from σ₀ to σ_c plus C_c from σ_c
    to σ_f. ``initial_void_ratio`` e₀, ``layer_thickness`` H, ``initial_effective_stress`` σ₀ (the
    mid-layer overburden), and ``stress_increment`` Δσ complete the inputs; give
    ``preconsolidation_stress`` and ``recompression_index`` together for the overconsolidated
    cases. Returns the settlement in mm.
    """
    _require(layer_thickness, "[length]", "layer_thickness")
    _require(initial_effective_stress, "[pressure]", "initial_effective_stress")
    _require(stress_increment, "[pressure]", "stress_increment")
    h = layer_thickness.to("m").magnitude
    s0 = initial_effective_stress.to("kPa").magnitude
    ds = stress_increment.to("kPa").magnitude
    if compression_index <= 0 or initial_void_ratio <= 0:
        raise ValueError("compression_index and initial_void_ratio must be positive")
    if h <= 0 or s0 <= 0 or ds < 0:
        raise ValueError("layer_thickness and stresses must be positive (increment non-negative)")
    sf = s0 + ds
    coeff = h / (1.0 + initial_void_ratio)

    if preconsolidation_stress is None:
        strain = compression_index * coeff * log10(sf / s0)
        return Quantity(magnitude=strain * 1000.0, unit="mm")

    _require(preconsolidation_stress, "[pressure]", "preconsolidation_stress")
    sc = preconsolidation_stress.to("kPa").magnitude
    if recompression_index is None or recompression_index <= 0:
        raise ValueError(
            "recompression_index must be given and positive when preconsolidation_stress is set"
        )
    if sc < s0:
        raise ValueError("preconsolidation_stress must be at least the initial effective stress")

    if sf <= sc:
        # Wholly on the recompression curve.
        strain = recompression_index * coeff * log10(sf / s0)
    else:
        # Recompression up to sigma_c, then virgin compression beyond it.
        strain = recompression_index * coeff * log10(sc / s0) + compression_index * coeff * log10(
            sf / sc
        )
    return Quantity(magnitude=strain * 1000.0, unit="mm")


def consolidation_time_factor(*, degree_of_consolidation: float) -> float:
    """The Terzaghi dimensionless time factor T_v for a given average degree of consolidation U.

    The nondimensional time in the 1D consolidation solution, from the standard two-branch fit to
    the theoretical U–T_v curve: T_v = (π/4)·U² for U ≤ 60% and T_v = 1.781 − 0.933·log₁₀(100 − U%)
    beyond, with U as a percentage. ``degree_of_consolidation`` U is the percent of ultimate
    settlement reached (0–100, exclusive of 100). Feed the result to :func:`consolidation_time` to
    get the elapsed time. Returns the dimensionless T_v.
    """
    u = degree_of_consolidation
    if not 0.0 <= u < 100.0:
        raise ValueError(f"degree_of_consolidation must be in [0, 100) percent; got {u}")
    if u <= 60.0:
        return (pi / 4.0) * (u / 100.0) ** 2
    return 1.781 - 0.933 * log10(100.0 - u)


def consolidation_time(
    *,
    time_factor: float,
    drainage_path_length: Quantity,
    coefficient_of_consolidation: Quantity,
) -> Quantity:
    """The elapsed time to reach a given consolidation time factor T_v.

    Inverting the time factor's definition T_v = c_v·t/H_dr² for the time: t = T_v·H_dr²/c_v.
    ``time_factor`` T_v comes from :func:`consolidation_time_factor`, ``drainage_path_length`` H_dr
    is the longest path water travels to a drainage boundary (the full layer thickness for
    single-sided drainage, half of it for double-sided), and ``coefficient_of_consolidation`` c_v
    is the soil's consolidation rate (units of area over time). Returns the time in years.
    """
    _require(drainage_path_length, "[length]", "drainage_path_length")
    _require(coefficient_of_consolidation, "[length]**2/[time]", "coefficient_of_consolidation")
    h_dr = drainage_path_length.to("m").magnitude
    c_v = coefficient_of_consolidation.to("m**2/year").magnitude
    if time_factor < 0:
        raise ValueError("time_factor must be non-negative")
    if h_dr <= 0 or c_v <= 0:
        raise ValueError("drainage_path_length and coefficient_of_consolidation must be positive")
    return Quantity(magnitude=time_factor * h_dr**2 / c_v, unit="year")


def retaining_wall_overturning_factor(
    *,
    lateral_thrust: Quantity,
    thrust_height: Quantity,
    vertical_load: Quantity,
    load_arm: Quantity,
) -> float:
    """The factor of safety against overturning of a retaining wall about its toe.

    A retaining wall tips about its toe when the backfill's lateral thrust overpowers the
    restoring moment of the weight bearing down on it. This is the ratio of the two moments,
    FS = (V·a) / (P·y): the ``vertical_load`` V (the wall plus the soil on its heel, per unit
    length) times its ``load_arm`` a to the toe, over the ``lateral_thrust`` P (from
    :func:`rankine_lateral_thrust`) times ``thrust_height`` y, the height of its line of action
    above the base (H/3 for the triangular soil pressure). Loads and thrust are per unit wall
    length; the units cancel to a dimensionless factor. Returns FS — 2.0 is a common minimum.
    """
    _require(lateral_thrust, "[force]/[length]", "lateral_thrust")
    _require(thrust_height, "[length]", "thrust_height")
    _require(vertical_load, "[force]/[length]", "vertical_load")
    _require(load_arm, "[length]", "load_arm")
    p = lateral_thrust.to("kN/m").magnitude
    y = thrust_height.to("m").magnitude
    v = vertical_load.to("kN/m").magnitude
    a = load_arm.to("m").magnitude
    if p <= 0 or y <= 0:
        raise ValueError("lateral_thrust and thrust_height must be positive")
    if v <= 0 or a <= 0:
        raise ValueError("vertical_load and load_arm must be positive")
    return (v * a) / (p * y)


def retaining_wall_sliding_factor(
    *,
    lateral_thrust: Quantity,
    vertical_load: Quantity,
    base_friction_coefficient: float,
    passive_resistance: Quantity | None = None,
) -> float:
    """The factor of safety against sliding of a retaining wall on its base.

    A wall slides when the lateral thrust exceeds the friction the base can mobilize. This is
    FS = (μ·V + P_p) / P: the base friction, ``base_friction_coefficient`` μ (= tanδ) times the
    ``vertical_load`` V pressing the wall down, plus any ``passive_resistance`` P_p mobilized in
    front of the toe, over the driving ``lateral_thrust`` P (from
    :func:`rankine_lateral_thrust`). Forces are per unit wall length. Passive resistance is often
    neglected (the soil in front can be excavated), so it defaults to none. Returns FS — 1.5 is a
    common minimum.
    """
    _require(lateral_thrust, "[force]/[length]", "lateral_thrust")
    _require(vertical_load, "[force]/[length]", "vertical_load")
    p = lateral_thrust.to("kN/m").magnitude
    v = vertical_load.to("kN/m").magnitude
    if p <= 0 or v <= 0:
        raise ValueError("lateral_thrust and vertical_load must be positive")
    if base_friction_coefficient <= 0:
        raise ValueError("base_friction_coefficient must be positive")
    resisting = base_friction_coefficient * v
    if passive_resistance is not None:
        _require(passive_resistance, "[force]/[length]", "passive_resistance")
        p_p = passive_resistance.to("kN/m").magnitude
        if p_p < 0:
            raise ValueError("passive_resistance must be non-negative")
        resisting += p_p
    return resisting / p


def eccentric_base_pressure(
    *,
    vertical_load: Quantity,
    base_width: Quantity,
    eccentricity: Quantity,
) -> dict[str, Quantity]:
    """The soil bearing pressures under the base of an eccentrically loaded wall or footing.

    The resultant vertical load on a retaining-wall base rarely lands at the center, and the
    pressure under the base tilts from heel to toe. While the eccentricity stays within the
    middle third (e ≤ B/6) the whole base bears and the pressures are the linear
    q = (V/B)·(1 ± 6e/B). Past the middle third the heel would need to pull the soil in tension —
    which it cannot — so contact shortens and the toe pressure jumps to q_max = 2V/[3·(B/2 − e)]
    with the heel at zero. ``vertical_load`` V and ``base_width`` B and ``eccentricity`` e of the
    resultant from the base centroid are all per unit wall length / actual dimensions. Returns a
    dict with ``"q_max"`` (toe) and ``"q_min"`` (heel) pressures in kPa.
    """
    _require(vertical_load, "[force]/[length]", "vertical_load")
    _require(base_width, "[length]", "base_width")
    _require(eccentricity, "[length]", "eccentricity")
    v = vertical_load.to("kN/m").magnitude
    b = base_width.to("m").magnitude
    e = eccentricity.to("m").magnitude
    if v <= 0 or b <= 0:
        raise ValueError("vertical_load and base_width must be positive")
    if e < 0:
        raise ValueError("eccentricity must be non-negative")
    if e >= b / 2.0:
        raise ValueError("eccentricity must be less than half the base width (resultant off base)")
    if e <= b / 6.0:
        q_max = (v / b) * (1.0 + 6.0 * e / b)
        q_min = (v / b) * (1.0 - 6.0 * e / b)
    else:
        q_max = 2.0 * v / (3.0 * (b / 2.0 - e))
        q_min = 0.0
    return {
        "q_max": Quantity(magnitude=q_max, unit="kPa"),
        "q_min": Quantity(magnitude=q_min, unit="kPa"),
    }


def infinite_slope_factor_of_safety(
    *,
    cohesion: Quantity,
    friction_angle: float,
    unit_weight: Quantity,
    depth: Quantity,
    slope_angle: float,
    pore_pressure: Quantity | None = None,
) -> float:
    """The factor of safety against sliding of a long, uniform (infinite) slope.

    A shallow soil layer on a long planar slope slides on a plane parallel to the surface when the
    shear the slope's weight drives exceeds the soil's strength on that plane. The ratio of the two
    is FS = [c + (γ·z·cos²β − u)·tanφ] / (γ·z·sinβ·cosβ): a cohesion term c, plus friction on the
    effective normal stress (the overburden γ·z·cos²β less any ``pore_pressure`` u), over the
    driving shear. ``cohesion`` c, ``friction_angle`` φ (degrees), ``unit_weight`` γ, ``depth`` z
    to the failure plane, and ``slope_angle`` β (degrees). For a dry cohesionless slope this
    reduces to the familiar tanφ/tanβ. Returns FS — below 1 the slope fails.
    """
    _require(cohesion, "[pressure]", "cohesion")
    _require(unit_weight, "[force]/[length]**3", "unit_weight")
    _require(depth, "[length]", "depth")
    _check_friction_angle(friction_angle)
    if not 0.0 < slope_angle < 90.0:
        raise ValueError(f"slope_angle must be in (0, 90) degrees; got {slope_angle}")
    c = cohesion.to("kPa").magnitude
    gamma = unit_weight.to("kN/m**3").magnitude
    z = depth.to("m").magnitude
    if c < 0 or gamma <= 0 or z <= 0:
        raise ValueError("cohesion non-negative, unit_weight and depth positive")
    beta = radians(slope_angle)
    phi = radians(friction_angle)
    u = 0.0
    if pore_pressure is not None:
        _require(pore_pressure, "[pressure]", "pore_pressure")
        u = pore_pressure.to("kPa").magnitude
        if u < 0:
            raise ValueError("pore_pressure must be non-negative")
    normal = gamma * z * cos(beta) ** 2 - u
    resisting = c + normal * tan(phi)
    driving = gamma * z * sin(beta) * cos(beta)
    return resisting / driving


def vertical_stress_increase_2to1(
    *,
    applied_pressure: Quantity,
    footing_width: Quantity,
    footing_length: Quantity,
    depth: Quantity,
) -> Quantity:
    """The vertical stress increase under a footing by the 2:1 spread approximation.

    A footing's bearing pressure does not reach far below it undiminished — it spreads out and
    weakens with depth. The simple 2:1 method assumes the load spreads on a 2-vertical-to-1-
    horizontal wedge, so at ``depth`` z below a rectangular footing the added stress is
    Δσ = q₀·B·L / [(B + z)·(L + z)]. ``applied_pressure`` q₀ is the contact pressure and
    ``footing_width`` B and ``footing_length`` L its plan dimensions. This is the Δσ that drives
    :func:`consolidation_settlement` in the soil below. Returns Δσ in kPa.
    """
    _require(applied_pressure, "[pressure]", "applied_pressure")
    _require(footing_width, "[length]", "footing_width")
    _require(footing_length, "[length]", "footing_length")
    _require(depth, "[length]", "depth")
    q0 = applied_pressure.to("kPa").magnitude
    b = footing_width.to("m").magnitude
    lo = footing_length.to("m").magnitude
    z = depth.to("m").magnitude
    if q0 <= 0 or b <= 0 or lo <= 0:
        raise ValueError("applied_pressure, footing_width, and footing_length must be positive")
    if z < 0:
        raise ValueError("depth must be non-negative")
    delta_sigma = q0 * b * lo / ((b + z) * (lo + z))
    return Quantity(magnitude=delta_sigma, unit="kPa")


def darcy_seepage_flow(
    *,
    permeability: Quantity,
    hydraulic_gradient: float,
    area: Quantity,
) -> Quantity:
    """The groundwater seepage flow through soil by Darcy's law, q = k·i·A.

    Water moves through soil in proportion to the hydraulic gradient driving it: q = k·i·A.
    ``permeability`` k is the soil's coefficient of permeability (hydraulic conductivity, a velocity
    — ~1e-2 m/s for gravel down to ~1e-9 m/s for clay), ``hydraulic_gradient`` i the dimensionless
    head drop per unit flow length (Δh/L), and ``area`` A the gross cross-section the flow crosses.
    This is the discharge for a dewatering or under-dam seepage estimate. Returns the flow in m³/s.
    """
    _require(permeability, "[length]/[time]", "permeability")
    _require(area, "[area]", "area")
    k = permeability.to("m/s").magnitude
    a = area.to("m**2").magnitude
    if k <= 0 or a <= 0:
        raise ValueError("permeability and area must be positive")
    if hydraulic_gradient < 0:
        raise ValueError("hydraulic_gradient must be non-negative")
    return Quantity(magnitude=k * hydraulic_gradient * a, unit="m**3/s")


def seepage_velocity(
    *,
    permeability: Quantity,
    hydraulic_gradient: float,
    porosity: float,
) -> Quantity:
    """The actual seepage velocity of water through the soil pores, v_s = k·i/n.

    Darcy's law gives a *discharge* velocity v = k·i over the gross area, but the water actually
    threads through only the pore space, so its true speed is higher: v_s = k·i/n. ``permeability``
    k, ``hydraulic_gradient`` i, and ``porosity`` n (the void fraction, ~0.3–0.5 for most soils).
    This is the velocity that governs how fast a contaminant or a tracer travels. Returns the
    seepage velocity in m/s.
    """
    _require(permeability, "[length]/[time]", "permeability")
    k = permeability.to("m/s").magnitude
    if k <= 0:
        raise ValueError("permeability must be positive")
    if hydraulic_gradient < 0:
        raise ValueError("hydraulic_gradient must be non-negative")
    if not 0.0 < porosity < 1.0:
        raise ValueError(f"porosity must be in (0, 1); got {porosity}")
    return Quantity(magnitude=k * hydraulic_gradient / porosity, unit="m/s")


def critical_hydraulic_gradient(*, specific_gravity: float, void_ratio: float) -> float:
    """The critical hydraulic gradient at which upward seepage floats the soil.

    When water seeps upward hard enough, its drag cancels the soil's buoyant weight and the grains
    lose all contact — the quicksand or piping condition. That happens at the critical gradient
    i_cr = (G_s − 1)/(1 + e), from the ``specific_gravity`` G_s of the solids (~2.65 for quartz
    sand) and the ``void_ratio`` e. It is close to 1 for most soils. Compare a computed exit
    gradient against it with :func:`piping_factor_of_safety`. Returns the dimensionless critical
    gradient.
    """
    if specific_gravity <= 1.0:
        raise ValueError(f"specific_gravity must exceed 1; got {specific_gravity}")
    if void_ratio <= 0:
        raise ValueError(f"void_ratio must be positive; got {void_ratio}")
    return (specific_gravity - 1.0) / (1.0 + void_ratio)


def piping_factor_of_safety(*, critical_gradient: float, exit_gradient: float) -> float:
    """The factor of safety against piping (heave/boiling) at a seepage exit, i_cr/i_exit.

    Downstream of a sheet-pile wall or under a dam, water exits the ground with an
    ``exit_gradient`` i_exit; if it reaches the ``critical_gradient`` i_cr (from
    :func:`critical_hydraulic_gradient`) the soil boils and pipes. The factor of safety is their
    ratio, FS = i_cr/i_exit — typically kept at 2.5–3 because the consequences (loss of a
    cofferdam, a dam foundation) are severe. Returns the dimensionless factor of safety.
    """
    if critical_gradient <= 0:
        raise ValueError(f"critical_gradient must be positive; got {critical_gradient}")
    if exit_gradient <= 0:
        raise ValueError(f"exit_gradient must be positive; got {exit_gradient}")
    return critical_gradient / exit_gradient


def pile_skin_friction_capacity(
    *,
    adhesion_factor: float,
    undrained_shear_strength: Quantity,
    diameter: Quantity,
    length: Quantity,
) -> Quantity:
    """The shaft (skin-friction) capacity of a pile in clay by the α-method.

    A pile carries much of its load in friction along its shaft. The α-method sets that unit
    friction as a fraction of the soil's strength, f_s = α·c_u, and integrates it over the shaft
    surface: Q_s = α·c_u·(π·D·L). ``adhesion_factor`` α (about 1.0 for soft clay down toward 0.5
    for stiff), ``undrained_shear_strength`` c_u, ``diameter`` D, and embedded ``length`` L. For a
    slender pile this term usually dominates the end bearing — see
    :func:`pile_end_bearing_capacity`. Returns the shaft capacity in kN.
    """
    _require(undrained_shear_strength, "[pressure]", "undrained_shear_strength")
    _require(diameter, "[length]", "diameter")
    _require(length, "[length]", "length")
    cu = undrained_shear_strength.to("kPa").magnitude
    d = diameter.to("m").magnitude
    lo = length.to("m").magnitude
    if not 0.0 < adhesion_factor <= 1.0:
        raise ValueError(f"adhesion_factor must be in (0, 1]; got {adhesion_factor}")
    if cu <= 0 or d <= 0 or lo <= 0:
        raise ValueError("undrained_shear_strength, diameter, and length must be positive")
    q_s = adhesion_factor * cu * pi * d * lo
    return Quantity(magnitude=q_s, unit="kN")


def pile_end_bearing_capacity(
    *,
    undrained_shear_strength: Quantity,
    diameter: Quantity,
    bearing_factor: float = 9.0,
) -> Quantity:
    """The end-bearing (tip) capacity of a pile in clay, Q_p = N_c·c_u·A_tip.

    The load a pile carries on its tip, from the deep bearing-capacity relation with the cohesion
    term only: Q_p = N_c·c_u·(π·D²/4). ``undrained_shear_strength`` c_u and ``diameter`` D, with the
    ``bearing_factor`` N_c taken as 9 for a deep pile in clay (the standard value). Usually the
    smaller part of a slender pile's capacity next to :func:`pile_skin_friction_capacity`. Returns
    the tip capacity in kN.
    """
    _require(undrained_shear_strength, "[pressure]", "undrained_shear_strength")
    _require(diameter, "[length]", "diameter")
    cu = undrained_shear_strength.to("kPa").magnitude
    d = diameter.to("m").magnitude
    if cu <= 0 or d <= 0:
        raise ValueError("undrained_shear_strength and diameter must be positive")
    if bearing_factor <= 0:
        raise ValueError("bearing_factor must be positive")
    area = pi * d**2 / 4.0
    q_p = bearing_factor * cu * area
    return Quantity(magnitude=q_p, unit="kN")


def pile_allowable_capacity(
    *,
    skin_friction: Quantity,
    end_bearing: Quantity,
    factor_of_safety: float,
) -> Quantity:
    """The allowable axial load of a pile, (Q_s + Q_p) / FS.

    The working load a pile can carry: the ultimate capacity — shaft ``skin_friction`` Q_s from
    :func:`pile_skin_friction_capacity` plus ``end_bearing`` Q_p from
    :func:`pile_end_bearing_capacity` — divided by a global ``factor_of_safety`` (typically 2.5–3
    for piles, reflecting the uncertainty in soil parameters and installation). Returns the
    allowable capacity in kN.
    """
    _require(skin_friction, "[force]", "skin_friction")
    _require(end_bearing, "[force]", "end_bearing")
    q_s = skin_friction.to("kN").magnitude
    q_p = end_bearing.to("kN").magnitude
    if q_s <= 0 or q_p <= 0:
        raise ValueError("skin_friction and end_bearing must be positive")
    if factor_of_safety <= 0:
        raise ValueError("factor_of_safety must be positive")
    return Quantity(magnitude=(q_s + q_p) / factor_of_safety, unit="kN")
