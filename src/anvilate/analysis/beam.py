"""T1 analytical beam checks (closed-form, no solver).

The T1 validation tier screens a design with handbook closed-form solutions before
any FEA. This module implements the classic Roark / Shigley cases — a cantilever with an
end load, and a simply-supported beam with a central load — reporting the maximum
bending stress and the maximum deflection. Every input and output is a
dimension-checked :class:`~anvilate.units.Quantity`, and the arithmetic runs
through Pint so the units carry through and validate themselves.

These are screening checks, not certified analysis — they assume a prismatic
linear-elastic beam, small deflections, and no stress concentration.
"""

from __future__ import annotations

from math import pi, sqrt

from pydantic import BaseModel, ConfigDict

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity

__all__ = [
    "BeamBendingResult",
    "cantilever_end_load",
    "cantilever_uniform_load",
    "cantilever_triangular_load",
    "simply_supported_center_load",
    "simply_supported_offset_load",
    "simply_supported_uniform_load",
    "simply_supported_triangular_load",
    "fixed_fixed_center_load",
    "fixed_fixed_uniform_load",
    "rectangular_second_moment",
    "circular_second_moment",
    "hollow_circular_second_moment",
    "max_transverse_shear_stress",
    "deflection_scorecard",
    "SHEAR_FORM_RECTANGULAR",
    "SHEAR_FORM_CIRCULAR",
]

# Peak-to-average transverse-shear form factors τ_max = k·V/A: 3/2 at the neutral
# axis of a rectangular section, 4/3 for a solid circular one.
SHEAR_FORM_RECTANGULAR = 1.5
SHEAR_FORM_CIRCULAR = 4.0 / 3.0


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _as_quantity(pint_value, unit: str) -> Quantity:
    """Wrap a computed Pint quantity as a :class:`Quantity` in ``unit``."""
    converted = pint_value.to(unit)
    return Quantity(magnitude=float(converted.magnitude), unit=unit)


def rectangular_second_moment(width: Quantity, height: Quantity) -> Quantity:
    """The area second moment I = b·h³/12 of a rectangular section about its
    neutral (bending) axis, ``height`` being the dimension in the load direction."""
    _require(width, "[length]", "width")
    _require(height, "[length]", "height")
    return _as_quantity(width.pint * height.pint**3 / 12, "mm**4")


def circular_second_moment(diameter: Quantity) -> Quantity:
    """The area second moment I = π·d⁴/64 of a solid circular section about a
    diameter — the bending stiffness of a round bar (half the polar J)."""
    _require(diameter, "[length]", "diameter")
    return _as_quantity(pi * diameter.pint**4 / 64, "mm**4")


def hollow_circular_second_moment(
    *, outer_diameter: Quantity, inner_diameter: Quantity
) -> Quantity:
    """The area second moment I = π·(D⁴−d⁴)/64 of a hollow circular (tube) section
    about a diameter. ``inner_diameter`` must be below ``outer_diameter``."""
    _require(outer_diameter, "[length]", "outer_diameter")
    _require(inner_diameter, "[length]", "inner_diameter")
    do = outer_diameter.to("mm").magnitude
    di = inner_diameter.to("mm").magnitude
    if not 0 <= di < do:
        raise ValueError(
            f"inner_diameter ({inner_diameter}) must be non-negative and below "
            f"outer_diameter ({outer_diameter})"
        )
    return _as_quantity(pi * (outer_diameter.pint**4 - inner_diameter.pint**4) / 64, "mm**4")


def max_transverse_shear_stress(
    *,
    shear_force: Quantity,
    area: Quantity,
    form_factor: float = SHEAR_FORM_RECTANGULAR,
) -> Quantity:
    """The peak transverse shear stress τ_max = k·V/A in a beam cross-section.

    The transverse shear peaks above the average V/A at the neutral axis; the
    ``form_factor`` k captures the section shape — :data:`SHEAR_FORM_RECTANGULAR`
    (1.5) or :data:`SHEAR_FORM_CIRCULAR` (4/3). Short, deep beams fail here rather
    than in bending. ``shear_force`` must be a force and ``area`` an area;
    ``form_factor`` must be positive. Returns the shear stress in MPa.
    """
    _require(shear_force, "[force]", "shear_force")
    _require(area, "[length]**2", "area")
    if form_factor <= 0:
        raise ValueError(f"form_factor must be positive; got {form_factor}")
    stress = form_factor * shear_force.pint / area.pint
    return _as_quantity(stress, "MPa")


