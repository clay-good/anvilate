"""T1 analytical fiber-composite micromechanics (rule of mixtures, closed-form).

A unidirectional fiber-reinforced composite — carbon or glass fibers in an epoxy
matrix, the material of aircraft skins, wind-turbine blades, and boat hulls — has
wildly different stiffness along the fibers versus across them, and the rule of
mixtures estimates both from the constituent properties and the fiber volume
fraction V_f. Along the fibers the two phases share the *strain* (they act in
parallel), so the modulus is the volume-weighted average

    E₁ = V_f·E_f + (1 − V_f)·E_m,

fiber-dominated and stiff. Across the fibers they share the *stress* (in series),
and the inverse rule

    1/E₂ = V_f/E_f + (1 − V_f)/E_m

gives a much lower, matrix-dominated modulus. The longitudinal strength follows the
same parallel rule. The fiber and matrix properties and V_f are the caller's inputs;
this module evaluates the closed forms. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values (V_f is a plain fraction in [0, 1]).

Sources: Jones, *Mechanics of Composite Materials*, and Daniel & Ishai,
*Engineering Mechanics of Composite Materials*, for the rule-of-mixtures and
lamina-stiffness relations.
"""

from __future__ import annotations

from math import cos, radians, sin

from ..units import Quantity, require_finite

