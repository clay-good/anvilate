"""T1 analytical wire/rod drawing checks (closed-form).

Drawing pulls a wire or rod through a conical die to reduce its diameter — the process behind every
drawn wire, from piano strings to cable. It is the fourth canonical metal-forming process with
:mod:`anvilate.analysis.forging`, :mod:`anvilate.analysis.rolling`, and
:mod:`anvilate.analysis.extrusion`, and it differs from them in one decisive way: the force is
applied by *pulling* the exit, so the drawn wire itself has to carry the draw stress — and if it
reaches the wire's own strength, the wire simply necks and snaps instead of drawing.

The draw stress to pull the wire down is σ_d = Y_avg·ln(A₀/A_f)·(1 + μ/tan α): the average flow
stress Y_avg times the natural strain ln(A₀/A_f) of the area reduction, raised by the die friction
term (1 + μ/tan α) for a die of semi-angle α and a friction coefficient μ. The draw force is that
stress over the exit area, F = σ_d·A_f.

The self-limiting failure mode is what sets drawing apart. Since the exit wire carries σ_d, a pass
can only reduce so much before σ_d reaches the flow stress and the wire yields at the exit: the
maximum area reduction per pass is r_max = 1 − exp(−1/(1 + μ/tan α)), which for a frictionless die
is the classic 1 − 1/e ≈ 0.63. Bigger reductions are split across many dies in a drawing train — the
reason wire is drawn in successive passes, not one.
"""

from __future__ import annotations

from math import exp, log, radians, tan

from ..units import Quantity

__all__ = [
    "wire_drawing_force",
    "wire_drawing_max_reduction",
    "wire_drawing_stress",
]


def wire_drawing_stress(
    *,
    flow_stress: Quantity,
    initial_area: Quantity,
    final_area: Quantity,
    die_half_angle: float,
    friction_coefficient: float,
) -> Quantity:
    """The draw stress to pull a wire down, σ_d = Y_avg·ln(A₀/A_f)·(1 + μ/tan α).

    The tensile stress the drawn wire must carry to reduce from an ``initial_area`` A₀ to a
    ``final_area`` A_f through a die of ``die_half_angle`` α (degrees) with a
    ``friction_coefficient`` μ: σ_d = Y_avg·ln(A₀/A_f)·(1 + μ/tan α), from the average
    ``flow_stress`` Y_avg of the
    (work-hardening) metal. The ln term is the ideal deformation work; the (1 + μ/tan α) term is the
    die friction. This stress is carried by the exit wire, so it must stay below the wire's flow
    stress or the wire snaps (see :func:`wire_drawing_max_reduction`). Returns the stress in MPa.
    """
    _check(flow_stress, "[pressure]", "flow_stress")
    _check(initial_area, "[area]", "initial_area")
    _check(final_area, "[area]", "final_area")
    y = flow_stress.to("MPa").magnitude
    a0 = initial_area.to("mm**2").magnitude
    af = final_area.to("mm**2").magnitude
    if y <= 0:
        raise ValueError("flow_stress must be positive")
    if a0 <= 0 or af <= 0:
        raise ValueError("initial_area and final_area must be positive")
    if af >= a0:
        raise ValueError("final_area must be smaller than initial_area (drawing reduces area)")
    if not 0.0 < die_half_angle < 90.0:
        raise ValueError("die_half_angle must be in (0, 90) degrees")
    if friction_coefficient < 0:
        raise ValueError("friction_coefficient must be non-negative")
    friction_factor = 1.0 + friction_coefficient / tan(radians(die_half_angle))
    return Quantity(magnitude=y * log(a0 / af) * friction_factor, unit="MPa")


def wire_drawing_force(*, drawing_stress: Quantity, final_area: Quantity) -> Quantity:
    """The draw force, F = σ_d·A_f.

    The pull the drawing bench must apply: the ``drawing_stress`` σ_d (from
    :func:`wire_drawing_stress`) acting on the ``final_area`` A_f of the exit wire, F = σ_d·A_f. It
    is the tension the drawn wire carries — the same tension that limits how much a pass can reduce.
    Returns the draw force in kN.
    """
    _check(drawing_stress, "[pressure]", "drawing_stress")
    _check(final_area, "[area]", "final_area")
    sigma = drawing_stress.to("Pa").magnitude
    af = final_area.to("m**2").magnitude
    if sigma <= 0:
        raise ValueError("drawing_stress must be positive")
    if af <= 0:
        raise ValueError("final_area must be positive")
    return Quantity(magnitude=sigma * af / 1000.0, unit="kN")


def wire_drawing_max_reduction(*, die_half_angle: float, friction_coefficient: float) -> float:
    """The maximum area reduction per pass, r_max = 1 − exp(−1/(1 + μ/tan α)).

    The largest fractional area reduction a single die can take before the draw stress reaches the
    wire's flow stress and the wire yields at the exit instead of drawing: setting σ_d = Y (no
    hardening) gives r_max = 1 − exp(−1/(1 + μ/tan α)), from the ``die_half_angle`` α (degrees) and
    the ``friction_coefficient`` μ. A frictionless die gives the classic 1 − 1/e ≈ 0.63; friction
    lowers it. Bigger reductions are split across a train of dies — the reason wire is drawn in
    successive passes. Returns the maximum area reduction as a fraction (0 to 1).
    """
    if not 0.0 < die_half_angle < 90.0:
        raise ValueError("die_half_angle must be in (0, 90) degrees")
    if friction_coefficient < 0:
        raise ValueError("friction_coefficient must be non-negative")
    friction_factor = 1.0 + friction_coefficient / tan(radians(die_half_angle))
    return 1.0 - exp(-1.0 / friction_factor)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