def deflection_scorecard(
    name: str,
    *,
    deflection: Quantity,
    limit: Quantity | None,
) -> ScorecardEntry:
    """Screen a computed ``deflection`` against an acceptance ``limit``.

    Builds a :class:`~anvilate.scorecard.ScorecardEntry`: ``PASS`` when the
    deflection magnitude is within ``limit``, ``FAIL`` when it exceeds it. When
    ``limit`` is ``None`` — no displacement limit was set on the spec — the entry
    is ``NOT_EVALUATED`` rather than a silent pass, the stiffness-dimension
    counterpart of :func:`anvilate.analysis.strength_scorecard`. Both quantities
    must be lengths.
    """
    _require(deflection, "[length]", "deflection")
    if limit is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — deflection limit unavailable",
        )
    _require(limit, "[length]", "limit")
    measured = abs(deflection.to("mm").magnitude)
    allowed = limit.to("mm").magnitude
    status = CheckStatus.PASS if measured <= allowed else CheckStatus.FAIL
    return ScorecardEntry(
        name=name,
        status=status,
        detail=f"deflection {measured:.3f} mm vs limit {allowed:.3f} mm",
    )


class BeamBendingResult(BaseModel):
    """The result of a closed-form beam bending check.

    ``max_bending_stress`` is the peak bending stress; ``max_deflection`` is the
    peak deflection (at the free end for a cantilever, at mid-span for a
    simply-supported beam). Both are screening estimates for a prismatic
    linear-elastic beam under small deflections.
    """

    model_config = ConfigDict(frozen=True)

    max_bending_stress: Quantity
    max_deflection: Quantity

    def bending_safety_factor(self, yield_strength: Quantity) -> float:
        """The factor of safety against yielding: yield strength / peak stress.

        ``yield_strength`` must be a stress (pressure), else :class:`ValueError`.
        A value below 1 means the beam yields under this load.
        """
        _require(yield_strength, "[pressure]", "yield_strength")
        sy = yield_strength.to("MPa").magnitude
        sigma = self.max_bending_stress.to("MPa").magnitude
        return sy / sigma

    def __str__(self) -> str:
        return (
            f"beam: sigma_max {self.max_bending_stress.to('MPa')}, "
            f"delta_max {self.max_deflection.to('mm')}"
        )