__all__ = [
    "fiber_volume_fraction_from_weight_fraction",
    "rule_of_mixtures_modulus",
    "transverse_modulus_inverse_rule",
    "rule_of_mixtures_strength",
    "composite_major_poisson_ratio",
    "composite_shear_modulus_inverse_rule",
    "composite_longitudinal_cte",
    "critical_fiber_length",
    "tsai_hill_failure_index",
    "off_axis_modulus",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


def _fraction(fiber_fraction: float) -> float:
    if not 0.0 <= fiber_fraction <= 1.0:
        raise ValueError(f"fiber_fraction must lie in [0, 1]; got {fiber_fraction}")
    return fiber_fraction


def rule_of_mixtures_modulus(
    *,
    fiber_fraction: float,
    fiber_modulus: Quantity,
    matrix_modulus: Quantity,
) -> Quantity:
    """The longitudinal (along-fiber) modulus E₁ = V_f·E_f + (1 − V_f)·E_m of a composite.

    Loaded along the fibers, the stiff fibers and compliant matrix stretch together
    (iso-strain), so their moduli average by volume — the fibers dominate, giving the high
    axial stiffness a unidirectional laminate is chosen for. ``fiber_fraction`` V_f is the
    fiber volume fraction (0 to 1, typically 0.5–0.65), ``fiber_modulus`` E_f, and
    ``matrix_modulus`` E_m. This is the *upper* (Voigt) bound on the composite modulus and
    the value for on-axis loading. Returns E₁ in MPa.
    """
    _require(fiber_modulus, "[pressure]", "fiber_modulus")
    _require(matrix_modulus, "[pressure]", "matrix_modulus")
    vf = _fraction(fiber_fraction)
    ef = fiber_modulus.to("MPa").magnitude
    em = matrix_modulus.to("MPa").magnitude
    if ef <= 0 or em <= 0:
        raise ValueError("fiber_modulus and matrix_modulus must be positive")
    return Quantity(magnitude=vf * ef + (1.0 - vf) * em, unit="MPa")


def transverse_modulus_inverse_rule(
    *,
    fiber_fraction: float,
    fiber_modulus: Quantity,
    matrix_modulus: Quantity,
) -> Quantity:
    """The transverse (across-fiber) modulus E₂, 1/E₂ = V_f/E_f + (1 − V_f)/E_m.

    Loaded across the fibers, the fibers and matrix carry the same *stress* in series
    (iso-stress), so their compliances add — and because the soft matrix must transfer the
    load, E₂ is far below the longitudinal E₁ and only weakly helped by the fibers. This is
    the inverse (Reuss) rule, the *lower* bound on the composite modulus and the reason a
    unidirectional ply is weak transversely (why real laminates cross-ply). ``fiber_fraction``
    V_f, ``fiber_modulus`` E_f, and ``matrix_modulus`` E_m as in
    :func:`rule_of_mixtures_modulus`. Returns E₂ in MPa.
    """
    _require(fiber_modulus, "[pressure]", "fiber_modulus")
    _require(matrix_modulus, "[pressure]", "matrix_modulus")
    vf = _fraction(fiber_fraction)
    ef = fiber_modulus.to("MPa").magnitude
    em = matrix_modulus.to("MPa").magnitude
    if ef <= 0 or em <= 0:
        raise ValueError("fiber_modulus and matrix_modulus must be positive")
    return Quantity(magnitude=1.0 / (vf / ef + (1.0 - vf) / em), unit="MPa")


def rule_of_mixtures_strength(
    *,
    fiber_fraction: float,
    fiber_strength: Quantity,
    matrix_stress_at_fiber_failure: Quantity,
) -> Quantity:
    """The longitudinal tensile strength σ₁ = V_f·σ_f + (1 − V_f)·σ_m* of a composite.

    In a fiber-dominated composite the fibers and matrix strain together until the fibers
    reach their failure strain and break, taking the laminate with them, so the longitudinal
    strength is the parallel rule σ₁ = V_f·σ_fu + (1 − V_f)·σ_m*, where σ_m* is the *matrix*
    stress at that fiber-failure strain (E_m·ε_fu, well below the matrix's own ultimate).
    ``fiber_fraction`` V_f, ``fiber_strength`` σ_fu the fiber tensile strength, and
    ``matrix_stress_at_fiber_failure`` σ_m*. Above a minimum fiber fraction the fibers
    carry nearly all the load, so σ₁ tracks V_f·σ_fu. Returns σ₁ in MPa.
    """
    _require(fiber_strength, "[pressure]", "fiber_strength")
    _require(matrix_stress_at_fiber_failure, "[pressure]", "matrix_stress_at_fiber_failure")
    vf = _fraction(fiber_fraction)
    sf = fiber_strength.to("MPa").magnitude
    sm = matrix_stress_at_fiber_failure.to("MPa").magnitude
    if sf <= 0 or sm < 0:
        raise ValueError(
            "fiber_strength must be positive and matrix_stress_at_fiber_failure non-negative"
        )
    return Quantity(magnitude=vf * sf + (1.0 - vf) * sm, unit="MPa")


def composite_major_poisson_ratio(
    *,
    fiber_fraction: float,
    fiber_poisson: float,
    matrix_poisson: float,
) -> float:
    """The major Poisson's ratio ν₁₂ = V_f·ν_f + (1 − V_f)·ν_m of a unidirectional ply.

    The third of a lamina's four independent elastic constants (with E₁, E₂, and G₁₂):
    ν₁₂ is the transverse contraction under longitudinal tension, and it follows the same
    parallel rule of mixtures as the longitudinal modulus. ``fiber_fraction`` V_f,
    ``fiber_poisson`` ν_f, and ``matrix_poisson`` ν_m (each in [0, 0.5)). It sits between the
    fiber and matrix values; the *minor* ratio ν₂₁ follows from the reciprocity
    ν₂₁ = ν₁₂·E₂/E₁. Returns the dimensionless ν₁₂.
    """
    vf = _fraction(fiber_fraction)
    for value, name in ((fiber_poisson, "fiber_poisson"), (matrix_poisson, "matrix_poisson")):
        if not 0.0 <= value < 0.5:
            raise ValueError(f"{name} must lie in [0, 0.5); got {value}")
    return vf * fiber_poisson + (1.0 - vf) * matrix_poisson


def composite_shear_modulus_inverse_rule(
    *,
    fiber_fraction: float,
    fiber_shear_modulus: Quantity,
    matrix_shear_modulus: Quantity,
) -> Quantity:
    """The in-plane shear modulus G₁₂, 1/G₁₂ = V_f/G_f + (1 − V_f)/G_m of a ply.

    The fourth independent elastic constant of a unidirectional lamina. In-plane shear loads
    the fibers and matrix in series much like transverse tension, so G₁₂ follows the inverse
    rule and is matrix-dominated and low — the simple lower-bound estimate (real plies run
    higher; a Halpin-Tsai fit is closer, but the inverse rule is the standard first screen).
    ``fiber_fraction`` V_f, ``fiber_shear_modulus`` G_f, and ``matrix_shear_modulus`` G_m.
    Returns G₁₂ in MPa.
    """
    _require(fiber_shear_modulus, "[pressure]", "fiber_shear_modulus")
    _require(matrix_shear_modulus, "[pressure]", "matrix_shear_modulus")
    vf = _fraction(fiber_fraction)
    gf = fiber_shear_modulus.to("MPa").magnitude
    gm = matrix_shear_modulus.to("MPa").magnitude
    if gf <= 0 or gm <= 0:
        raise ValueError("fiber_shear_modulus and matrix_shear_modulus must be positive")
    return Quantity(magnitude=1.0 / (vf / gf + (1.0 - vf) / gm), unit="MPa")


def composite_longitudinal_cte(
    *,
    fiber_fraction: float,
    fiber_modulus: Quantity,
    matrix_modulus: Quantity,
    fiber_cte: Quantity,
    matrix_cte: Quantity,
) -> Quantity:
    """The longitudinal thermal-expansion coefficient α₁ of a unidirectional ply.

    Along the fibers the two phases must expand together, and the stiff fibers win, so the
    laminate CTE is *stiffness*-weighted, not volume-weighted:
    α₁ = (V_f·E_f·α_f + (1 − V_f)·E_m·α_m)/(V_f·E_f + (1 − V_f)·E_m). Because carbon fiber has
    a near-zero (even slightly negative) axial CTE, a carbon/epoxy laminate is almost
    dimensionally stable along the fibers — the property that makes CFRP the choice for
    satellite optical benches and precision structures. ``fiber_fraction`` V_f,
    ``fiber_modulus`` E_f, ``matrix_modulus`` E_m, ``fiber_cte`` α_f, and ``matrix_cte`` α_m
    (each a 1/temperature quantity). The transverse α₂ is much larger (matrix-dominated) and
    needs the Schapery form, not this. Returns α₁ in 1/K.
    """
    _require(fiber_modulus, "[pressure]", "fiber_modulus")
    _require(matrix_modulus, "[pressure]", "matrix_modulus")
    if not fiber_cte.has_dimension("1 / [temperature]"):
        raise ValueError(
            f"fiber_cte must have units of 1/temperature; got {fiber_cte.dimensionality}"
        )
    if not matrix_cte.has_dimension("1 / [temperature]"):
        raise ValueError(
            f"matrix_cte must have units of 1/temperature; got {matrix_cte.dimensionality}"
        )
    vf = _fraction(fiber_fraction)
    ef = fiber_modulus.to("MPa").magnitude
    em = matrix_modulus.to("MPa").magnitude
    af = fiber_cte.to("1/K").magnitude
    am = matrix_cte.to("1/K").magnitude
    if ef <= 0 or em <= 0:
        raise ValueError("fiber_modulus and matrix_modulus must be positive")
    stiffness = vf * ef + (1.0 - vf) * em
    alpha1 = (vf * ef * af + (1.0 - vf) * em * am) / stiffness
    return Quantity(magnitude=alpha1, unit="1/K")


def critical_fiber_length(
    *,
    fiber_strength: Quantity,
    fiber_diameter: Quantity,
    interface_shear_strength: Quantity,
) -> Quantity:
    """The critical fiber length ℓ_c = σ_fu·d/(2·τ) for load transfer in a short-fiber composite.

    A short (chopped, injection-moulded) fiber is not gripped along its whole length — the
    matrix builds up tension in it through interface shear, from zero at each end. Only a
    fiber at least ℓ_c long can be stressed all the way to its own strength before it pulls
    out, so ℓ_c sets whether reinforcement is fiber-limited (fibers break, strong) or
    interface-limited (fibers pull out, weak). ℓ_c = σ_fu·d/(2·τ), where ``fiber_strength``
    σ_fu is the fiber tensile strength, ``fiber_diameter`` d, and ``interface_shear_strength``
    τ the fiber-matrix (or matrix yield) shear strength. Practical chopped fibers are made a
    few times ℓ_c so most of each fiber is fully effective. Returns ℓ_c in mm.
    """
    _require(fiber_strength, "[pressure]", "fiber_strength")
    _require(fiber_diameter, "[length]", "fiber_diameter")
    _require(interface_shear_strength, "[pressure]", "interface_shear_strength")
    sfu = fiber_strength.to("MPa").magnitude
    d = fiber_diameter.to("mm").magnitude
    tau = interface_shear_strength.to("MPa").magnitude
    if sfu <= 0 or d <= 0 or tau <= 0:
        raise ValueError("all inputs must be positive")
    return Quantity(magnitude=sfu * d / (2.0 * tau), unit="mm")


def tsai_hill_failure_index(
    *,
    longitudinal_stress: Quantity,
    transverse_stress: Quantity,
    shear_stress: Quantity,
    longitudinal_strength: Quantity,
    transverse_strength: Quantity,
    shear_strength: Quantity,
) -> float:
    """The Tsai-Hill first-ply-failure index of a lamina under combined in-plane stress.

    A composite ply rarely sees pure longitudinal load; it carries σ₁, σ₂, and τ₁₂ together,
    and the Tsai-Hill criterion combines them into one interactive index,
    FI = (σ₁/X)² − σ₁·σ₂/X² + (σ₂/Y)² + (τ₁₂/S)². The ply is predicted to fail when FI reaches
    1.0, so FI is the fraction of strength used and 1/√FI is the load factor on a
    proportional stress state. ``longitudinal_stress`` σ₁ and ``transverse_stress`` σ₂ are the
    ply-axis normal stresses (signed) and ``shear_stress`` τ₁₂ the in-plane shear;
    ``longitudinal_strength`` X, ``transverse_strength`` Y, and ``shear_strength`` S are the
    corresponding strengths — use the *tensile* or *compressive* X, Y to match the sign of
    each normal stress. Because Y (transverse) is small, a modest σ₂ often drives failure,
    which is why unidirectional plies are laid up in several directions. Returns the
    dimensionless failure index (≥ 1 means first-ply failure).
    """
    _require(longitudinal_stress, "[pressure]", "longitudinal_stress")
    _require(transverse_stress, "[pressure]", "transverse_stress")
    _require(shear_stress, "[pressure]", "shear_stress")
    _require(longitudinal_strength, "[pressure]", "longitudinal_strength")
    _require(transverse_strength, "[pressure]", "transverse_strength")
    _require(shear_strength, "[pressure]", "shear_strength")
    s1 = longitudinal_stress.to("MPa").magnitude
    s2 = transverse_stress.to("MPa").magnitude
    t12 = shear_stress.to("MPa").magnitude
    x = longitudinal_strength.to("MPa").magnitude
    y = transverse_strength.to("MPa").magnitude
    s = shear_strength.to("MPa").magnitude
    if x <= 0 or y <= 0 or s <= 0:
        raise ValueError("the strengths must be positive")
    return (s1 / x) ** 2 - s1 * s2 / x**2 + (s2 / y) ** 2 + (t12 / s) ** 2


def off_axis_modulus(
    *,
    angle: float,
    longitudinal_modulus: Quantity,
    transverse_modulus: Quantity,
    shear_modulus: Quantity,
    major_poisson: float,
) -> Quantity:
    """The apparent modulus E_x of a lamina loaded at an angle θ to its fibers.

    Rotate the load off the fiber axis and the ply's stiffness collapses toward its weak
    directions — the transformation of the four ply constants into the loading axis:

        1/E_x = cos⁴θ/E₁ + (1/G₁₂ − 2·ν₁₂/E₁)·sin²θ·cos²θ + sin⁴θ/E₂.

    At θ = 0 it is the stiff E₁, at 90° the soft E₂, and near 45° the shear term dominates
    and E_x drops close to E₂ even though the fibers are only halfway turned — the reason a
    single off-axis ply is a poor structural choice and laminates stack 0/±45/90 plies.
    ``angle`` θ is the load direction relative to the fibers **in degrees**,
    ``longitudinal_modulus`` E₁, ``transverse_modulus`` E₂, ``shear_modulus`` G₁₂, and
    ``major_poisson`` ν₁₂ (the four ply constants, e.g. from the rule-of-mixtures functions).
    Returns E_x in MPa.
    """
    _require(longitudinal_modulus, "[pressure]", "longitudinal_modulus")
    _require(transverse_modulus, "[pressure]", "transverse_modulus")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    e1 = longitudinal_modulus.to("MPa").magnitude
    e2 = transverse_modulus.to("MPa").magnitude
    g12 = shear_modulus.to("MPa").magnitude
    if e1 <= 0 or e2 <= 0 or g12 <= 0:
        raise ValueError("the moduli must be positive")
    if not -0.5 < major_poisson < 1.0:
        raise ValueError(f"major_poisson is out of a physical range; got {major_poisson}")
    theta = radians(angle)
    c = cos(theta)
    s = sin(theta)
    compliance = c**4 / e1 + (1.0 / g12 - 2.0 * major_poisson / e1) * s**2 * c**2 + s**4 / e2
    if compliance <= 0:
        raise ValueError("the computed compliance is non-positive; check the ply constants")
    return Quantity(magnitude=1.0 / compliance, unit="MPa")


def fiber_volume_fraction_from_weight_fraction(
    *, fiber_weight_fraction: float, fiber_density: Quantity, matrix_density: Quantity
) -> float:
    """The fiber volume fraction from a weight fraction, V_f = (W_f/ρ_f)/(W_f/ρ_f + W_m/ρ_m).

    Every function in this module consumes the fiber *volume* fraction V_f, and the module
    docstring says V_f is the caller's input — but prepreg, tow, and resin-content data sheets are
    quoted by *weight*. This converts, from the ``fiber_weight_fraction`` W_f and the two
    densities: divide each phase's mass fraction by its density to get relative volumes, then
    normalise.

    Feeding a weight fraction straight in where a volume fraction belongs is a silent and
    consistently unconservative error, because fibers are denser than resin so V_f < W_f always.
    Carbon/epoxy at W_f = 0.60 with ρ_f = 1800 and ρ_m = 1200 kg/m³ is V_f = 0.50, and
    :func:`rule_of_mixtures_modulus` reports 139.4 GPa on the weight fraction against the correct
    116.7 — **19% stiff**, propagating into :func:`rule_of_mixtures_strength`,
    :func:`tsai_hill_failure_index`, and :func:`composite_longitudinal_cte` with nothing
    dimensional to signal it, since both fractions are plain floats in (0, 1).

    The composite density falls out of the same numbers as ρ_c = V_f·ρ_f + (1 − V_f)·ρ_m, and
    W_f = V_f·ρ_f/ρ_c inverts it exactly. When the two densities are equal, volume and weight
    fractions coincide. Returns the fiber volume fraction as a plain float.
    """
    _require(fiber_density, "[mass]/[volume]", "fiber_density")
    _require(matrix_density, "[mass]/[volume]", "matrix_density")
    if not 0.0 <= fiber_weight_fraction <= 1.0:
        raise ValueError(f"fiber_weight_fraction must lie in [0, 1]; got {fiber_weight_fraction}")
    rho_f = fiber_density.to("kg/m**3").magnitude
    rho_m = matrix_density.to("kg/m**3").magnitude
    if rho_f <= 0 or rho_m <= 0:
        raise ValueError("fiber_density and matrix_density must be positive")
    fiber_volume = fiber_weight_fraction / rho_f
    matrix_volume = (1.0 - fiber_weight_fraction) / rho_m
    return fiber_volume / (fiber_volume + matrix_volume)
