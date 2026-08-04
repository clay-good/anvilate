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
