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
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "rule_of_mixtures_modulus",
    "transverse_modulus_inverse_rule",
    "rule_of_mixtures_strength",
    "composite_major_poisson_ratio",
    "composite_shear_modulus_inverse_rule",
    "composite_longitudinal_cte",
    "critical_fiber_length",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


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
