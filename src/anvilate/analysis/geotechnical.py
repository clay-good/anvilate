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

from math import exp, log10, pi, radians, tan

from ..units import Quantity

__all__ = [
    "bearing_capacity_factors",
    "consolidation_settlement",
    "consolidation_time",
    "consolidation_time_factor",
    "rankine_earth_pressure_coefficient",
    "rankine_lateral_thrust",
    "terzaghi_bearing_capacity",
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