def cantilever_end_load(
    *,
    force: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The Roark/Shigley cantilever-with-end-load check.

    A prismatic beam of length ``length`` and section second moment
    ``second_moment`` (about the bending axis), fixed at one end and carrying a
    transverse ``force`` at the free end. ``extreme_fibre`` is the distance from
    the neutral axis to the outermost fibre (c, e.g. half the height of a
    rectangular section); ``elastic_modulus`` is the material's Young's modulus.

    Returns the peak bending stress at the fixed end (σ = M·c/I with M = F·L) and
    the free-end deflection (δ = F·L³/(3·E·I)). Every argument is dimension-checked.
    For a rectangular section, :func:`rectangular_second_moment` gives I and c is
    half the height.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = f * length_p
    stress = moment * c / inertia
    deflection = f * length_p**3 / (3 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def cantilever_offset_load(
    *,
    force: Quantity,
    load_position: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The cantilever with a point load short of the tip (Roark/Shigley).

    A prismatic beam fixed at one end and free at the other, carrying a
    transverse ``force`` at ``load_position`` a, measured from the fixed end,
    with 0 < a ≤ length. Other arguments match :func:`cantilever_end_load`,
    which this generalizes: at the tip (a = L) the two agree exactly.

    Returns the peak bending stress at the fixed end (σ = M·c/I with M = F·a)
    and the free-tip deflection δ = F·a²·(3L − a)/(6·E·I) — the beam is straight
    but rotated beyond the load, so the maximum is always at the tip. Every
    argument is dimension-checked.
    """
    _require(force, "[force]", "force")
    _require(load_position, "[length]", "load_position")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    position = load_position.pint.to(length_p.units)
    if not 0 < position.magnitude <= length_p.magnitude:
        raise ValueError(
            f"load_position must lie on the beam (0, {length}], measured from the "
            f"fixed end; got {load_position}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = f * position
    stress = moment * c / inertia
    deflection = f * position**2 * (3 * length_p - position) / (6 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def cantilever_uniform_load(
    *,
    distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The cantilever under a uniformly distributed load (Roark/Shigley).

    A prismatic beam fixed at one end and free at the other, carrying a uniform
    ``distributed_load`` w (force per unit length — e.g. self-weight). Returns the
    peak bending stress at the fixed end (σ = M·c/I with M = w·L²/2) and the
    free-end deflection (δ = w·L⁴/(8·E·I)). Every argument is dimension-checked.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * length_p**2 / 2
    stress = moment * c / inertia
    deflection = w * length_p**4 / (8 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def cantilever_triangular_load(
    *,
    peak_distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The cantilever under a linearly varying (triangular) load (Roark).

    A prismatic beam fixed at one end and free at the other, carrying a load that
    peaks at ``peak_distributed_load`` w₀ (force per unit length) at the fixed end
    and falls linearly to zero at the tip — soil pressure on a retaining-wall
    stiffener, hydrostatic pressure on a cantilevered baffle. Returns the peak
    bending stress at the fixed end (σ = M·c/I with M = w₀·L²/6) and the free-end
    deflection (δ = w₀·L⁴/(30·E·I)). Every argument is dimension-checked.
    """
    _require(peak_distributed_load, "[force] / [length]", "peak_distributed_load")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w0 = peak_distributed_load.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w0 * length_p**2 / 6
    stress = moment * c / inertia
    deflection = w0 * length_p**4 / (30 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def simply_supported_center_load(
    *,
    force: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The Roark/Shigley simply-supported-beam, central-load check.

    A prismatic beam simply supported at both ends over a span ``length``, with a
    transverse ``force`` at mid-span. Arguments match :func:`cantilever_end_load`.

    Returns the peak bending stress at mid-span (σ = M·c/I with M = F·L/4) and the
    mid-span deflection (δ = F·L³/(48·E·I)). Every argument is dimension-checked.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = f * length_p / 4
    stress = moment * c / inertia
    deflection = f * length_p**3 / (48 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def simply_supported_offset_load(
    *,
    force: Quantity,
    load_position: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The simply-supported beam with a point load off mid-span (Roark/Shigley).

    A prismatic beam simply supported over a span ``length``, with a transverse
    ``force`` at ``load_position`` (measured from either support — the case is
    symmetric) strictly inside the span. Other arguments match
    :func:`simply_supported_center_load`, which this generalizes: at mid-span the
    two agree exactly.

    Returns the peak bending stress under the load (σ = M·c/I with M = F·a·b/L)
    and the true maximum deflection δ = F·b·(L² − b²)^{3/2}/(9·√3·L·E·I), where b
    is the load's distance to the nearer support — the maximum sits between the
    load and mid-span, not under the load. Every argument is dimension-checked.
    """
    _require(force, "[force]", "force")
    _require(load_position, "[length]", "load_position")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    position = load_position.pint.to(length_p.units)
    if not 0 < position.magnitude < length_p.magnitude:
        raise ValueError(
            f"load_position must lie strictly inside the span (0, {length}); got {load_position}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    far = max(position, length_p - position)
    near = length_p - far  # distance from the load to the nearer support
    moment = f * far * near / length_p
    stress = moment * c / inertia
    deflection = f * near * (length_p**2 - near**2) ** 1.5 / (9 * 3**0.5 * length_p * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def simply_supported_uniform_load(
    *,
    distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The simply-supported beam under a uniformly distributed load (Roark/Shigley).

    A prismatic beam simply supported over a span ``length`` carrying a uniform
    ``distributed_load`` w (force per unit length — self-weight, pressure on a
    span). Returns the peak bending stress at mid-span (σ = M·c/I with the maximum
    moment M = w·L²/8) and the mid-span deflection (δ = 5·w·L⁴/(384·E·I)). Every
    argument is dimension-checked.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * length_p**2 / 8
    stress = moment * c / inertia
    deflection = 5 * w * length_p**4 / (384 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def simply_supported_triangular_load(
    *,
    peak_distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The simply-supported beam under a linearly varying (triangular) load (Roark).

    A prismatic beam simply supported over a span ``length`` carrying a load that
    rises linearly from zero at one support to ``peak_distributed_load`` w₀ (force
    per unit length) at the other — hydrostatic pressure on a gate stiffener, a
    bin wall's stored-solids push. The maximum moment w₀·L²/(9·√3) occurs at
    L/√3 ≈ 0.577·L from the zero end, and the maximum deflection (≈0.00652·w₀·L⁴/(E·I),
    evaluated exactly from the elastic curve) at ≈0.519·L — neither at mid-span.
    Every argument is dimension-checked.
    """
    _require(peak_distributed_load, "[force] / [length]", "peak_distributed_load")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w0 = peak_distributed_load.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w0 * length_p**2 / (9 * sqrt(3))
    stress = moment * c / inertia
    # Elastic curve v(x) = w0·x·(7L⁴ − 10L²x² + 3x⁴)/(360·L·E·I) measured from the
    # zero-intensity end; v′ = 0 at x² = L²·(30 − √480)/30.
    x = length_p * sqrt((30 - sqrt(480)) / 30)
    deflection = (
        w0
        * x
        * (7 * length_p**4 - 10 * length_p**2 * x**2 + 3 * x**4)
        / (360 * length_p * e * inertia)
    )
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_pinned_center_load(
    *,
    force: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The propped cantilever (fixed-pinned) beam with a central point load.

    A prismatic beam clamped at one end and simply supported (propped) at the
    other over a span ``length``, with a transverse ``force`` at mid-span (AISC
    Table 3-23 case 13). Arguments match :func:`fixed_fixed_center_load`.

    Returns the peak bending stress at the fixed end (σ = M·c/I with the maximum
    moment M = 3·F·L/16) and the true maximum deflection δ = F·L³/(48·√5·E·I),
    which sits 0.447·L from the propped end — between the simply-supported and
    fixed-fixed cases on both counts. Every argument is dimension-checked.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = 3 * f * length_p / 16
    stress = moment * c / inertia
    deflection = f * length_p**3 / (48 * 5**0.5 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_pinned_offset_load(
    *,
    force: Quantity,
    load_position: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The propped cantilever with a point load anywhere on the span.

    A prismatic beam clamped at one end and simply supported (propped) at the
    other, with a transverse ``force`` at ``load_position`` a — measured from the
    **propped** end (the case is not symmetric) — strictly inside the span (AISC
    Table 3-23 case 26). Other arguments match :func:`fixed_pinned_center_load`,
    which this generalizes: at mid-span the two agree exactly.

    Returns the peak bending stress from whichever moment governs — under the
    load (M = F·a·b²·(a+2L)/(2L³), governs near the prop) or hogging at the wall
    (M = F·a·b·(a+L)/(2L²), governs elsewhere, peaking at a = L/√3) — and the
    true maximum deflection, whose closed form is piecewise about a = 0.414·L.
    Every argument is dimension-checked.
    """
    _require(force, "[force]", "force")
    _require(load_position, "[length]", "load_position")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    position = load_position.pint.to(length_p.units)
    if not 0 < position.magnitude < length_p.magnitude:
        raise ValueError(
            f"load_position must lie strictly inside the span (0, {length}), measured "
            f"from the propped end; got {load_position}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    a = position
    b = length_p - a  # distance from the load to the wall
    under_load = f * a * b**2 * (a + 2 * length_p) / (2 * length_p**3)
    at_wall = f * a * b * (a + length_p) / (2 * length_p**2)
    moment = max(under_load, at_wall)
    stress = moment * c / inertia
    if a.magnitude < (2**0.5 - 1) * length_p.magnitude:
        deflection = (
            f * a * (length_p**2 - a**2) ** 3 / (3 * e * inertia * (3 * length_p**2 - a**2) ** 2)
        )
    else:
        deflection = f * a * b**2 / (6 * e * inertia) * (a / (2 * length_p + a)) ** 0.5
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_pinned_uniform_load(
    *,
    distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The propped cantilever (fixed-pinned) beam under a uniform load.

    A prismatic beam clamped at one end and simply supported (propped) at the
    other, carrying a uniform ``distributed_load`` w (AISC Table 3-23 case 12).
    Returns the peak bending stress at the fixed end (σ = M·c/I with the maximum
    moment M = w·L²/8 — the same governing moment as the simply-supported case,
    but hogging at the wall) and the maximum deflection δ = w·L⁴/(185·E·I),
    which sits 0.422·L from the propped end. Every argument is dimension-checked.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * length_p**2 / 8
    stress = moment * c / inertia
    deflection = w * length_p**4 / (185 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_fixed_center_load(
    *,
    force: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The fixed-fixed (both ends built-in) beam with a central point load.

    A prismatic beam clamped at both ends over a span ``length`` with a transverse
    ``force`` at mid-span. Returns the peak bending stress (σ = M·c/I with the
    maximum moment M = F·L/8, at the ends and mid-span) and the mid-span deflection
    (δ = F·L³/(192·E·I)) — far stiffer than the simply-supported case. Every
    argument is dimension-checked.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = f * length_p / 8
    stress = moment * c / inertia
    deflection = f * length_p**3 / (192 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_fixed_offset_load(
    *,
    force: Quantity,
    load_position: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The fixed-fixed beam with a point load off mid-span (Roark; AISC Table 3-23).

    A prismatic beam clamped at both ends over a span ``length``, with a transverse
    ``force`` at ``load_position`` (measured from either wall — the case is
    symmetric) strictly inside the span. Other arguments match
    :func:`fixed_fixed_center_load`, which this generalizes: at mid-span the two
    agree exactly.

    Returns the peak bending stress at the wall nearer the load (σ = M·c/I with
    the hogging moment M = F·a·b²/L², a the near distance) and the true maximum
    deflection δ = 2·F·b³·a²/(3·E·I·(3b + a)²), b the far distance. Unlike the
    simply-supported case, mid-span is *not* the worst position: the wall moment
    peaks at a = L/3 (M = 4·F·L/27, 18.5% above the mid-span F·L/8). Every
    argument is dimension-checked.
    """
    _require(force, "[force]", "force")
    _require(load_position, "[length]", "load_position")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    position = load_position.pint.to(length_p.units)
    if not 0 < position.magnitude < length_p.magnitude:
        raise ValueError(
            f"load_position must lie strictly inside the span (0, {length}); got {load_position}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    far = max(position, length_p - position)
    near = length_p - far  # distance from the load to the nearer wall
    moment = f * near * far**2 / length_p**2
    stress = moment * c / inertia
    deflection = 2 * f * far**3 * near**2 / (3 * e * inertia * (3 * far + near) ** 2)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_fixed_uniform_load(
    *,
    distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The fixed-fixed beam under a uniformly distributed load.

    A prismatic beam clamped at both ends carrying a uniform ``distributed_load``
    w (force per unit length). Returns the peak bending stress (σ = M·c/I with the
    maximum moment M = w·L²/12, at the ends) and the mid-span deflection
    (δ = w·L⁴/(384·E·I)). Every argument is dimension-checked.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * length_p**2 / 12
    stress = moment * c / inertia
    deflection = w * length_p**4 / (384 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )
