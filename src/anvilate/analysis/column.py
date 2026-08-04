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
    "euler_second_moment_for_load",
    "radius_of_gyration",
    "slenderness_ratio",
    "euler_critical_stress",
    "transition_slenderness",
    "johnson_critical_stress",
    "secant_column_max_stress",
    "perry_robertson_stress",
    "lateral_torsional_buckling_moment",
    "rankine_gordon_stress",
    "aisc_flexural_buckling_stress",
    "aisc_plastic_bracing_limit",
    "aisc_effective_radius_of_gyration",
    "aisc_elastic_ltb_stress",
    "aisc_inelastic_ltb_limit",
    "aisc_inelastic_ltb_moment",
    "aisc_beam_column_interaction",
    "aisc_effective_length_factor_braced",
    "aisc_effective_length_factor_sway",
    "aisc_moment_amplifier_b1",
    "aisc_moment_amplifier_b2",
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


def euler_second_moment_for_load(
    *,
    design_load: Quantity,
    length: Quantity,
    elastic_modulus: Quantity,
    required_safety_factor: float,
    effective_length_factor: float = 1.0,
) -> Quantity:
    """The least section second moment I to carry ``design_load`` with a required
    margin against Euler buckling.

    The inverse of :func:`euler_buckling_load`: demanding P_cr ≥ n·P gives
    I_min = n·P·(K·L)²/(π²·E). Sizing a strut runs this way — the load, length,
    and required safety factor are known, and a section with at least this weak-axis
    I must be chosen. ``design_load`` P is the service compression,
    ``required_safety_factor`` n the margin on the buckling load,
    ``effective_length_factor`` K the end condition. Returns the minimum I in mm⁴;
    every quantity is dimension-checked and ``n``/``K`` must be positive.

    A screening size only — an intermediate (stubby) column may be governed by
    inelastic (Johnson) failure or yield instead, which this elastic form ignores.
    """
    _require(design_load, "[force]", "design_load")
    _require(length, "[length]", "length")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    if effective_length_factor <= 0:
        raise ValueError(f"effective_length_factor must be positive; got {effective_length_factor}")
    effective_length = effective_length_factor * length.pint
    inertia = (
        required_safety_factor
        * design_load.pint
        * effective_length**2
        / (pi**2 * elastic_modulus.pint)
    )
    converted = inertia.to("mm**4")
    return Quantity(magnitude=float(converted.magnitude), unit="mm**4")


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


def aisc_flexural_buckling_stress(
    *,
    yield_strength: Quantity,
    euler_stress: Quantity,
) -> Quantity:
    """The AISC 360 Chapter E flexural buckling stress F_cr of a steel column.

    The modern steel column curve (AISC 360 §E3), a single smooth transition from
    inelastic to elastic buckling based on the ratio of yield to elastic (Euler)
    stress:

    - F_cr = 0.658^(F_y/F_e)·F_y  when F_y/F_e ≤ 2.25 (equivalently KL/r ≤ 4.71√(E/F_y)),
      the inelastic range where residual stresses soften the buckling;
    - F_cr = 0.877·F_e            when F_y/F_e > 2.25, the elastic range, the Euler
      stress knocked down by an out-of-straightness factor.

    ``yield_strength`` F_y is the steel's yield and ``euler_stress`` F_e = π²E/(KL/r)²
    the elastic buckling stress (from :func:`euler_critical_stress` at the effective
    slenderness). The design compressive strength is φ·F_cr·A_g (φ = 0.90). Returns
    F_cr as a stress in MPa.
    """
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(euler_stress, "[pressure]", "euler_stress")
    fy = yield_strength.to("MPa").magnitude
    fe = euler_stress.to("MPa").magnitude
    if fy <= 0 or fe <= 0:
        raise ValueError("yield_strength and euler_stress must be positive")
    if fy / fe <= 2.25:
        fcr = 0.658 ** (fy / fe) * fy
    else:
        fcr = 0.877 * fe
    return Quantity(magnitude=fcr, unit="MPa")


def aisc_plastic_bracing_limit(
    *,
    minor_radius_of_gyration: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The AISC 360 laterally-unbraced length L_p = 1.76·r_y·√(E/F_y) for full plastic
    bending.

    An I-shaped beam can reach its full plastic moment M_p only if its compression
    flange is braced against lateral-torsional buckling at a spacing no greater than
    L_p (AISC 360 §F2.2): L_p = 1.76·r_y·√(E/F_y), where ``minor_radius_of_gyration``
    r_y is the section's weak-axis radius of gyration, ``yield_strength`` F_y, and
    ``elastic_modulus`` E. Beyond L_p the moment capacity falls — first linearly (the
    inelastic-LTB range up to L_r), then elastically. A stockier section (large r_y) or
    a lower-strength steel tolerates a longer unbraced length. Returns L_p in mm.
    """
    _require(minor_radius_of_gyration, "[length]", "minor_radius_of_gyration")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    ry = minor_radius_of_gyration.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if ry <= 0 or fy <= 0 or e <= 0:
        raise ValueError("all inputs must be positive")
    return Quantity(magnitude=1.76 * ry * sqrt(e / fy), unit="mm")


def aisc_effective_radius_of_gyration(
    *,
    minor_second_moment: Quantity,
    elastic_section_modulus: Quantity,
    flange_centroid_distance: Quantity,
) -> Quantity:
    """The AISC 360 §F2 effective radius of gyration r_ts of a doubly-symmetric I-shape.

    r_ts is the section property that governs lateral-torsional buckling, feeding the
    inelastic-LTB limit L_r (:func:`aisc_inelastic_ltb_limit`). Its general definition
    r_ts² = √(I_y·C_w)/S_x collapses, for a doubly-symmetric I whose warping constant is
    C_w = I_y·h_o²/4, to the clean r_ts = √(I_y·h_o/(2·S_x)). ``minor_second_moment`` I_y is
    the weak-axis second moment, ``elastic_section_modulus`` S_x the strong-axis section
    modulus, and ``flange_centroid_distance`` h_o the distance between the flange centroids.
    r_ts sits a little above the flange's own radius of gyration; it is what turns the
    section geometry into the L_r brace-spacing limit. Returns r_ts in mm.
    """
    if not minor_second_moment.has_dimension("[length]**4"):
        raise ValueError("minor_second_moment must be a [length]**4 quantity")
    if not elastic_section_modulus.has_dimension("[length]**3"):
        raise ValueError("elastic_section_modulus must be a [length]**3 quantity")
    _require(flange_centroid_distance, "[length]", "flange_centroid_distance")
    iy = minor_second_moment.to("mm**4").magnitude
    sx = elastic_section_modulus.to("mm**3").magnitude
    ho = flange_centroid_distance.to("mm").magnitude
    if iy <= 0 or sx <= 0 or ho <= 0:
        raise ValueError("all inputs must be positive")
    return Quantity(magnitude=sqrt(iy * ho / (2.0 * sx)), unit="mm")


def aisc_inelastic_ltb_limit(
    *,
    effective_radius_of_gyration: Quantity,
    torsion_constant: Quantity,
    elastic_section_modulus: Quantity,
    flange_centroid_distance: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
    section_coefficient: float = 1.0,
) -> Quantity:
    """The AISC 360 §F2 limiting unbraced length L_r for inelastic lateral-torsional buckling.

    L_r is the brace spacing beyond which a beam buckles *elastically* rather than
    inelastically — the upper anchor of the sloping line that :func:`aisc_inelastic_ltb_moment`
    interpolates from L_p (:func:`aisc_plastic_bracing_limit`). AISC 360 Eq. F2-5:

        L_r = 1.95·r_ts·(E/(0.7·F_y))·√( J·c/(S_x·h_o) + √((J·c/(S_x·h_o))² + 6.76·(0.7·F_y/E)²) ).

    ``effective_radius_of_gyration`` r_ts (the LTB radius of gyration, r_ts² = √(I_y·C_w)/S_x),
    ``torsion_constant`` J, ``elastic_section_modulus`` S_x (strong axis),
    ``flange_centroid_distance`` h_o (between flange centroids), ``yield_strength`` F_y,
    ``elastic_modulus`` E, and ``section_coefficient`` c — 1.0 for a doubly-symmetric
    I-shape (the default), (h_o/2)·√(I_y/C_w) for a channel. The 0.7·F_y term is the
    flange stress net of residual stress. Returns L_r in mm.
    """
    _require(effective_radius_of_gyration, "[length]", "effective_radius_of_gyration")
    _require(torsion_constant, "[length]**4", "torsion_constant")
    _require(elastic_section_modulus, "[length]**3", "elastic_section_modulus")
    _require(flange_centroid_distance, "[length]", "flange_centroid_distance")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    rts = effective_radius_of_gyration.to("mm").magnitude
    j = torsion_constant.to("mm**4").magnitude
    sx = elastic_section_modulus.to("mm**3").magnitude
    ho = flange_centroid_distance.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if min(rts, j, sx, ho, fy, e) <= 0:
        raise ValueError("all inputs must be positive")
    if section_coefficient <= 0:
        raise ValueError(f"section_coefficient must be positive; got {section_coefficient}")
    term = j * section_coefficient / (sx * ho)
    f_ratio = 0.7 * fy / e
    l_r = 1.95 * rts * (1.0 / f_ratio) * sqrt(term + sqrt(term**2 + 6.76 * f_ratio**2))
    return Quantity(magnitude=l_r, unit="mm")


def aisc_elastic_ltb_stress(
    *,
    unbraced_length: Quantity,
    effective_radius_of_gyration: Quantity,
    torsion_constant: Quantity,
    elastic_section_modulus: Quantity,
    flange_centroid_distance: Quantity,
    elastic_modulus: Quantity,
    moment_gradient_factor: float = 1.0,
    section_coefficient: float = 1.0,
) -> Quantity:
    """The AISC 360 §F2.2(b) elastic lateral-torsional buckling stress F_cr (Eq. F2-4).

    Beyond the inelastic limit L_r (:func:`aisc_inelastic_ltb_limit`) a beam buckles
    elastically, and this is the code-accurate critical stress — the one that includes both
    the St-Venant torsion and the warping term the simplified
    :func:`lateral_torsional_buckling_moment` leaves out:

        F_cr = (C_b·π²·E/(L_b/r_ts)²)·√(1 + 0.078·(J·c/(S_x·h_o))·(L_b/r_ts)²).

    The flexural strength is then M_n = F_cr·S_x (capped at M_p). ``unbraced_length`` L_b,
    ``effective_radius_of_gyration`` r_ts (:func:`aisc_effective_radius_of_gyration`),
    ``torsion_constant`` J, ``elastic_section_modulus`` S_x, ``flange_centroid_distance``
    h_o, ``elastic_modulus`` E, the ``moment_gradient_factor`` C_b (1.0 for uniform moment;
    higher for a varying moment), and ``section_coefficient`` c (1.0 for a doubly-symmetric
    I). The √ term is the warping contribution — it makes a compact, stocky-flanged beam
    noticeably stronger than the pure-torsion estimate. Returns F_cr in MPa.
    """
    _require(unbraced_length, "[length]", "unbraced_length")
    _require(effective_radius_of_gyration, "[length]", "effective_radius_of_gyration")
    if not torsion_constant.has_dimension("[length]**4"):
        raise ValueError("torsion_constant must be a [length]**4 quantity")
    if not elastic_section_modulus.has_dimension("[length]**3"):
        raise ValueError("elastic_section_modulus must be a [length]**3 quantity")
    _require(flange_centroid_distance, "[length]", "flange_centroid_distance")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    lb = unbraced_length.to("mm").magnitude
    rts = effective_radius_of_gyration.to("mm").magnitude
    j = torsion_constant.to("mm**4").magnitude
    sx = elastic_section_modulus.to("mm**3").magnitude
    ho = flange_centroid_distance.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if min(lb, rts, j, sx, ho, e) <= 0:
        raise ValueError("all quantity inputs must be positive")
    if moment_gradient_factor <= 0:
        raise ValueError(f"moment_gradient_factor must be positive; got {moment_gradient_factor}")
    if section_coefficient <= 0:
        raise ValueError(f"section_coefficient must be positive; got {section_coefficient}")
    slenderness = lb / rts
    term = j * section_coefficient / (sx * ho)
    f_cr = (
        moment_gradient_factor
        * pi**2
        * e
        / slenderness**2
        * sqrt(1.0 + 0.078 * term * slenderness**2)
    )
    return Quantity(magnitude=f_cr, unit="MPa")


def aisc_inelastic_ltb_moment(
    *,
    plastic_moment: Quantity,
    residual_yield_moment: Quantity,
    unbraced_length: Quantity,
    plastic_limit: Quantity,
    inelastic_limit: Quantity,
    moment_gradient_factor: float = 1.0,
) -> Quantity:
    """The AISC 360 §F2.2 flexural strength M_n in the inelastic LTB range.

    Between the plastic-bracing limit L_p (:func:`aisc_plastic_bracing_limit`) and the
    inelastic limit L_r, a compact I-beam's capacity falls linearly from the plastic
    moment toward the residual-yield moment as the unbraced length grows:

        M_n = C_b·[M_p − (M_p − 0.7·F_y·S_x)·(L_b − L_p)/(L_r − L_p)] ≤ M_p.

    ``plastic_moment`` M_p and ``residual_yield_moment`` 0.7·F_y·S_x (the moment at L_r)
    are the anchors, ``unbraced_length`` L_b the actual brace spacing, ``plastic_limit``
    L_p and ``inelastic_limit`` L_r the range bounds, and ``moment_gradient_factor`` C_b
    the moment-gradient factor (1.0 for uniform moment; higher for a varying moment
    braces the beam more). At or below L_p the strength is M_p; beyond L_r use the
    elastic form (:func:`lateral_torsional_buckling_moment`). The result is capped at
    M_p. Returns M_n in kN·m.
    """
    _require(plastic_moment, "[force] * [length]", "plastic_moment")
    _require(residual_yield_moment, "[force] * [length]", "residual_yield_moment")
    _require(unbraced_length, "[length]", "unbraced_length")
    _require(plastic_limit, "[length]", "plastic_limit")
    _require(inelastic_limit, "[length]", "inelastic_limit")
    mp = plastic_moment.to("kN*m").magnitude
    mr = residual_yield_moment.to("kN*m").magnitude
    lb = unbraced_length.to("mm").magnitude
    lp = plastic_limit.to("mm").magnitude
    lr = inelastic_limit.to("mm").magnitude
    if mp <= 0 or mr <= 0 or lb <= 0 or lp <= 0 or lr <= 0:
        raise ValueError("the moments and lengths must be positive")
    if moment_gradient_factor <= 0:
        raise ValueError(f"moment_gradient_factor must be positive; got {moment_gradient_factor}")
    if lr <= lp:
        raise ValueError("inelastic_limit L_r must exceed plastic_limit L_p")
    if lb <= lp:
        return Quantity(magnitude=mp, unit="kN*m")
    if lb > lr:
        raise ValueError(
            "unbraced_length exceeds L_r — elastic LTB governs; use "
            "lateral_torsional_buckling_moment"
        )
    mn = moment_gradient_factor * (mp - (mp - mr) * (lb - lp) / (lr - lp))
    return Quantity(magnitude=min(mn, mp), unit="kN*m")


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


def perry_robertson_stress(
    *,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
    slenderness_ratio: float,
    imperfection_factor: float,
) -> Quantity:
    """The Perry-Robertson mean compressive stress of an imperfect column.

    Real columns are never perfectly straight, and the Perry-Robertson model —
    the basis of the column curves in modern design codes — sizes them by asking
    when an initially-crooked column's peak fibre first reaches yield. With the
    Euler stress σ_e = π²·E/λ², the yield strength σ_y, and the Perry imperfection
    factor η (a dimensionless measure of the initial crookedness, supplied like any
    code coefficient — η = 0 is the perfect column), the failure stress is the
    smaller root of the interaction quadratic:

        σ_c = ½·[ (σ_y + (η+1)·σ_e) − √((σ_y + (η+1)·σ_e)² − 4·σ_y·σ_e) ].

    A perfect column (η = 0) recovers σ_c = min(σ_y, σ_e) — it fails by yield when
    stocky and by Euler buckling when slender — and any η > 0 knocks the capacity
    below that, most sharply near the transition slenderness. ``slenderness_ratio``
    λ must be positive and ``imperfection_factor`` η non-negative. Returns the mean
    stress at failure in MPa.
    """
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if slenderness_ratio <= 0:
        raise ValueError(f"slenderness_ratio must be positive; got {slenderness_ratio}")
    if imperfection_factor < 0:
        raise ValueError(f"imperfection_factor must be non-negative; got {imperfection_factor}")
    sy = yield_strength.to("MPa").magnitude
    se = pi**2 * elastic_modulus.to("MPa").magnitude / slenderness_ratio**2
    b = sy + (imperfection_factor + 1.0) * se
    sigma_c = 0.5 * (b - sqrt(b**2 - 4.0 * sy * se))
    return Quantity(magnitude=sigma_c, unit="MPa")


def lateral_torsional_buckling_moment(
    *,
    unbraced_length: Quantity,
    weak_axis_second_moment: Quantity,
    torsion_constant: Quantity,
    elastic_modulus: Quantity,
    shear_modulus: Quantity,
) -> Quantity:
    """The elastic lateral-torsional buckling moment M_cr = (π/L)·√(E·I_y·G·J).

    A beam bent about its strong axis can buckle *sideways* — twisting and swaying
    out of plane — long before the material yields, if its compression edge is not
    braced. The classic critical moment for a simply-supported beam under uniform
    moment (no warping restraint) is M_cr = (π/L)·√(E·I_y·G·J), where ``unbraced_length``
    L is the distance between lateral braces, ``weak_axis_second_moment`` I_y the
    minor-axis second moment, ``torsion_constant`` J the section torsion constant,
    ``elastic_modulus`` E, and ``shear_modulus`` G. This is exact for a narrow
    rectangular section and *conservative* for an I-beam (it omits the warping term
    that adds capacity), so it is a safe first screen — brace the beam or deepen it
    if the service moment approaches M_cr. Every argument is dimension-checked and
    must be positive. Returns the critical moment in N·m.
    """
    _require(unbraced_length, "[length]", "unbraced_length")
    _require(weak_axis_second_moment, "[length]**4", "weak_axis_second_moment")
    _require(torsion_constant, "[length]**4", "torsion_constant")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    length = unbraced_length.to("mm").magnitude
    iy = weak_axis_second_moment.to("mm**4").magnitude
    j = torsion_constant.to("mm**4").magnitude
    e = elastic_modulus.to("MPa").magnitude
    g = shear_modulus.to("MPa").magnitude
    if min(length, iy, j, e, g) <= 0:
        raise ValueError("every lateral-torsional-buckling input must be positive")
    m_cr_n_mm = pi / length * sqrt(e * iy * g * j)  # N*mm
    return Quantity(magnitude=m_cr_n_mm / 1000.0, unit="N*m")


def rankine_gordon_stress(
    *,
    crushing_stress: Quantity,
    slenderness_ratio: float,
    rankine_constant: float,
) -> Quantity:
    """The Rankine-Gordon column stress σ_R = σ_c / (1 + a·λ²).

    An empirical column formula (British practice) that blends the two failure modes
    into one smooth curve: at zero slenderness it is the crushing stress σ_c, and as
    slenderness grows the 1/(1 + a·λ²) denominator pulls it down toward the Euler
    curve. σ_R = σ_c / (1 + a·λ²), where ``crushing_stress`` σ_c is the material's
    compressive (yield/crushing) strength, ``slenderness_ratio`` λ = K·L/r the
    effective slenderness, and ``rankine_constant`` a a material constant (≈ 1/7500
    for mild steel, ≈ 1/1600 for cast iron — supplied like any code coefficient, and
    tuned so the curve matches Euler at high λ). It needs no separate transition
    check: one expression covers stubby and slender columns. ``slenderness_ratio``
    must be non-negative and ``rankine_constant`` positive. Returns the allowable
    mean stress in MPa.
    """
    _require(crushing_stress, "[pressure]", "crushing_stress")
    if slenderness_ratio < 0:
        raise ValueError(f"slenderness_ratio must be non-negative; got {slenderness_ratio}")
    if rankine_constant <= 0:
        raise ValueError(f"rankine_constant must be positive; got {rankine_constant}")
    sc = crushing_stress.to("MPa").magnitude
    if sc <= 0:
        raise ValueError(f"crushing_stress must be positive; got {crushing_stress}")
    return Quantity(magnitude=sc / (1.0 + rankine_constant * slenderness_ratio**2), unit="MPa")


def aisc_beam_column_interaction(
    *,
    axial_demand: Quantity,
    axial_capacity: Quantity,
    major_moment_demand: Quantity,
    major_moment_capacity: Quantity,
    minor_moment_demand: Quantity | None = None,
    minor_moment_capacity: Quantity | None = None,
) -> float:
    """The AISC 360 §H1.1 combined axial-and-flexure interaction ratio (≤ 1 passes).

    A member carrying both compression (or tension) and bending is checked with one
    unity equation that trades axial demand against bending demand. §H1.1 uses two forms
    depending on how axial-dominated the member is, with P_r/P_c the axial ratio and
    (M_rx/M_cx + M_ry/M_cy) the summed bending ratio about both axes:

        P_r/P_c ≥ 0.2:  P_r/P_c + (8/9)·(M_rx/M_cx + M_ry/M_cy)
        P_r/P_c < 0.2:  P_r/(2·P_c) + (M_rx/M_cx + M_ry/M_cy).

    ``axial_demand`` P_r and ``axial_capacity`` P_c (the available axial strength),
    ``major_moment_demand`` M_rx and ``major_moment_capacity`` M_cx, and optionally
    ``minor_moment_demand`` M_ry with ``minor_moment_capacity`` M_cy for biaxial bending.
    Capacities are the available strengths (φ·nominal for LRFD, nominal/Ω for ASD) — feed
    demands and capacities in the same basis. Returns the interaction ratio; a value at or
    below 1.0 passes, above 1.0 the member is overloaded.
    """
    _require(axial_demand, "[force]", "axial_demand")
    _require(axial_capacity, "[force]", "axial_capacity")
    _require(major_moment_demand, "[force] * [length]", "major_moment_demand")
    _require(major_moment_capacity, "[force] * [length]", "major_moment_capacity")
    pc = axial_capacity.to("kN").magnitude
    mcx = major_moment_capacity.to("kN*m").magnitude
    if pc <= 0 or mcx <= 0:
        raise ValueError("axial_capacity and major_moment_capacity must be positive")
    pr = axial_demand.to("kN").magnitude
    mrx = major_moment_demand.to("kN*m").magnitude
    if pr < 0 or mrx < 0:
        raise ValueError("axial_demand and major_moment_demand must be non-negative")
    bending_ratio = mrx / mcx
    if minor_moment_demand is not None:
        _require(minor_moment_demand, "[force] * [length]", "minor_moment_demand")
        if minor_moment_capacity is None:
            raise ValueError("minor_moment_capacity is required when minor_moment_demand is given")
        _require(minor_moment_capacity, "[force] * [length]", "minor_moment_capacity")
        mcy = minor_moment_capacity.to("kN*m").magnitude
        mry = minor_moment_demand.to("kN*m").magnitude
        if mcy <= 0:
            raise ValueError("minor_moment_capacity must be positive")
        if mry < 0:
            raise ValueError("minor_moment_demand must be non-negative")
        bending_ratio += mry / mcy
    axial_ratio = pr / pc
    if axial_ratio >= 0.2:
        return axial_ratio + (8.0 / 9.0) * bending_ratio
    return axial_ratio / 2.0 + bending_ratio


def aisc_effective_length_factor_braced(*, g_top: float, g_bottom: float) -> float:
    """The effective-length factor K of a braced-frame column from its joint stiffness ratios.

    A real column is neither perfectly pinned nor fixed; its ends are held by the beams
    framing in, and the AISC alignment chart reads the effective-length factor K from the
    joint stiffness ratio G = Σ(E·I/L)_columns / Σ(E·I/L)_girders at each end. This is the
    Dumonteil closed-form fit to the *braced* (sidesway-prevented) chart:
    K = (3·G_A·G_B + 1.4·(G_A + G_B) + 0.64) / (3·G_A·G_B + 2·(G_A + G_B) + 1.28). ``g_top``
    G_A and ``g_bottom`` G_B are the stiffness ratios at the two ends (AISC recommends
    G ≈ 1.0 for a nominally fixed base and G ≈ 10 for a nominally pinned one, since a real
    footing is neither ideal). K runs from 0.5 (both ends fixed) to 1.0 (both pinned) and is
    always ≤ 1 for a braced frame, so bracing always helps. Feed K·L to the slenderness and
    buckling checks. Returns the dimensionless K.
    """
    if g_top < 0 or g_bottom < 0:
        raise ValueError("g_top and g_bottom must be non-negative")
    a, b = g_top, g_bottom
    return (3.0 * a * b + 1.4 * (a + b) + 0.64) / (3.0 * a * b + 2.0 * (a + b) + 1.28)


def aisc_effective_length_factor_sway(*, g_top: float, g_bottom: float) -> float:
    """The effective-length factor K of a sway-frame column from its joint stiffness ratios.

    The unbraced (sidesway-permitted) companion to
    :func:`aisc_effective_length_factor_braced`: when a frame can lean, its columns are far
    more slender than the braced case, and K exceeds 1.0 — often well above 2. The Dumonteil
    fit to the sway alignment chart is
    K = √[(1.6·G_A·G_B + 4·(G_A + G_B) + 7.5) / (G_A + G_B + 7.5)], with ``g_top`` G_A and
    ``g_bottom`` G_B the joint stiffness ratios (G ≈ 1 for a fixed base, ≈ 10 for a pinned
    one). K = 1.0 with both ends fixed and grows without bound as the ends approach pinned
    (a sway frame on pinned columns is a mechanism). The large K is why an unbraced frame's
    columns govern — bracing or a moment frame is what tames it. Returns the dimensionless K.
    """
    if g_top < 0 or g_bottom < 0:
        raise ValueError("g_top and g_bottom must be non-negative")
    a, b = g_top, g_bottom
    return ((1.6 * a * b + 4.0 * (a + b) + 7.5) / (a + b + 7.5)) ** 0.5


def aisc_moment_amplifier_b1(
    *,
    moment_gradient_coefficient: float,
    required_axial_strength: Quantity,
    elastic_buckling_load: Quantity,
    load_factor: float = 1.0,
) -> float:
    """The AISC 360 §C2 B₁ amplifier for member second-order (P-δ) moments.

    Axial compression bows a member and amplifies the moment along its length; the
    amplified first-order method captures that with B₁ = C_m/(1 − α·P_r/P_e1) ≥ 1.
    ``moment_gradient_coefficient`` C_m accounts for the moment shape (0.6 − 0.4·(M1/M2)
    for a member with no transverse load, 1.0 with one), ``required_axial_strength`` P_r
    the compression, ``elastic_buckling_load`` P_e1 = π²·E·I/(K1·L)² the in-plane elastic
    buckling load, and ``load_factor`` α (1.0 for LRFD, 1.6 for ASD). B₁ never falls below
    1, and it runs away as P_r approaches P_e1 — the signal that the member is too slender.
    Feed B₁·M_nt (plus B₂·M_lt) as the required moment of the §H1.1 interaction
    (:func:`aisc_beam_column_interaction`). Returns the dimensionless amplifier.
    """
    _require(required_axial_strength, "[force]", "required_axial_strength")
    _require(elastic_buckling_load, "[force]", "elastic_buckling_load")
    pr = required_axial_strength.to("kN").magnitude
    pe1 = elastic_buckling_load.to("kN").magnitude
    if pr < 0:
        raise ValueError(
            f"required_axial_strength must be non-negative; got {required_axial_strength}"
        )
    if pe1 <= 0:
        raise ValueError(f"elastic_buckling_load must be positive; got {elastic_buckling_load}")
    if load_factor <= 0:
        raise ValueError(f"load_factor must be positive; got {load_factor}")
    denominator = 1.0 - load_factor * pr / pe1
    if denominator <= 0:
        raise ValueError(
            "alpha*P_r has reached the elastic buckling load P_e1 — the member is "
            "unstable in-plane; increase the section or reduce the load"
        )
    return max(moment_gradient_coefficient / denominator, 1.0)


def aisc_moment_amplifier_b2(
    *,
    story_axial_load: Quantity,
    story_elastic_buckling_strength: Quantity,
    load_factor: float = 1.0,
) -> float:
    """The AISC 360 §C2 B₂ amplifier for frame second-order (P-Δ) sidesway moments.

    When a frame leans, gravity acting through the drift adds moment story-wide; the
    amplified first-order method captures that with B₂ = 1/(1 − α·ΣP_r/ΣP_e,story) ≥ 1.
    ``story_axial_load`` ΣP_r is the total vertical load on the story,
    ``story_elastic_buckling_strength`` ΣP_e,story its elastic sidesway buckling strength
    (R_M·ΣH·L/Δ_H from the first-order drift), and ``load_factor`` α (1.0 LRFD, 1.6 ASD).
    B₂ multiplies the sidesway (lateral-translation) moments M_lt before they enter the
    §H1.1 interaction. A stiff, well-braced story keeps B₂ near 1; a flexible one inflates
    it and can run away — the quantitative stability check on the frame. Returns the
    dimensionless amplifier.
    """
    _require(story_axial_load, "[force]", "story_axial_load")
    _require(story_elastic_buckling_strength, "[force]", "story_elastic_buckling_strength")
    p_story = story_axial_load.to("kN").magnitude
    p_e = story_elastic_buckling_strength.to("kN").magnitude
    if p_story < 0:
        raise ValueError(f"story_axial_load must be non-negative; got {story_axial_load}")
    if p_e <= 0:
        raise ValueError(
            "story_elastic_buckling_strength must be positive; got "
            f"{story_elastic_buckling_strength}"
        )
    if load_factor <= 0:
        raise ValueError(f"load_factor must be positive; got {load_factor}")
    denominator = 1.0 - load_factor * p_story / p_e
    if denominator <= 0:
        raise ValueError(
            "alpha*ΣP_r has reached the story buckling strength — the frame is unstable "
            "in sidesway; stiffen or brace it"
        )
    return max(1.0 / denominator, 1.0)
