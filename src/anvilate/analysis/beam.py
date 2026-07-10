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
    "cantilever_offset_load",
    "cantilever_uniform_load",
    "cantilever_partial_uniform_load",
    "cantilever_center_patch_load",
    "cantilever_triangular_load",
    "cantilever_triangular_load_peak_at_tip",
    "cantilever_end_moment",
    "simply_supported_center_load",
    "simply_supported_offset_load",
    "simply_supported_symmetric_point_loads",
    "simply_supported_uniform_load",
    "simply_supported_partial_uniform_load",
    "simply_supported_center_patch_load",
    "simply_supported_triangular_load",
    "simply_supported_end_moment",
    "fixed_fixed_center_load",
    "fixed_fixed_offset_load",
    "fixed_fixed_uniform_load",
    "fixed_fixed_partial_uniform_load",
    "fixed_fixed_center_patch_load",
    "fixed_fixed_triangular_load",
    "fixed_pinned_center_load",
    "fixed_pinned_offset_load",
    "fixed_pinned_uniform_load",
    "fixed_pinned_partial_uniform_load",
    "fixed_pinned_center_patch_load",
    "fixed_pinned_triangular_load",
    "fixed_pinned_triangular_load_peak_at_prop",
    "fixed_pinned_end_moment",
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


def cantilever_partial_uniform_load(
    *,
    distributed_load: Quantity,
    loaded_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The cantilever uniformly loaded over part of its length (Roark).

    A prismatic beam fixed at one end and free at the other, carrying a uniform
    ``distributed_load`` w (force per unit length) over ``loaded_length`` a
    measured from the fixed end, unloaded beyond — an equipment skid parked
    against the wall end of a cantilevered platform. Degenerates exactly to
    :func:`cantilever_uniform_load` at a = L.

    Returns the peak bending stress at the fixed end (σ = M·c/I with M = w·a²/2)
    and the free-end deflection δ = w·a³·(4L−a)/(24·E·I) — the loaded segment's
    own deflection plus the rigid rotation it hands the unloaded overhang. Every
    argument is dimension-checked.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(loaded_length, "[length]", "loaded_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    loaded = loaded_length.pint.to(length_p.units)
    if not 0 < loaded.magnitude <= length_p.magnitude:
        raise ValueError(
            f"loaded_length must lie within the span (0, {length}]; got {loaded_length}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * loaded**2 / 2
    stress = moment * c / inertia
    deflection = w * loaded**3 * (4 * length_p - loaded) / (24 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def cantilever_center_patch_load(
    *,
    distributed_load: Quantity,
    loaded_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The cantilever uniformly loaded over a centered patch (Roark).

    A prismatic beam fixed at one end and free at the other, carrying a uniform
    ``distributed_load`` w (force per unit length) over ``loaded_length`` a
    centered on mid-span, unloaded toward both the wall and the tip — a machine
    footprint in the middle of a cantilevered platform. Degenerates exactly to
    :func:`cantilever_uniform_load` at a = L and to :func:`cantilever_offset_load`
    at mid-span as a → 0 at fixed total w·a; the wall-adjacent counterpart is
    :func:`cantilever_partial_uniform_load`.

    Returns the peak bending stress at the fixed end (σ = M·c/I with
    M = w·a·L/2, the patch total acting at its mid-span centroid) and the tip
    deflection δ = w·L·a·(5L² + a²)/(48·E·I). Every argument is
    dimension-checked; verified against an independent numeric integration of
    the beam ODE.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(loaded_length, "[length]", "loaded_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    loaded = loaded_length.pint.to(length_p.units)
    if not 0 < loaded.magnitude <= length_p.magnitude:
        raise ValueError(
            f"loaded_length must lie within the span (0, {length}]; got {loaded_length}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * loaded * length_p / 2
    stress = moment * c / inertia
    deflection = w * length_p * loaded * (5 * length_p**2 + loaded**2) / (48 * e * inertia)
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


def cantilever_triangular_load_peak_at_tip(
    *,
    peak_distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The cantilever under a triangular load peaking at the free end (Roark).

    The mirror orientation of :func:`cantilever_triangular_load`: the load
    rises linearly from zero at the wall to ``peak_distributed_load`` w₀
    (force per unit length) at the tip — drifted snow piled against the edge
    parapet of a cantilevered canopy. The resultant w₀·L/2 acts at 2·L/3 from
    the wall, so the wall moment w₀·L²/3 is TWICE the peak-at-wall
    orientation's w₀·L²/6 — assuming the milder orientation is unconservative
    by a factor of two. Returns the peak bending stress at the fixed end
    (σ = M·c/I with M = w₀·L²/3) and the free-end deflection
    (δ = 11·w₀·L⁴/(120·E·I)). Both maxima sit where the mirror's do, so the
    two orientations superpose exactly to the full-UDL cantilever in stress
    AND deflection (1/6 + 1/3 = 1/2; 1/30 + 11/120 = 1/8). Every argument is
    dimension-checked; verified against an independent numeric integration of
    the beam ODE.
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

    moment = w0 * length_p**2 / 3
    stress = moment * c / inertia
    deflection = 11 * w0 * length_p**4 / (120 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def cantilever_end_moment(
    *,
    moment: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The cantilever with a couple applied at the free end (Roark).

    A prismatic beam fixed at one end and free at the other, carrying an
    applied ``moment`` M₀ (a couple in the bending plane) at the tip — the
    reaction a bracket, crank socket, or eccentric fitting hands the beam.
    The bending moment is CONSTANT at M₀ over the whole span (pure bending):
    unlike a tip force, whose moment falls linearly to zero at the tip, every
    section is equally stressed — there is no lightly-loaded region to drill
    or notch. For the same wall moment (M₀ = F·L) the couple also deflects
    the tip 1.5× as far as the force (L²/2 vs L³/3 per unit wall moment).

    Returns the peak bending stress (σ = M₀·c/I, everywhere) and the tip
    deflection δ = M₀·L²/(2·E·I). Every argument is dimension-checked;
    verified against an independent numeric integration of the beam ODE.
    """
    _require(moment, "[force] * [length]", "moment")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    m0 = moment.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    stress = m0 * c / inertia
    deflection = m0 * length_p**2 / (2 * e * inertia)
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


def simply_supported_symmetric_point_loads(
    *,
    force: Quantity,
    load_offset: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The simply-supported beam with two equal symmetric point loads (Roark).

    Four-point bending: a prismatic beam simply supported over a span
    ``length`` carrying ``force`` F at ``load_offset`` a from EACH support —
    a machine on two rails, a spreader-beam lift, a flexure-test rig. Each
    support reacts F, so the moment is constant at M = F·a everywhere between
    the loads (pure bending) — modeling the pair as its 2·F resultant at
    mid-span overstates the moment by L/(2·a), 1.5x for third-point rails.

    Returns the peak bending stress (σ = M·c/I with M = F·a) and the mid-span
    deflection δ = F·a·(3·L² − 4·a²)/(24·E·I), the maximum by symmetry. At
    a = L/2 both loads coincide at mid-span and the result degenerates exactly
    to :func:`simply_supported_center_load` with 2·F. Every argument is
    dimension-checked; verified against an independent numeric integration of
    the beam ODE.
    """
    _require(force, "[force]", "force")
    _require(load_offset, "[length]", "load_offset")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    offset = load_offset.pint.to(length_p.units)
    if not 0 < offset.magnitude <= length_p.magnitude / 2:
        raise ValueError(
            f"load_offset must lie within the half-span (0, {length} / 2]; got {load_offset}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = f * offset
    stress = moment * c / inertia
    deflection = f * offset * (3 * length_p**2 - 4 * offset**2) / (24 * e * inertia)
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


def simply_supported_partial_uniform_load(
    *,
    distributed_load: Quantity,
    loaded_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The simply-supported beam uniformly loaded over part of its span (AISC).

    A prismatic beam simply supported over a span ``length``, carrying a uniform
    ``distributed_load`` w (force per unit length) over ``loaded_length`` a
    measured from one support, unloaded beyond — a pallet stack parked at one end
    of a floor beam, drifted snow against a parapet (AISC Table 3-23 case 24).
    Degenerates exactly to :func:`simply_supported_uniform_load` at a = L.

    Returns the peak bending stress where the shear crosses zero inside the
    loaded region (σ = M·c/I with M = R₁²/(2·w), R₁ = w·a·(2L−a)/(2L)) and the
    true maximum deflection from the piecewise elastic curve — its stationary
    point is closed-form in the unloaded region and bisected to machine
    precision from the analytic slope polynomial in the loaded one (no FEA).
    Every argument is dimension-checked.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(loaded_length, "[length]", "loaded_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    loaded = loaded_length.pint.to(length_p.units)
    alpha = loaded.magnitude / length_p.magnitude  # a/L
    if not 0 < alpha <= 1:
        raise ValueError(
            f"loaded_length must lie within the span (0, {length}]; got {loaded_length}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    reaction = w * loaded * (2 * length_p - loaded) / (2 * length_p)
    moment = reaction**2 / (2 * w)
    stress = moment * c / inertia

    # Dimensionless elastic curve (ξ = x/L from the loaded-end support, deflection
    # in units of w·L⁴/(24·E·I)):
    #   loaded (ξ < α):   δ = ξ·(α²(2−α)² − 2α(2−α)ξ² + ξ³)
    #   unloaded (ξ ≥ α): δ = α²(1−ξ)(4ξ − 2ξ² − α²)
    # The unloaded-region slope 6ξ² − 12ξ + 4 + α² vanishes at
    # ξ* = 1 − √((2 − α²)/6); when the slope is already negative at ξ = α
    # (7α² − 12α + 4 < 0), the maximum sits in the loaded region instead, where
    # the slope polynomial 4ξ³ − 6α(2−α)ξ² + α²(2−α)² is bisected on (0, α).
    if 7 * alpha**2 - 12 * alpha + 4 > 0:
        xi = 1 - sqrt((2 - alpha**2) / 6)
        deflection_norm = alpha**2 * (1 - xi) * (4 * xi - 2 * xi**2 - alpha**2)
    else:
        lo, hi = 0.0, alpha
        for _ in range(100):
            mid = (lo + hi) / 2
            slope = 4 * mid**3 - 6 * alpha * (2 - alpha) * mid**2 + alpha**2 * (2 - alpha) ** 2
            if slope > 0:
                lo = mid
            else:
                hi = mid
        xi = (lo + hi) / 2
        deflection_norm = xi * (
            alpha**2 * (2 - alpha) ** 2 - 2 * alpha * (2 - alpha) * xi**2 + xi**3
        )
    deflection = deflection_norm * w * length_p**4 / (24 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def simply_supported_center_patch_load(
    *,
    distributed_load: Quantity,
    loaded_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The simply-supported beam uniformly loaded over a centered patch (AISC).

    A prismatic beam simply supported over a span ``length``, carrying a uniform
    ``distributed_load`` w (force per unit length) over ``loaded_length`` a
    centered on mid-span, unloaded toward both supports — a machine footprint in
    the middle of a floor beam (AISC Table 3-23 case 25 with equal end
    segments). Degenerates exactly to :func:`simply_supported_uniform_load` at
    a = L; the one-sided counterpart is
    :func:`simply_supported_partial_uniform_load`.

    Returns the peak bending stress at mid-span (σ = M·c/I with
    M = w·a·(2L−a)/8) and the mid-span maximum deflection
    δ = w·a·(8L³ − 4a²·L + a³)/(384·E·I). Every argument is dimension-checked.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(loaded_length, "[length]", "loaded_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    loaded = loaded_length.pint.to(length_p.units)
    if not 0 < loaded.magnitude <= length_p.magnitude:
        raise ValueError(
            f"loaded_length must lie within the span (0, {length}]; got {loaded_length}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * loaded * (2 * length_p - loaded) / 8
    stress = moment * c / inertia
    deflection = (
        w * loaded * (8 * length_p**3 - 4 * loaded**2 * length_p + loaded**3) / (384 * e * inertia)
    )
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


def simply_supported_end_moment(
    *,
    moment: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The simply-supported beam with a couple applied at one end (Roark).

    A prismatic beam simply supported over a span ``length``, carrying an
    applied ``moment`` M₀ (a couple in the bending plane) at one support — a
    semi-rigid end connection's transferred moment, a brake or lever hub
    clamped at the end of a shaft span. The reactions form the countering
    couple M₀/L, so the bending moment falls linearly from M₀ at the loaded
    end to zero at the far one.

    Returns the peak bending stress at the loaded end (σ = M₀·c/I) and the
    true maximum deflection from the elastic curve
    EI·v = −M₀·(2ξ − 3ξ² + ξ³)·L²/6, ξ measured from the loaded end — its
    slope vanishes inside the span exactly at ξ = 1 − 1/√3 ≈ 0.423, giving
    δ_max = M₀·L²/(9·√3·E·I). Every argument is dimension-checked; verified
    against an independent numeric integration of the beam ODE.
    """
    _require(moment, "[force] * [length]", "moment")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    m0 = moment.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    stress = m0 * c / inertia
    deflection = m0 * length_p**2 / (9 * sqrt(3) * e * inertia)
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


def fixed_pinned_partial_uniform_load(
    *,
    distributed_load: Quantity,
    loaded_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The propped cantilever uniformly loaded over a wall-adjacent patch (Roark).

    A prismatic beam clamped at one end and simply supported (propped) at the
    other over a span ``length``, carrying a uniform ``distributed_load`` w
    (force per unit length) over ``loaded_length`` a measured from the **fixed**
    end, unloaded toward the prop — equipment parked against the wall end of a
    propped platform. Degenerates to :func:`fixed_pinned_uniform_load` at a = L
    (the moment exactly; the deflection to the 0.2% rounding of that function's
    handbook constant 185).

    The hogging moment at the wall governs everywhere (σ = M·c/I with
    M = w·a²·(2L − a)²/(8L²); the interior sagging peak R₁²/(2w) − M is always
    smaller, R₁ = w·a − w·a³·(4L − a)/(8L³) the wall reaction). The true maximum
    deflection comes from the piecewise elastic curve
    EI·v = −M·x²/2 + R₁·x³/6 − w·x⁴/24 + w·⟨x−a⟩⁴/24, x from the wall — its
    stationary point is closed-form in both regions: for long patches the
    smaller root of x² − (3R₁/w)·x + 6M/w = 0 lands inside the loaded region;
    for shorter ones that root turns complex or overshoots the patch and the
    maximum sits at the rising root of the unloaded region's quadratic slope
    (R₁ − w·a)·x²/2 + (w·a²/2 − M)·x − w·a³/6. Every argument is
    dimension-checked; verified against an independent numeric integration of
    the beam ODE.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(loaded_length, "[length]", "loaded_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    loaded = loaded_length.pint.to(length_p.units)
    if not 0 < loaded.magnitude <= length_p.magnitude:
        raise ValueError(
            f"loaded_length must lie within the span (0, {length}]; got {loaded_length}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * loaded**2 * (2 * length_p - loaded) ** 2 / (8 * length_p**2)
    stress = moment * c / inertia

    reaction = w * loaded - w * loaded**3 * (4 * length_p - loaded) / (8 * length_p**3)
    half_sum = 3 * reaction / (2 * w)  # half the root sum of the loaded-region slope
    disc = half_sum**2 - 6 * moment / w
    if disc.magnitude >= 0 and (x := half_sum - disc**0.5) <= loaded:
        deflection = (moment * x**2 / 2 - reaction * x**3 / 6 + w * x**4 / 24) / (e * inertia)
    else:
        quad = (reaction - w * loaded) / 2
        lin = w * loaded**2 / 2 - moment
        const = -w * loaded**3 / 6
        x = (-lin + (lin**2 - 4 * quad * const) ** 0.5) / (2 * quad)
        deflection = (
            moment * x**2 / 2 - reaction * x**3 / 6 + w * x**4 / 24 - w * (x - loaded) ** 4 / 24
        ) / (e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_pinned_center_patch_load(
    *,
    distributed_load: Quantity,
    loaded_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The propped cantilever uniformly loaded over a centered patch (Roark).

    A prismatic beam clamped at one end and simply supported (propped) at the
    other over a span ``length``, carrying a uniform ``distributed_load`` w
    (force per unit length) over ``loaded_length`` a centered on mid-span,
    unloaded toward both supports — a machine footprint in the middle of a
    propped floor beam. Degenerates to :func:`fixed_pinned_uniform_load` at
    a = L (the moment exactly; the deflection to the 0.2% rounding of that
    function's handbook constant 185) and to :func:`fixed_pinned_center_load`
    exactly as a → 0 at fixed total w·a.

    The hogging moment at the wall governs everywhere (σ = M·c/I with
    M = w·a·(3L² − a²)/(16L), from integrating the point-load wall-moment
    influence over the patch; the interior sagging peak stays below it). The
    maximum deflection comes from the piecewise elastic curve, x from the wall
    with patch edges c₁,₂ = (L ∓ a)/2:
    EI·δ = M·x²/2 − R₁·x³/6 + w·⟨x−c₁⟩⁴/24 − w·⟨x−c₂⟩⁴/24, R₁ the wall
    reaction w·a·(11L² − a²)/(16L²) — for very short patches its stationary
    point sits beyond the patch at the smaller root of the prop-side quadratic
    slope; otherwise it is bisected to machine precision from the analytic
    slope cubic inside the patch. Every argument is dimension-checked; verified
    against an independent numeric integration of the beam ODE.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(loaded_length, "[length]", "loaded_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    loaded = loaded_length.pint.to(length_p.units)
    if not 0 < loaded.magnitude <= length_p.magnitude:
        raise ValueError(
            f"loaded_length must lie within the span (0, {length}]; got {loaded_length}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * loaded * (3 * length_p**2 - loaded**2) / (16 * length_p)
    stress = moment * c / inertia

    reaction = w * loaded * (11 * length_p**2 - loaded**2) / (16 * length_p**2)
    near_edge = (length_p - loaded) / 2
    far_edge = (length_p + loaded) / 2

    def _slope(x):
        return moment * x - reaction * x**2 / 2 + w * (x - near_edge) ** 3 / 6

    if _slope(far_edge).magnitude <= 0:
        lo, hi = near_edge, far_edge
        for _ in range(100):
            mid = (lo + hi) / 2
            if _slope(mid).magnitude > 0:
                lo = mid
            else:
                hi = mid
        x = (lo + hi) / 2
        deflection = (moment * x**2 / 2 - reaction * x**3 / 6 + w * (x - near_edge) ** 4 / 24) / (
            e * inertia
        )
    else:
        quad = (w * loaded - reaction) / 2
        lin = moment - w * loaded * length_p / 2
        const = w * loaded * (3 * length_p**2 + loaded**2) / 24
        x = (-lin - (lin**2 - 4 * quad * const) ** 0.5) / (2 * quad)
        deflection = (
            moment * x**2 / 2
            - reaction * x**3 / 6
            + w * (x - near_edge) ** 4 / 24
            - w * (x - far_edge) ** 4 / 24
        ) / (e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_pinned_triangular_load(
    *,
    peak_distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The propped cantilever under a triangular load peaking at the fixed end.

    A prismatic beam clamped at one end and simply supported (propped) at the
    other over a span ``length``, carrying a load that rises linearly from zero
    at the prop to ``peak_distributed_load`` w₀ (force per unit length) at the
    wall — a barrier stiffener welded at the sill where the pressure peaks and
    pinned at the top waler (Roark; prop reaction w₀·L/10). The wall moment
    w₀·L²/15 governs (the interior sagging peak is only w₀·L²/(15·√5)).

    Returns the peak bending stress at the fixed end (σ = M·c/I with
    M = w₀·L²/15) and the true maximum deflection from the elastic curve
    v(ξ) = (ξ − 2ξ³ + ξ⁵)·w₀·L⁴/(120·E·I), ξ measured from the prop — its slope
    5ξ⁴ − 6ξ² + 1 vanishes inside the span exactly at ξ = 1/√5 ≈ 0.447, giving
    δ_max = 16·w₀·L⁴/(3000·√5·E·I) ≈ w₀·L⁴/(419·E·I). Every argument is
    dimension-checked.
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

    moment = w0 * length_p**2 / 15
    stress = moment * c / inertia
    xi = 1 / sqrt(5)
    deflection = (xi - 2 * xi**3 + xi**5) * w0 * length_p**4 / (120 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_pinned_triangular_load_peak_at_prop(
    *,
    peak_distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The propped cantilever under a triangular load peaking at the prop.

    The mirror orientation of :func:`fixed_pinned_triangular_load`: the load
    rises linearly from zero at the wall to ``peak_distributed_load`` w₀
    (force per unit length) at the prop — a barrier stiffener welded at the
    top and propped at the sill where the pressure peaks. The prop carries
    11·w₀·L/40 and the wall moment 7·w₀·L²/120 still governs (the interior
    sagging peak, (9·√5/200 − 7/120)·w₀·L² ≈ 0.0423·w₀·L² at
    L·(1 − 3/(2·√5)) from the prop, is smaller) — though it is milder than
    the peak-at-wall wall moment
    w₀·L²/15; the two orientations superpose exactly to the full-UDL wall
    moment w₀·L²/8.

    Returns the peak bending stress at the fixed end (σ = M·c/I with
    M = 7·w₀·L²/120) and the true maximum deflection from the elastic curve
    v(ξ) = (7ξ² − 9ξ³ + 2ξ⁵)·w₀·L⁴/(240·E·I), ξ measured from the wall — its
    slope vanishes inside the span at the root of 10ξ³ − 27ξ + 14 (bisected to
    machine precision, ξ ≈ 0.5975), giving δ_max ≈ w₀·L⁴/(328·E·I). Every
    argument is dimension-checked; verified against an independent numeric
    integration of the beam ODE.
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

    moment = 7 * w0 * length_p**2 / 120
    stress = moment * c / inertia

    # v'(ξ) ∝ −14ξ + 27ξ² − 10ξ⁴, whose interior zero is the single (0, 1)
    # root of 10ξ³ − 27ξ + 14 (positive at 0, negative at 1).
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if 10 * mid**3 - 27 * mid + 14 > 0:
            lo = mid
        else:
            hi = mid
    xi = (lo + hi) / 2
    deflection = (7 * xi**2 - 9 * xi**3 + 2 * xi**5) * w0 * length_p**4 / (240 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_pinned_end_moment(
    *,
    moment: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The propped cantilever with a couple applied at the prop (Roark).

    A prismatic beam clamped at one end and simply supported (propped) at the
    other over a span ``length``, carrying an applied ``moment`` M₀ (a couple
    in the bending plane) at the propped end — a semi-rigid connection or hub
    at the pinned end of a member whose far end is built in. The wall carries
    over exactly half the applied couple with opposite sign (the classic
    moment-distribution carry-over factor), so the moment falls linearly from
    M₀ at the prop through zero at 2L/3 to −M₀/2 at the wall, and the applied
    couple still governs. Compared with the same couple on a simply-supported
    span, building in the far end leaves the peak stress unchanged but cuts
    the maximum deflection to exactly 1/√3 of it.

    Returns the peak bending stress at the propped end (σ = M₀·c/I) and the
    true maximum deflection from the elastic curve
    EI·v = M₀·(x²/2 − x³/(4L) − L·x/4), x measured from the prop — its slope
    vanishes inside the span exactly at x = L/3, giving δ_max = M₀·L²/(27·E·I).
    Every argument is dimension-checked; verified against an independent
    numeric integration of the beam ODE.
    """
    _require(moment, "[force] * [length]", "moment")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    m0 = moment.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    stress = m0 * c / inertia
    deflection = m0 * length_p**2 / (27 * e * inertia)
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


def fixed_fixed_partial_uniform_load(
    *,
    distributed_load: Quantity,
    loaded_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The fixed-fixed beam uniformly loaded over part of its span (Roark).

    A prismatic beam clamped at both ends over a span ``length``, carrying a
    uniform ``distributed_load`` w (force per unit length) over ``loaded_length``
    a measured from one wall, unloaded beyond — equipment parked at one end of a
    built-in floor beam. Degenerates exactly to :func:`fixed_fixed_uniform_load`
    at a = L; the simply-supported counterpart is
    :func:`simply_supported_partial_uniform_load`.

    The hogging moment at the loaded-end wall governs everywhere (σ = M·c/I with
    M = w·a²·(6L² − 8aL + 3a²)/(12L²); the far wall carries only
    w·a³·(4L − 3a)/(12L²) and the interior sagging peak R₁²/(2w) − M is smaller
    still, R₁ = w·a·(2L³ − 2La² + a³)/(2L³) the loaded-end reaction). The true
    maximum deflection comes from the piecewise elastic curve
    EI·v = −M·x²/2 + R₁·x³/6 − w·x⁴/24 + w·⟨x−a⟩⁴/24 — its stationary point is
    closed-form in both regions: the unloaded slope is quadratic with the fixed
    end x = L as one root, putting the other at x* = 2L²/(3·(2L−a)) (valid while
    3α² − 6α + 2 > 0, α = a/L); past that patch ratio the maximum moves into the
    loaded region, to the smaller root of x² − (3R₁/w)·x + 6M/w = 0. Every
    argument is dimension-checked; verified against an independent numeric
    integration of the beam ODE.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(loaded_length, "[length]", "loaded_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    loaded = loaded_length.pint.to(length_p.units)
    alpha = loaded.magnitude / length_p.magnitude  # a/L
    if not 0 < alpha <= 1:
        raise ValueError(
            f"loaded_length must lie within the span (0, {length}]; got {loaded_length}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = (
        w
        * loaded**2
        * (6 * length_p**2 - 8 * loaded * length_p + 3 * loaded**2)
        / (12 * length_p**2)
    )
    stress = moment * c / inertia

    reaction = (
        w * loaded * (2 * length_p**3 - 2 * length_p * loaded**2 + loaded**3) / (2 * length_p**3)
    )
    if 3 * alpha**2 - 6 * alpha + 2 > 0:
        x = 2 * length_p**2 / (3 * (2 * length_p - loaded))
        deflection = (
            moment * x**2 / 2 - reaction * x**3 / 6 + w * x**4 / 24 - w * (x - loaded) ** 4 / 24
        ) / (e * inertia)
    else:
        half_sum = 3 * reaction / (2 * w)  # half the root sum of the loaded-region slope
        x = half_sum - (half_sum**2 - 6 * moment / w) ** 0.5
        deflection = (moment * x**2 / 2 - reaction * x**3 / 6 + w * x**4 / 24) / (e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_fixed_center_patch_load(
    *,
    distributed_load: Quantity,
    loaded_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The fixed-fixed beam uniformly loaded over a centered patch (Roark).

    A prismatic beam clamped at both ends over a span ``length``, carrying a
    uniform ``distributed_load`` w (force per unit length) over ``loaded_length``
    a centered on mid-span, unloaded toward both walls — a machine footprint in
    the middle of a built-in floor beam. Degenerates exactly to
    :func:`fixed_fixed_uniform_load` at a = L and to
    :func:`fixed_fixed_center_load` as a → 0 at fixed total w·a; the
    simply-supported counterpart is :func:`simply_supported_center_patch_load`
    and the one-sided one :func:`fixed_fixed_partial_uniform_load`.

    The hogging moment at the walls governs (σ = M·c/I with
    M = w·a·(3L² − a²)/(24L), from integrating the point-load fixed-end-moment
    influence over the patch; the mid-span sagging peak w·a·(3L² − 3aL + a²)/(24L)
    trails it by w·a²·(3L − 2a)/(24L) for every patch length) and the maximum
    deflection sits at mid-span by symmetry,
    δ = w·a·(2L³ − 2La² + a³)/(384·E·I). Every argument is dimension-checked;
    verified against an independent numeric integration of the beam ODE.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(loaded_length, "[length]", "loaded_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    length_p = length.pint
    loaded = loaded_length.pint.to(length_p.units)
    if not 0 < loaded.magnitude <= length_p.magnitude:
        raise ValueError(
            f"loaded_length must lie within the span (0, {length}]; got {loaded_length}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * loaded * (3 * length_p**2 - loaded**2) / (24 * length_p)
    stress = moment * c / inertia
    deflection = (
        w * loaded * (2 * length_p**3 - 2 * length_p * loaded**2 + loaded**3) / (384 * e * inertia)
    )
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def fixed_fixed_triangular_load(
    *,
    peak_distributed_load: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The fixed-fixed beam under a linearly varying (triangular) load (Roark).

    A prismatic beam clamped at both ends over a span ``length``, carrying a load
    that rises linearly from zero at one wall to ``peak_distributed_load`` w₀
    (force per unit length) at the other — hydrostatic pressure on a stiffener
    whose ends are welded in. The peak-end wall moment w₀·L²/20 governs (the
    zero-end wall carries w₀·L²/30, the interior sagging peak only ≈w₀·L²/47).

    Returns the peak bending stress at the loaded-end wall (σ = M·c/I with
    M = w₀·L²/20) and the true maximum deflection from the elastic curve
    v(ξ) = (2ξ² − 3ξ³ + ξ⁵)·w₀·L⁴/(120·E·I), ξ measured from the zero end —
    its slope 5ξ³ − 9ξ + 4 factors as (ξ−1)(5ξ² + 5ξ − 4), putting the maximum
    at ξ = (√105 − 5)/10 ≈ 0.525 (≈w₀·L⁴/(764·E·I)). Every argument is
    dimension-checked.
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

    moment = w0 * length_p**2 / 20
    stress = moment * c / inertia
    xi = (sqrt(105) - 5) / 10
    deflection = (2 * xi**2 - 3 * xi**3 + xi**5) * w0 * length_p**4 / (120 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )
