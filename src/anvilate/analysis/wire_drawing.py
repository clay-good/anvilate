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

Sources: Kalpakjian & Schmid, *Manufacturing Engineering and Technology* (rod and wire drawing)
— the ideal drawing stress with its friction and redundant-work terms, the force that stress
implies, and the maximum reduction per pass before the drawn wire yields.
"""

from __future__ import annotations

from math import exp, log, radians, tan

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_WIRE_DRAWING_GEOMETRY_SOURCE = (
    "the wire drawing plan or verified incoming and finished wire geometry"
)
_WIRE_DRAWING_MATERIAL_SOURCE = "the wire material certificate or qualified flow-stress test"
_WIRE_DRAWING_PROCESS_SOURCE = "the qualified die schedule and lubrication record"
_WIRE_DRAWING_CALCULATION_SOURCE = (
    "the verified drawing-stress calculation or qualified process trial"
)


class _WireDrawingInputError(RefusalError, ValueError):
    """A wire-drawing input that cannot be used without correction."""


def _wire_drawing_refusal(message: str, *, subject: str, source: str) -> _WireDrawingInputError:
    return _WireDrawingInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _wire_drawing_input_source(name: str) -> str:
    if name == "flow_stress":
        return _WIRE_DRAWING_MATERIAL_SOURCE
    if name == "drawing_stress":
        return _WIRE_DRAWING_CALCULATION_SOURCE
    return _WIRE_DRAWING_GEOMETRY_SOURCE


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
    stress or the wire snaps — a pass past :func:`wire_drawing_max_reduction` is refused here
    rather than priced. Returns the stress in MPa.
    """
    require_finite(die_half_angle, name="die_half_angle")
    require_finite(friction_coefficient, name="friction_coefficient")
    _check(flow_stress, "[pressure]", "flow_stress")
    _check(initial_area, "[area]", "initial_area")
    _check(final_area, "[area]", "final_area")
    y = flow_stress.to("MPa").magnitude
    a0 = initial_area.to("mm**2").magnitude
    af = final_area.to("mm**2").magnitude
    if y <= 0:
        raise _wire_drawing_refusal(
            "flow_stress must be positive",
            subject="flow_stress",
            source=_WIRE_DRAWING_MATERIAL_SOURCE,
        )
    if a0 <= 0 or af <= 0:
        raise _wire_drawing_refusal(
            "initial_area and final_area must be positive",
            subject="initial_area and final_area",
            source=_WIRE_DRAWING_GEOMETRY_SOURCE,
        )
    if af >= a0:
        raise _wire_drawing_refusal(
            "final_area must be smaller than initial_area (drawing reduces area)",
            subject="initial_area and final_area",
            source=_WIRE_DRAWING_GEOMETRY_SOURCE,
        )
    if not 0.0 < die_half_angle < 90.0:
        raise _wire_drawing_refusal(
            "die_half_angle must be in (0, 90) degrees",
            subject="die_half_angle",
            source=_WIRE_DRAWING_PROCESS_SOURCE,
        )
    if friction_coefficient < 0:
        raise _wire_drawing_refusal(
            "friction_coefficient must be non-negative",
            subject="friction_coefficient",
            source=_WIRE_DRAWING_PROCESS_SOURCE,
        )
    friction_factor = 1.0 + friction_coefficient / tan(radians(die_half_angle))
    # The exit wire carries this stress, so a pass that drives it past the flow stress does
    # not draw -- the wire yields at the exit and snaps. That is r > r_max, and r_max is
    # this module's own `wire_drawing_max_reduction` from the same two die parameters. It
    # was never called from here, so an infeasible pass returned a confident draw stress
    # 2.4x the wire's own flow stress.
    reduction = 1.0 - af / a0
    max_reduction = 1.0 - exp(-1.0 / friction_factor)
    if reduction > max_reduction:
        raise _wire_drawing_refusal(
            f"the pass reduces area by {reduction:.3f}, past the r_max = {max_reduction:.3f} this "
            f"die can take (die_half_angle {die_half_angle:g}°, mu {friction_coefficient:g}). The "
            f"draw stress would exceed the wire's flow stress and the wire would yield at the exit "
            f"instead of drawing; split the reduction across a train of dies",
            subject="initial_area, final_area, die_half_angle, and friction_coefficient",
            source=_WIRE_DRAWING_PROCESS_SOURCE,
        )
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
        raise _wire_drawing_refusal(
            "drawing_stress must be positive",
            subject="drawing_stress",
            source=_WIRE_DRAWING_CALCULATION_SOURCE,
        )
    if af <= 0:
        raise _wire_drawing_refusal(
            "final_area must be positive",
            subject="final_area",
            source=_WIRE_DRAWING_GEOMETRY_SOURCE,
        )
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
    require_finite(die_half_angle, name="die_half_angle")
    require_finite(friction_coefficient, name="friction_coefficient")
    if not 0.0 < die_half_angle < 90.0:
        raise _wire_drawing_refusal(
            "die_half_angle must be in (0, 90) degrees",
            subject="die_half_angle",
            source=_WIRE_DRAWING_PROCESS_SOURCE,
        )
    if friction_coefficient < 0:
        raise _wire_drawing_refusal(
            "friction_coefficient must be non-negative",
            subject="friction_coefficient",
            source=_WIRE_DRAWING_PROCESS_SOURCE,
        )
    friction_factor = 1.0 + friction_coefficient / tan(radians(die_half_angle))
    return 1.0 - exp(-1.0 / friction_factor)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _wire_drawing_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_wire_drawing_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _wire_drawing_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_wire_drawing_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
