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

from math import degrees, pi, sqrt

from pydantic import BaseModel, ConfigDict

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity, decimals_distinguishing, require_finite

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
    "cantilever_offset_moment",
    "simply_supported_center_load",
    "simply_supported_offset_load",
    "simply_supported_symmetric_point_loads",
    "simply_supported_uniform_load",
    "simply_supported_partial_uniform_load",
    "simply_supported_center_patch_load",
    "simply_supported_triangular_load",
    "simply_supported_end_moment",
    "simply_supported_offset_moment",
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
    "overhang_tip_load",
    "overhang_uniform_load",
    "rectangular_second_moment",
    "circular_second_moment",
    "hollow_circular_second_moment",
    "rectangular_tube_second_moment",
    "i_section_second_moment",
    "rectangular_plastic_section_modulus",
    "circular_plastic_section_modulus",
    "hollow_circular_plastic_section_modulus",
    "rectangular_tube_plastic_section_modulus",
    "i_section_plastic_section_modulus",
    "plastic_moment",
    "simply_supported_plastic_collapse_load",
    "fixed_fixed_plastic_collapse_load",
    "propped_cantilever_plastic_collapse_load",
    "simply_supported_center_load_support_slope",
    "simply_supported_uniform_load_support_slope",
    "cantilever_end_load_tip_slope",
    "cantilever_uniform_load_tip_slope",
    "simply_supported_plastic_collapse_udl",
    "fixed_fixed_plastic_collapse_udl",
    "propped_cantilever_plastic_collapse_udl",
    "max_transverse_shear_stress",
    "aisc_web_local_yielding_strength",
    "aisc_bearing_length_for_web_yielding",
    "aisc_web_crippling_strength",
    "aisc_web_compression_buckling_strength",
    "aisc_round_hss_flexural_strength",
    "aisc_round_hss_shear_strength",
    "aisc_rectangular_hss_shear_strength",
    "aisc_rectangular_hss_flexural_strength",
    "aisc_minor_axis_flexural_strength",
    "aisc_plate_girder_bending_factor",
    "aisc_plate_girder_flange_stress",
    "aisc_tension_field_shear_strength",
    "aisc_web_shear_strength",
    "two_span_continuous_middle_moment",
    "two_span_continuous_interior_reaction",
    "shear_flow",
    "fastener_spacing_for_shear_flow",
    "deflection_scorecard",
    "span_deflection_limit",
    "SHEAR_FORM_RECTANGULAR",
    "SHEAR_FORM_CIRCULAR",
]

# Peak-to-average transverse-shear form factors τ_max = k·V/A: 3/2 at the neutral
# axis of a rectangular section, 4/3 for a solid circular one.
SHEAR_FORM_RECTANGULAR = 1.5
SHEAR_FORM_CIRCULAR = 4.0 / 3.0


# Section and material properties that cannot be zero or negative in any beam formula:
# a span, a second moment, a distance to the extreme fibre, a modulus. The slope family
# has always enforced this through `_slope_inputs`; the ~30 bending-case functions only
# dimension-checked, so I = 0 was a bare ZeroDivisionError and I = −1e6 mm⁴ came back as a
# quietly negative stress and deflection — a wrong number with no signal, which is worse.
# Enforcing by name here means a new call site inherits the guard instead of forgetting it.
# Loads, moments and offsets are deliberately absent: a hogging moment and an uplift force
# are signed on purpose.
_POSITIVE_DEFINITE = frozenset({"length", "second_moment", "extreme_fibre", "elastic_modulus"})


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)
    if name in _POSITIVE_DEFINITE and value.magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")


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


def rectangular_tube_second_moment(
    *, width: Quantity, height: Quantity, wall_thickness: Quantity
) -> Quantity:
    """The bending second moment I = (b·h³ − b_i·h_i³)/12 of a rectangular (box) tube.

    A hollow rectangular section — an RHS/SHS box beam — subtracts its inner
    rectangle from the outer: I = (b·h³ − (b − 2t)·(h − 2t)³)/12 about the axis
    perpendicular to ``height``. ``width`` b and ``height`` h are the outer overall
    dimensions and ``wall_thickness`` t the wall; 2t must stay below both outer
    dimensions. A box carries far more I per unit weight than the solid bar it hollows
    out, which is why beams are box or I sections. Returns the second moment in mm⁴.
    """
    _require(width, "[length]", "width")
    _require(height, "[length]", "height")
    _require(wall_thickness, "[length]", "wall_thickness")
    b = width.to("mm").magnitude
    h = height.to("mm").magnitude
    t = wall_thickness.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"wall_thickness must be positive; got {wall_thickness}")
    if 2 * t >= b or 2 * t >= h:
        raise ValueError(
            f"2*wall_thickness ({2 * t} mm) must be below both width and height ({width}, {height})"
        )
    inner = (b - 2 * t) * (h - 2 * t) ** 3
    return Quantity(magnitude=(b * h**3 - inner) / 12.0, unit="mm**4")


def i_section_second_moment(
    *,
    flange_width: Quantity,
    total_height: Quantity,
    flange_thickness: Quantity,
    web_thickness: Quantity,
) -> Quantity:
    """The strong-axis second moment I = (b·h³ − (b − t_w)·(h − 2·t_f)³)/12 of an I-beam.

    A doubly-symmetric I- or H-section is the outer bounding rectangle minus the two
    web-flanking voids: I = (b·h³ − (b − t_w)·(h − 2·t_f)³)/12 about the strong
    (horizontal) axis. ``flange_width`` b, ``total_height`` h, ``flange_thickness``
    t_f, and ``web_thickness`` t_w describe the section, with 2·t_f < h and t_w < b.
    Nearly all the material sits in the flanges far from the axis, which is where the
    I-section's stiffness-per-weight comes from. Returns the second moment in mm⁴.
    """
    _require(flange_width, "[length]", "flange_width")
    _require(total_height, "[length]", "total_height")
    _require(flange_thickness, "[length]", "flange_thickness")
    _require(web_thickness, "[length]", "web_thickness")
    b = flange_width.to("mm").magnitude
    h = total_height.to("mm").magnitude
    tf = flange_thickness.to("mm").magnitude
    tw = web_thickness.to("mm").magnitude
    if tf <= 0 or tw <= 0:
        raise ValueError("flange_thickness and web_thickness must be positive")
    if 2 * tf >= h:
        raise ValueError(f"2*flange_thickness ({2 * tf} mm) must be below total_height ({h} mm)")
    if tw >= b:
        raise ValueError(f"web_thickness ({tw} mm) must be below flange_width ({b} mm)")
    return Quantity(magnitude=(b * h**3 - (b - tw) * (h - 2 * tf) ** 3) / 12.0, unit="mm**4")


def rectangular_plastic_section_modulus(width: Quantity, height: Quantity) -> Quantity:
    """The plastic section modulus Z_p = b·h²/4 of a rectangular section.

    Where the elastic section modulus (:meth:`CrossSection.section_modulus`, I/c =
    b·h²/6) sets first yield at the extreme fibre, the *plastic* modulus sets the
    fully-plastic moment M_p = Z_p·S_y at which the whole section has yielded and a
    plastic hinge forms. For a rectangle Z_p = b·h²/4, exactly 3/2 of the elastic
    b·h²/6 — the rectangle's shape factor. ``width`` b and ``height`` h (the depth in
    the load direction) must be positive lengths. Returns Z_p in mm³.
    """
    _require(width, "[length]", "width")
    _require(height, "[length]", "height")
    return _as_quantity(width.pint * height.pint**2 / 4, "mm**3")


def circular_plastic_section_modulus(diameter: Quantity) -> Quantity:
    """The plastic section modulus Z_p = d³/6 of a solid circular section.

    The round-bar counterpart of :func:`rectangular_plastic_section_modulus`: the
    fully-plastic modulus is Z_p = d³/6, against the elastic π·d³/32, so a solid
    circle's shape factor is 16/(3π) ≈ 1.70 — a round section keeps more reserve past
    first yield than a rectangle does. ``diameter`` d must be a positive length.
    Returns Z_p in mm³.
    """
    _require(diameter, "[length]", "diameter")
    return _as_quantity(diameter.pint**3 / 6, "mm**3")


def hollow_circular_plastic_section_modulus(
    *, outer_diameter: Quantity, inner_diameter: Quantity
) -> Quantity:
    """The plastic section modulus Z_p = (D³ − d³)/6 of a hollow circular (tube) section.

    The tube form of :func:`circular_plastic_section_modulus`: the fully-plastic
    modulus subtracts the bore from the outside, Z_p = (D³ − d³)/6, recovering the
    solid d³/6 as the bore vanishes. ``outer_diameter`` D and ``inner_diameter`` d
    (which must be non-negative and below D) set it. Returns Z_p in mm³.
    """
    _require(outer_diameter, "[length]", "outer_diameter")
    _require(inner_diameter, "[length]", "inner_diameter")
    do = outer_diameter.to("mm").magnitude
    di = inner_diameter.to("mm").magnitude
    if not 0 <= di < do:
        raise ValueError(
            f"inner_diameter ({inner_diameter}) must be non-negative and below "
            f"outer_diameter ({outer_diameter})"
        )
    return _as_quantity((outer_diameter.pint**3 - inner_diameter.pint**3) / 6, "mm**3")


def rectangular_tube_plastic_section_modulus(
    *, width: Quantity, height: Quantity, wall_thickness: Quantity
) -> Quantity:
    """The plastic section modulus Z_p = (b·h² − b_i·h_i²)/4 of a rectangular (box) tube.

    The box-tube form of :func:`rectangular_plastic_section_modulus`, the plastic
    counterpart of :func:`rectangular_tube_second_moment`: it subtracts the inner
    rectangle's plastic modulus from the outer's,
    Z_p = (b·h² − (b − 2t)·(h − 2t)²)/4, bending about the axis perpendicular to
    ``height``. ``width`` b and ``height`` h are the outer overall dimensions and
    ``wall_thickness`` t the wall; 2t must stay below both. Returns Z_p in mm³.
    """
    _require(width, "[length]", "width")
    _require(height, "[length]", "height")
    _require(wall_thickness, "[length]", "wall_thickness")
    b = width.to("mm").magnitude
    h = height.to("mm").magnitude
    t = wall_thickness.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"wall_thickness must be positive; got {wall_thickness}")
    if 2 * t >= b or 2 * t >= h:
        raise ValueError(
            f"2*wall_thickness ({2 * t} mm) must be below both width and height ({width}, {height})"
        )
    inner = (b - 2 * t) * (h - 2 * t) ** 2
    return Quantity(magnitude=(b * h**2 - inner) / 4.0, unit="mm**3")


def i_section_plastic_section_modulus(
    *,
    flange_width: Quantity,
    total_height: Quantity,
    flange_thickness: Quantity,
    web_thickness: Quantity,
) -> Quantity:
    """The strong-axis plastic section modulus of a doubly-symmetric I-section.

    Summing area·(distance to the plastic neutral axis) over the fully-yielded
    section gives, for the two flanges plus the web,

        Z_p = b·t_f·(h − t_f) + t_w·(h − 2·t_f)²/4,

    the plastic counterpart of :func:`i_section_second_moment` (and, with the flanges
    grown to fill the depth, it recovers the solid rectangle's b·h²/4).
    ``flange_width`` b, ``total_height`` h, ``flange_thickness`` t_f, and
    ``web_thickness`` t_w describe the section, with 2·t_f < h and t_w < b. Because
    an I-section piles its area in the flanges its shape factor is low (~1.1–1.2), so
    it keeps little reserve past first yield. Returns Z_p in mm³.
    """
    _require(flange_width, "[length]", "flange_width")
    _require(total_height, "[length]", "total_height")
    _require(flange_thickness, "[length]", "flange_thickness")
    _require(web_thickness, "[length]", "web_thickness")
    b = flange_width.to("mm").magnitude
    h = total_height.to("mm").magnitude
    tf = flange_thickness.to("mm").magnitude
    tw = web_thickness.to("mm").magnitude
    if tf <= 0 or tw <= 0:
        raise ValueError("flange_thickness and web_thickness must be positive")
    if 2 * tf >= h:
        raise ValueError(f"2*flange_thickness ({2 * tf} mm) must be below total_height ({h} mm)")
    if tw >= b:
        raise ValueError(f"web_thickness ({tw} mm) must be below flange_width ({b} mm)")
    z_p = b * tf * (h - tf) + tw * (h - 2 * tf) ** 2 / 4.0
    return Quantity(magnitude=z_p, unit="mm**3")


def plastic_moment(*, plastic_section_modulus: Quantity, yield_strength: Quantity) -> Quantity:
    """The fully-plastic moment M_p = Z_p·S_y of a section.

    The moment at which a whole section has yielded and forms a plastic hinge — the
    basis of plastic (limit-state) design and the collapse load of a ductile beam.
    ``plastic_section_modulus`` Z_p is the section's plastic modulus (e.g.
    :func:`rectangular_plastic_section_modulus`) and ``yield_strength`` S_y the
    material's yield stress. It exceeds the first-yield moment M_y = S·S_y by the
    section's shape factor Z_p/S. Both must be positive. Returns M_p in N·m.
    """
    _require(plastic_section_modulus, "[length]**3", "plastic_section_modulus")
    _require(yield_strength, "[pressure]", "yield_strength")
    if plastic_section_modulus.to("mm**3").magnitude <= 0:
        raise ValueError(f"plastic_section_modulus must be positive; got {plastic_section_modulus}")
    if yield_strength.to("MPa").magnitude <= 0:
        raise ValueError(f"yield_strength must be positive; got {yield_strength}")
    return _as_quantity(plastic_section_modulus.pint * yield_strength.pint, "N*m")


def _collapse_inputs(
    plastic_moment_capacity: Quantity, span: Quantity
) -> tuple[Quantity, Quantity]:
    _require(plastic_moment_capacity, "[force] * [length]", "plastic_moment_capacity")
    _require(span, "[length]", "span")
    if plastic_moment_capacity.to("N*m").magnitude <= 0:
        raise ValueError(f"plastic_moment_capacity must be positive; got {plastic_moment_capacity}")
    if span.to("mm").magnitude <= 0:
        raise ValueError(f"span must be positive; got {span}")
    return plastic_moment_capacity, span


def simply_supported_plastic_collapse_load(
    *, plastic_moment_capacity: Quantity, span: Quantity
) -> Quantity:
    """The central point load that collapses a simply-supported beam, P = 4·M_p/L.

    A simply-supported beam under a central point load collapses when a single
    plastic hinge forms at midspan, where the peak moment P·L/4 reaches the section's
    plastic moment M_p — so the collapse load is P = 4·M_p/L (equivalently, the
    beam is statically determinate, so collapse coincides with the midspan section
    fully yielding). ``plastic_moment_capacity`` M_p is the section's fully-plastic
    moment (:func:`plastic_moment`) and ``span`` L the support spacing; both must be
    positive. Returns the collapse point load in newtons.
    """
    mp, length = _collapse_inputs(plastic_moment_capacity, span)
    return _as_quantity(4 * mp.pint / length.pint, "N")


def fixed_fixed_plastic_collapse_load(
    *, plastic_moment_capacity: Quantity, span: Quantity
) -> Quantity:
    """The central point load that collapses a fixed-fixed beam, P = 8·M_p/L.

    A built-in (fixed-fixed) beam is statically indeterminate, so it does not fail
    when the first section yields: hinges form at the two fixed ends and then a third
    at midspan before a mechanism develops. Virtual work on that three-hinge
    mechanism (end rotations θ, a 2θ midspan hinge) gives P·(L/2)·θ = 4·M_p·θ, i.e.
    P = 8·M_p/L — twice the simply-supported
    :func:`simply_supported_plastic_collapse_load`, the extra capacity coming from
    the moment redistribution a ductile indeterminate structure allows.
    ``plastic_moment_capacity`` M_p and ``span`` L must be positive. Returns the
    collapse point load in newtons.
    """
    mp, length = _collapse_inputs(plastic_moment_capacity, span)
    return _as_quantity(8 * mp.pint / length.pint, "N")


def propped_cantilever_plastic_collapse_load(
    *, plastic_moment_capacity: Quantity, span: Quantity
) -> Quantity:
    """The central point load that collapses a propped cantilever, P = 6·M_p/L.

    A propped cantilever (fixed one end, propped the other) under a central point
    load fails by a two-hinge mechanism: a hinge at the fixed end and one under the
    load. Virtual work (end rotation θ, a 2θ hinge under the load) gives
    P·(L/2)·θ = 3·M_p·θ, i.e. P = 6·M_p/L — between the simply-supported
    :func:`simply_supported_plastic_collapse_load` (4·M_p/L) and the fixed-fixed
    :func:`fixed_fixed_plastic_collapse_load` (8·M_p/L), as its one fixed end sits
    between the two support conditions. ``plastic_moment_capacity`` M_p and ``span``
    L must be positive. Returns the collapse point load in newtons.
    """
    mp, length = _collapse_inputs(plastic_moment_capacity, span)
    return _as_quantity(6 * mp.pint / length.pint, "N")


def _slope_inputs(
    length: Quantity, second_moment: Quantity, elastic_modulus: Quantity
) -> tuple[float, float, float]:
    """Validate and return (L, I, E) in mm, mm⁴, MPa for a beam-slope formula."""
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    ell = length.to("mm").magnitude
    i = second_moment.to("mm**4").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if ell <= 0 or i <= 0 or e <= 0:
        raise ValueError("length, second_moment, and elastic_modulus must be positive")
    return ell, i, e


def simply_supported_center_load_support_slope(
    *,
    force: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The end slope θ = F·L²/(16·E·I) of a simply-supported beam with a central load.

    A simply-supported beam bends most steeply at its supports, where the slope is
    θ = F·L²/(16·E·I) for a central point ``force`` F. On a shaft this is the
    *misalignment angle* the load imposes on the bearings at the ends — a rolling
    bearing tolerates only about 0.001–0.004 rad before its life falls off, so this is
    the slope to screen against the bearing's allowable, not just the midspan
    deflection. ``length`` L, ``second_moment`` I, and ``elastic_modulus`` E are the
    beam's; all must be positive. Returns the support slope in degrees (a radian
    tolerance is degrees·π/180).
    """
    _require(force, "[force]", "force")
    ell, i, e = _slope_inputs(length, second_moment, elastic_modulus)
    f = force.to("N").magnitude
    slope_rad = f * ell**2 / (16.0 * e * i)
    return Quantity(magnitude=degrees(slope_rad), unit="degree")


def simply_supported_uniform_load_support_slope(
    *,
    load_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The end slope θ = w·L³/(24·E·I) of a simply-supported beam under a uniform load.

    The distributed-load counterpart of
    :func:`simply_supported_center_load_support_slope`: a simply-supported beam under a
    uniform ``load_per_length`` w slopes at its supports by θ = w·L³/(24·E·I) — the
    self-weight or distributed-load misalignment a shaft imposes on its end bearings.
    ``length`` L, ``second_moment`` I, and ``elastic_modulus`` E must be positive.
    Returns the support slope in degrees.
    """
    _require(load_per_length, "[force] / [length]", "load_per_length")
    ell, i, e = _slope_inputs(length, second_moment, elastic_modulus)
    w = load_per_length.to("N/mm").magnitude
    slope_rad = w * ell**3 / (24.0 * e * i)
    return Quantity(magnitude=degrees(slope_rad), unit="degree")


def cantilever_end_load_tip_slope(
    *,
    force: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The free-end slope θ = F·L²/(2·E·I) of a cantilever with an end load.

    A cantilever bends most steeply at its tip, where the slope is θ = F·L²/(2·E·I)
    for an end ``force`` F. For an overhung shaft — a spindle nose, an outboard
    pulley — this is the misalignment angle the load imposes on the *inboard* bearing
    (or the tilt of a tool held at the tip), the slope counterpart of
    :func:`simply_supported_center_load_support_slope`. ``length`` L, ``second_moment``
    I, and ``elastic_modulus`` E must be positive. Returns the tip slope in degrees (a
    radian tolerance is degrees·π/180).
    """
    _require(force, "[force]", "force")
    ell, i, e = _slope_inputs(length, second_moment, elastic_modulus)
    f = force.to("N").magnitude
    slope_rad = f * ell**2 / (2.0 * e * i)
    return Quantity(magnitude=degrees(slope_rad), unit="degree")


def cantilever_uniform_load_tip_slope(
    *,
    load_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The free-end slope θ = w·L³/(6·E·I) of a cantilever under a uniform load.

    The distributed-load counterpart of :func:`cantilever_end_load_tip_slope`: a
    cantilever carrying a uniform ``load_per_length`` w tilts its free end by
    θ = w·L³/(6·E·I) — the self-weight or distributed-load misalignment an overhung
    shaft imposes on its inboard bearing, or the tilt of a boom under its own weight.
    ``length`` L, ``second_moment`` I, and ``elastic_modulus`` E must be positive.
    Returns the tip slope in degrees.
    """
    _require(load_per_length, "[force] / [length]", "load_per_length")
    ell, i, e = _slope_inputs(length, second_moment, elastic_modulus)
    w = load_per_length.to("N/mm").magnitude
    slope_rad = w * ell**3 / (6.0 * e * i)
    return Quantity(magnitude=degrees(slope_rad), unit="degree")


def simply_supported_plastic_collapse_udl(
    *, plastic_moment_capacity: Quantity, span: Quantity
) -> Quantity:
    """The distributed load that collapses a simply-supported beam, w = 8·M_p/L².

    Under a uniform load the peak (midspan) moment of a simply-supported beam is
    w·L²/8, so a plastic hinge forms there and the beam collapses when it reaches the
    plastic moment M_p: w = 8·M_p/L². ``plastic_moment_capacity`` M_p
    (:func:`plastic_moment`) and ``span`` L must be positive. Returns the collapse
    load per unit length in N/m.
    """
    mp, length = _collapse_inputs(plastic_moment_capacity, span)
    return _as_quantity(8 * mp.pint / length.pint**2, "N/m")


def fixed_fixed_plastic_collapse_udl(
    *, plastic_moment_capacity: Quantity, span: Quantity
) -> Quantity:
    """The distributed load that collapses a fixed-fixed beam, w = 16·M_p/L².

    The built-in counterpart of :func:`simply_supported_plastic_collapse_udl`: with
    hinges forming at the two fixed ends and at midspan, virtual work on the
    three-hinge mechanism (w·(L·δ/2) = 4·M_p·θ, δ = θ·L/2) gives w = 16·M_p/L² —
    twice the simply-supported collapse load, the reserve from moment redistribution
    in a ductile indeterminate beam. ``plastic_moment_capacity`` M_p and ``span`` L
    must be positive. Returns the collapse load per unit length in N/m.
    """
    mp, length = _collapse_inputs(plastic_moment_capacity, span)
    return _as_quantity(16 * mp.pint / length.pint**2, "N/m")


def propped_cantilever_plastic_collapse_udl(
    *, plastic_moment_capacity: Quantity, span: Quantity
) -> Quantity:
    """The distributed load that collapses a propped cantilever, w = (6 + 4√2)·M_p/L².

    A propped cantilever (fixed at one end, simply propped at the other) under a
    uniform load fails by a two-hinge mechanism: one hinge at the fixed end and a
    second, sagging hinge in the span. Unlike the symmetric fixed-fixed case the span
    hinge does not sit at midspan — minimizing the collapse load over its position
    (the kinematic theorem) places it at (√2 − 1)·L ≈ 0.414·L from the propped end and
    gives w = (6 + 4√2)·M_p/L² ≈ 11.66·M_p/L², between the simply-supported 8 and the
    fixed-fixed 16. ``plastic_moment_capacity`` M_p (:func:`plastic_moment`) and
    ``span`` L must be positive. Returns the collapse load per unit length in N/m.
    """
    mp, length = _collapse_inputs(plastic_moment_capacity, span)
    return _as_quantity((6.0 + 4.0 * sqrt(2.0)) * mp.pint / length.pint**2, "N/m")


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


def aisc_web_local_yielding_strength(
    *,
    web_yield: Quantity,
    web_thickness: Quantity,
    fillet_distance: Quantity,
    bearing_length: Quantity,
    at_member_end: bool = False,
) -> Quantity:
    """The AISC 360 §J10.2 web local yielding strength at a concentrated load.

    A concentrated load (a support reaction or a bearing point) spreads from the
    flange into the web at roughly 1:1 (2.5:1 through the fillet), and the web yields
    over that spread length: R_n = F_yw·t_w·(C·k + N). ``web_yield`` F_yw is the web's
    yield, ``web_thickness`` t_w the web thickness, ``fillet_distance`` k the distance
    from the outer flange face to the web toe of the fillet, and ``bearing_length`` N
    the length of bearing. ``at_member_end`` picks the spread coefficient C — 2.5 for a
    load within a member depth of the end (one-sided spread), 5.0 for an interior load
    (two-sided). A thicker web, a deeper fillet, or a longer bearing all raise the
    strength; a thin web at a short bearing is where beams crush at their supports.
    Returns R_n in kN.
    """
    _require(web_yield, "[pressure]", "web_yield")
    _require(web_thickness, "[length]", "web_thickness")
    _require(fillet_distance, "[length]", "fillet_distance")
    _require(bearing_length, "[length]", "bearing_length")
    fyw = web_yield.to("MPa").magnitude
    tw = web_thickness.to("mm").magnitude
    k = fillet_distance.to("mm").magnitude
    n = bearing_length.to("mm").magnitude
    if fyw <= 0 or tw <= 0 or k <= 0 or n < 0:
        raise ValueError(
            "web_yield, web_thickness, and fillet_distance must be positive and "
            "bearing_length non-negative"
        )
    coefficient = 2.5 if at_member_end else 5.0
    rn_n = fyw * tw * (coefficient * k + n)
    return Quantity(magnitude=rn_n / 1000.0, unit="kN")


def aisc_bearing_length_for_web_yielding(
    *,
    required_reaction: Quantity,
    web_yield: Quantity,
    web_thickness: Quantity,
    fillet_distance: Quantity,
    at_member_end: bool = False,
) -> Quantity:
    """The minimum bearing length N so the web local yielding strength meets a reaction.

    The design inverse of :func:`aisc_web_local_yielding_strength`: given the reaction a
    seat or bearing must deliver, solve R_n = F_yw·t_w·(C·k + N) for the bearing length
    N = R/(F_yw·t_w) − C·k. That is the seat width (or the stiff-bearing length of a
    bearing plate) a detailer needs so the web does not crush — the number the forward
    check leaves you to back into by trial. ``required_reaction`` R, ``web_yield`` F_yw,
    ``web_thickness`` t_w, and ``fillet_distance`` k as in the forward check;
    ``at_member_end`` picks the spread coefficient C (2.5 at an end, 5.0 interior). When
    the web alone already carries the reaction over its fillet spread the result clamps
    to zero (no bearing length is required). Returns N in mm.
    """
    _require(required_reaction, "[force]", "required_reaction")
    _require(web_yield, "[pressure]", "web_yield")
    _require(web_thickness, "[length]", "web_thickness")
    _require(fillet_distance, "[length]", "fillet_distance")
    r = required_reaction.to("N").magnitude
    fyw = web_yield.to("MPa").magnitude
    tw = web_thickness.to("mm").magnitude
    k = fillet_distance.to("mm").magnitude
    if r <= 0 or fyw <= 0 or tw <= 0 or k <= 0:
        raise ValueError(
            "required_reaction, web_yield, web_thickness, and fillet_distance must be positive"
        )
    coefficient = 2.5 if at_member_end else 5.0
    n_mm = r / (fyw * tw) - coefficient * k
    return Quantity(magnitude=max(0.0, n_mm), unit="mm")


def aisc_web_crippling_strength(
    *,
    web_thickness: Quantity,
    flange_thickness: Quantity,
    member_depth: Quantity,
    bearing_length: Quantity,
    web_yield: Quantity,
    elastic_modulus: Quantity,
    at_member_end: bool = False,
) -> Quantity:
    """The AISC 360 §J10.3 web local crippling strength at a concentrated load.

    Web local yielding (:func:`aisc_web_local_yielding_strength`) is the web crushing;
    web crippling is the web *buckling* — the thin web folding out of plane under the
    bearing. Both are checked at every concentrated load and the lesser governs. For an
    interior load (§J10.3a) R_n = 0.80·t_w²·[1 + 3(N/d)(t_w/t_f)^1.5]·√(E·F_yw·t_f/t_w);
    for a load within half a depth of the member end (§J10.3b) the leading coefficient
    drops to 0.40, and once the bearing is long (N/d > 0.2) the bracket becomes
    [1 + (4N/d − 0.2)(t_w/t_f)^1.5]. ``web_thickness`` t_w, ``flange_thickness`` t_f,
    ``member_depth`` d, ``bearing_length`` N, ``web_yield`` F_yw, and ``elastic_modulus``
    E. A thicker web dominates (the t_w² term); a thin web at a member end with a short
    bearing is the weakest case. Returns R_n in kN.
    """
    _require(web_thickness, "[length]", "web_thickness")
    _require(flange_thickness, "[length]", "flange_thickness")
    _require(member_depth, "[length]", "member_depth")
    _require(bearing_length, "[length]", "bearing_length")
    _require(web_yield, "[pressure]", "web_yield")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    tw = web_thickness.to("mm").magnitude
    tf = flange_thickness.to("mm").magnitude
    d = member_depth.to("mm").magnitude
    n = bearing_length.to("mm").magnitude
    fyw = web_yield.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if tw <= 0 or tf <= 0 or d <= 0 or n < 0 or fyw <= 0 or e <= 0:
        raise ValueError(
            "web_thickness, flange_thickness, member_depth, web_yield, and "
            "elastic_modulus must be positive and bearing_length non-negative"
        )
    n_over_d = n / d
    ratio = (tw / tf) ** 1.5
    if at_member_end:
        coefficient = 0.40
        bracket = (
            1.0 + (4.0 * n_over_d - 0.2) * ratio if n_over_d > 0.2 else 1.0 + 3.0 * n_over_d * ratio
        )
    else:
        coefficient = 0.80
        bracket = 1.0 + 3.0 * n_over_d * ratio
    rn_n = coefficient * tw**2 * bracket * (e * fyw * tf / tw) ** 0.5
    return Quantity(magnitude=rn_n / 1000.0, unit="kN")


def aisc_web_compression_buckling_strength(
    *,
    web_thickness: Quantity,
    clear_web_depth: Quantity,
    web_yield: Quantity,
    elastic_modulus: Quantity,
    at_member_end: bool = False,
) -> Quantity:
    """The AISC 360 §J10.5 web compression buckling strength under a force pair.

    Where two opposing concentrated forces bear on both flanges at the same section —
    the compression flange of a beam framing into a column, both flanges of a moment
    connection — the web between them acts like a stubby column and can buckle:
    R_n = 24·t_w³·√(E·F_yw)/h, with ``web_thickness`` t_w, ``clear_web_depth`` h (the
    clear distance between flanges less the fillets), ``web_yield`` F_yw, and
    ``elastic_modulus`` E. The cube on t_w makes web thickness decisive and a slender
    (large h) web the vulnerable one. Per §J10.5 the strength is halved when the force
    pair sits within half a member depth of the end (``at_member_end``). This is the
    two-sided companion to the one-sided web local yielding and crippling checks.
    Returns R_n in kN.
    """
    _require(web_thickness, "[length]", "web_thickness")
    _require(clear_web_depth, "[length]", "clear_web_depth")
    _require(web_yield, "[pressure]", "web_yield")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    tw = web_thickness.to("mm").magnitude
    h = clear_web_depth.to("mm").magnitude
    fyw = web_yield.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if tw <= 0 or h <= 0 or fyw <= 0 or e <= 0:
        raise ValueError(
            "web_thickness, clear_web_depth, web_yield, and elastic_modulus must be positive"
        )
    rn_n = 24.0 * tw**3 * (e * fyw) ** 0.5 / h
    if at_member_end:
        rn_n *= 0.5
    return Quantity(magnitude=rn_n / 1000.0, unit="kN")


def aisc_round_hss_flexural_strength(
    *,
    diameter: Quantity,
    thickness: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
    plastic_section_modulus: Quantity,
    elastic_section_modulus: Quantity,
) -> Quantity:
    """The AISC 360 §F8 flexural strength of a round HSS or pipe.

    Round tubes bend differently from I-shapes: there is no lateral-torsional buckling,
    and the only slenderness that matters is the wall's D/t. §F8 reads the wall in three
    ranges against λ_p = 0.07·E/F_y and λ_r = 0.31·E/F_y. A compact wall reaches the full
    plastic moment M_p = F_y·Z (§F8.1). A noncompact wall buckles locally at
    M_n = (0.021·E/(D/t) + F_y)·S, and a slender wall at M_n = F_cr·S with F_cr =
    0.33·E/(D/t) (§F8.2) — both capped at M_p. ``diameter`` D, ``thickness`` t (wall),
    ``yield_strength`` F_y, ``elastic_modulus`` E, ``plastic_section_modulus`` Z, and
    ``elastic_section_modulus`` S. §F8 does not apply past D/t = 0.45·E/F_y (the tube is
    then too thin to carry bending as a section) — that raises. Returns M_n in kN·m.
    """
    _require(diameter, "[length]", "diameter")
    _require(thickness, "[length]", "thickness")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not isinstance(plastic_section_modulus, Quantity):
        raise ValueError(
            f"plastic_section_modulus must be a [length]**3 quantity; "
            f"got {plastic_section_modulus!r}"
        )
    if not plastic_section_modulus.has_dimension("[length]**3"):
        raise ValueError("plastic_section_modulus must be a [length]**3 quantity")
    # Through the module's own `_require`, which checks finiteness. Written as a raw
    # `has_dimension` these three functions let a NaN elastic modulus past, and
    # `min(fy*Z, 1.6*fy*S)` then deleted the §F6.1 (and local-buckling) cap: all three
    # returned the *exact same number* as the all-valid call, with a limit state silently
    # removed. S = 0 was refused and S = NaN was not, and a NaN plastic modulus propagated
    # correctly — that asymmetry is the tell.
    _require(elastic_section_modulus, "[length]**3", "elastic_section_modulus")
    d = diameter.to("mm").magnitude
    t = thickness.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    z = plastic_section_modulus.to("mm**3").magnitude
    s = elastic_section_modulus.to("mm**3").magnitude
    if d <= 0 or t <= 0 or fy <= 0 or e <= 0 or z <= 0 or s <= 0:
        raise ValueError(
            "diameter, thickness, yield_strength, elastic_modulus, and the section "
            "moduli must all be positive"
        )
    dt = d / t
    limit = 0.45 * e / fy
    if dt > limit:
        # Both sides at a precision that keeps them apart. At one place a D/t of 90.04
        # against a limit of 90.0 read "90.0 exceeds the limit 90.0" — a refusal whose own
        # numbers say there is nothing to refuse.
        places = decimals_distinguishing(dt, limit, minimum=1)
        raise ValueError(
            f"D/t = {dt:.{places}f} exceeds the §F8 applicability limit "
            f"0.45E/F_y = {limit:.{places}f}"
        )
    lambda_p = 0.07 * e / fy
    lambda_r = 0.31 * e / fy
    m_p = fy * z
    if dt <= lambda_p:
        m_n = m_p
    elif dt <= lambda_r:
        m_n = (0.021 * e / dt + fy) * s
    else:
        m_n = 0.33 * e / dt * s
    m_n = min(m_n, m_p)
    return Quantity(magnitude=m_n / 1.0e6, unit="kN*m")


def aisc_rectangular_hss_flexural_strength(
    *,
    flange_flat_width: Quantity,
    web_flat_height: Quantity,
    wall_thickness: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
    plastic_section_modulus: Quantity,
    elastic_section_modulus: Quantity,
) -> Quantity:
    """The AISC 360 §F7 flexural strength of a rectangular HSS or box section.

    A box in bending is limited by three things and the least governs: the plastic moment
    M_p = F_y·Z (§F7.1); flange local buckling of the compression wall (§F7.2); and web
    local buckling of the side walls (§F7.3). Each wall is read against its compact and
    noncompact limits — the flange against λ_pf = 1.12·√(E/F_y), λ_rf = 1.40·√(E/F_y); the
    web against λ_pw = 2.42·√(E/F_y), λ_rw = 5.70·√(E/F_y). A noncompact flange knocks the
    moment down by (M_p − F_y·S)·(3.57·(b/t)·√(F_y/E) − 4.0); a noncompact web by
    (M_p − F_y·S)·(0.305·(h/t)·√(F_y/E) − 0.738); both bottom out at the yield moment F_y·S.
    ``flange_flat_width`` b and ``web_flat_height`` h are the flat wall dimensions (overall
    less the corners), ``wall_thickness`` t, ``yield_strength`` F_y, ``elastic_modulus`` E,
    ``plastic_section_modulus`` Z, and ``elastic_section_modulus`` S. A slender flange
    (b/t > λ_rf) or slender web (h/t > λ_rw) needs the §F7 effective-section provisions,
    which depend on the full section geometry — this raises rather than guess. Returns
    M_n in kN·m.
    """
    _require(flange_flat_width, "[length]", "flange_flat_width")
    _require(web_flat_height, "[length]", "web_flat_height")
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not isinstance(plastic_section_modulus, Quantity):
        raise ValueError(
            f"plastic_section_modulus must be a [length]**3 quantity; "
            f"got {plastic_section_modulus!r}"
        )
    if not plastic_section_modulus.has_dimension("[length]**3"):
        raise ValueError("plastic_section_modulus must be a [length]**3 quantity")
    # Through the module's own `_require`, which checks finiteness. Written as a raw
    # `has_dimension` these three functions let a NaN elastic modulus past, and
    # `min(fy*Z, 1.6*fy*S)` then deleted the §F6.1 (and local-buckling) cap: all three
    # returned the *exact same number* as the all-valid call, with a limit state silently
    # removed. S = 0 was refused and S = NaN was not, and a NaN plastic modulus propagated
    # correctly — that asymmetry is the tell.
    _require(elastic_section_modulus, "[length]**3", "elastic_section_modulus")
    b = flange_flat_width.to("mm").magnitude
    h = web_flat_height.to("mm").magnitude
    t = wall_thickness.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    z = plastic_section_modulus.to("mm**3").magnitude
    s = elastic_section_modulus.to("mm**3").magnitude
    if b <= 0 or h <= 0 or t <= 0 or fy <= 0 or e <= 0 or z <= 0 or s <= 0:
        raise ValueError(
            "flange_flat_width, web_flat_height, wall_thickness, yield_strength, "
            "elastic_modulus, and the section moduli must all be positive"
        )
    root = (e / fy) ** 0.5
    b_t = b / t
    h_t = h / t
    lambda_rf = 1.40 * root
    lambda_rw = 5.70 * root
    if b_t > lambda_rf:
        raise ValueError(
            f"slender flange (b/t = {b_t:.1f} > lambda_rf = {lambda_rf:.1f}); §F7 "
            "effective-section modulus is required and is not implemented"
        )
    if h_t > lambda_rw:
        raise ValueError(
            f"slender web (h/t = {h_t:.1f} > lambda_rw = {lambda_rw:.1f}); §F7 "
            "effective-section modulus is required and is not implemented"
        )
    lambda_pf = 1.12 * root
    lambda_pw = 2.42 * root
    m_p = fy * z
    m_yield = fy * s
    m_n = m_p
    if b_t > lambda_pf:
        m_flb = m_p - (m_p - m_yield) * (3.57 * b_t * (fy / e) ** 0.5 - 4.0)
        m_n = min(m_n, m_flb)
    if h_t > lambda_pw:
        m_wlb = m_p - (m_p - m_yield) * (0.305 * h_t * (fy / e) ** 0.5 - 0.738)
        m_n = min(m_n, m_wlb)
    m_n = min(m_n, m_p)
    return Quantity(magnitude=m_n / 1.0e6, unit="kN*m")


def aisc_plate_girder_bending_factor(
    *,
    web_clear_depth: Quantity,
    web_thickness: Quantity,
    compression_flange_width: Quantity,
    compression_flange_thickness: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
) -> float:
    """The AISC 360 §F5 bending-strength reduction factor R_pg of a slender-web girder.

    A deep built-up plate girder has a web too slender to keep its share of the bending
    stress; it buckles and sheds load to the flanges, and §F5 debits the flexural
    strength by R_pg = 1 − (a_w/(1200 + 300·a_w))·(h_c/t_w − 5.7·√(E/F_y)) ≤ 1.0, where
    a_w = h_c·t_w/(b_fc·t_fc) is the web-to-compression-flange area ratio (capped at 10).
    ``web_clear_depth`` h_c (twice the distance from the centroid to the inside of the
    compression flange — the web depth for a symmetric girder), ``web_thickness`` t_w,
    ``compression_flange_width`` b_fc, ``compression_flange_thickness`` t_fc,
    ``yield_strength`` F_y, and ``elastic_modulus`` E. A web at or below the slenderness
    limit 5.7·√(E/F_y) is not slender and R_pg is 1.0 (no penalty); a very slender web
    drives R_pg down. Multiply the compression-flange stress strength F_cr·S_xc by R_pg
    for the §F5 girder moment. Returns R_pg (0 to 1, dimensionless).
    """
    _require(web_clear_depth, "[length]", "web_clear_depth")
    _require(web_thickness, "[length]", "web_thickness")
    _require(compression_flange_width, "[length]", "compression_flange_width")
    _require(compression_flange_thickness, "[length]", "compression_flange_thickness")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    hc = web_clear_depth.to("mm").magnitude
    tw = web_thickness.to("mm").magnitude
    bfc = compression_flange_width.to("mm").magnitude
    tfc = compression_flange_thickness.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if hc <= 0 or tw <= 0 or bfc <= 0 or tfc <= 0 or fy <= 0 or e <= 0:
        raise ValueError("all dimensions and material properties must be positive")
    a_w = min(hc * tw / (bfc * tfc), 10.0)
    limit = 5.7 * (e / fy) ** 0.5
    r_pg = 1.0 - (a_w / (1200.0 + 300.0 * a_w)) * (hc / tw - limit)
    if r_pg <= 0.0:
        raise ValueError(
            f"web slenderness h_c/t_w = {hc / tw:.0f} drives the F5 reduction factor to "
            f"{r_pg:.3f}, at or below zero — the girder is far outside the range the §F5 "
            "linear reduction covers (AISC caps web slenderness separately in §F13.2)"
        )
    return min(r_pg, 1.0)


def aisc_tension_field_shear_strength(
    *,
    web_area: Quantity,
    web_depth: Quantity,
    web_thickness: Quantity,
    stiffener_spacing: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The AISC 360 §G2.2 shear strength of a stiffened girder web with tension-field action.

    Once a transversely-stiffened web buckles in shear, it does not fail — the panel acts
    like a Pratt truss, the buckled web carrying diagonal tension while the stiffeners take
    compression. §G2.2 credits that post-buckling reserve:
    V_n = 0.6·F_y·A_w·[C_v2 + (1 − C_v2)/(1.15·√(1 + (a/h)²))], where the second term is the
    tension-field bonus over the plain buckling strength 0.6·F_y·A_w·C_v2. ``web_area`` A_w,
    ``web_depth`` h (clear web between flanges), ``web_thickness`` t_w, ``stiffener_spacing``
    a (clear distance between transverse stiffeners), ``yield_strength`` F_y, and
    ``elastic_modulus`` E. The stiffener spacing sets both the panel aspect ratio a/h and the
    plate buckling coefficient k_v = 5 + 5/(a/h)², from which the web shear coefficient C_v2
    follows. Closer stiffeners (small a/h) mobilize more tension field. Tension-field action
    is not permitted for end panels or when the flanges are too small to anchor it (§G2.2(b));
    check those limits before relying on this. Returns V_n in kN.
    """
    if not isinstance(web_area, Quantity):
        raise ValueError(f"web_area must be a [length]**2 quantity; got {web_area!r}")
    if not web_area.has_dimension("[length]**2"):
        raise ValueError("web_area must be a [length]**2 quantity")
    _require(web_depth, "[length]", "web_depth")
    _require(web_thickness, "[length]", "web_thickness")
    _require(stiffener_spacing, "[length]", "stiffener_spacing")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    a_w = web_area.to("mm**2").magnitude
    h = web_depth.to("mm").magnitude
    tw = web_thickness.to("mm").magnitude
    a = stiffener_spacing.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if a_w <= 0 or h <= 0 or tw <= 0 or a <= 0 or fy <= 0 or e <= 0:
        raise ValueError("all inputs must be positive")
    aspect = a / h
    h_tw = h / tw
    # AISC 360 §G2.2(b) does not permit tension-field action when the panel is too long to
    # anchor the field: a/h > 3.0, or a/h > [260/(h/t_w)]^2. Both are computable from the
    # arguments already here, and neither was checked -- so a web with essentially no
    # stiffeners still collected the tension-field bonus, 2.09x the §G2.1 strength at
    # a/h = 5 and still 1.22x at a/h = 20.
    aspect_limit = min(3.0, (260.0 / h_tw) ** 2)
    if aspect > aspect_limit:
        raise ValueError(
            f"a/h = {aspect:.4g} exceeds the AISC 360 §G2.2(b) limit of {aspect_limit:.4g} "
            f"(the smaller of 3.0 and [260/(h/t_w)]² = {(260.0 / h_tw) ** 2:.4g}), so tension-"
            f"field action is not permitted for this panel. Use the §G2.1 shear strength, "
            f"which takes no tension-field bonus"
        )
    kv = 5.0 + 5.0 / aspect**2
    limit_1 = 1.10 * (kv * e / fy) ** 0.5
    limit_2 = 1.37 * (kv * e / fy) ** 0.5
    if h_tw <= limit_1:
        c_v2 = 1.0
    elif h_tw <= limit_2:
        c_v2 = limit_1 / h_tw
    else:
        c_v2 = 1.51 * kv * e / (h_tw**2 * fy)
    tension_field = c_v2 + (1.0 - c_v2) / (1.15 * (1.0 + aspect**2) ** 0.5)
    v_n = 0.6 * fy * a_w * tension_field
    return Quantity(magnitude=v_n / 1000.0, unit="kN")


def aisc_plate_girder_flange_stress(
    *,
    flange_width: Quantity,
    flange_thickness: Quantity,
    web_depth: Quantity,
    web_thickness: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The AISC 360 §F5.3 compression-flange local-buckling stress F_cr of a plate girder.

    A plate girder's bending strength is M_n = R_pg·F_cr·S_xc
    (:func:`aisc_plate_girder_bending_factor` gives R_pg); this is the F_cr set by the
    compression flange buckling locally. Unlike a rolled shape, a girder flange's buckling
    limit depends on the web through the coefficient k_c = 4/√(h/t_w), bounded to
    [0.35, 0.76]: a slender web offers the flange less restraint. The flange slenderness
    λ = b_f/(2·t_f) is read against λ_pf = 0.38·√(E/F_y) and λ_rf = 0.95·√(k_c·E/F_L),
    F_L = 0.7·F_y. A compact flange reaches F_cr = F_y; a noncompact one falls linearly to
    F_L; a slender one buckles elastically at F_cr = 0.9·E·k_c/λ². ``flange_width`` b_f,
    ``flange_thickness`` t_f, ``web_depth`` h, ``web_thickness`` t_w, ``yield_strength`` F_y,
    and ``elastic_modulus`` E. Take the lesser of this and the girder's lateral-torsional
    buckling stress before applying R_pg. Returns F_cr in MPa.
    """
    _require(flange_width, "[length]", "flange_width")
    _require(flange_thickness, "[length]", "flange_thickness")
    _require(web_depth, "[length]", "web_depth")
    _require(web_thickness, "[length]", "web_thickness")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    bf = flange_width.to("mm").magnitude
    tf = flange_thickness.to("mm").magnitude
    h = web_depth.to("mm").magnitude
    tw = web_thickness.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if bf <= 0 or tf <= 0 or h <= 0 or tw <= 0 or fy <= 0 or e <= 0:
        raise ValueError("all dimensions and material properties must be positive")
    k_c = min(max(4.0 / (h / tw) ** 0.5, 0.35), 0.76)
    lam = bf / (2.0 * tf)
    f_l = 0.7 * fy
    lambda_pf = 0.38 * (e / fy) ** 0.5
    lambda_rf = 0.95 * (k_c * e / f_l) ** 0.5
    if lam <= lambda_pf:
        f_cr = fy
    elif lam <= lambda_rf:
        f_cr = fy - 0.3 * fy * (lam - lambda_pf) / (lambda_rf - lambda_pf)
    else:
        f_cr = 0.9 * e * k_c / lam**2
    return Quantity(magnitude=f_cr, unit="MPa")


def aisc_minor_axis_flexural_strength(
    *,
    flange_width: Quantity,
    flange_thickness: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
    plastic_section_modulus: Quantity,
    elastic_section_modulus: Quantity,
) -> Quantity:
    """The AISC 360 §F6 minor-axis flexural strength of an I-shape or channel.

    Bending an I-shape about its weak axis — the other half of biaxial bending, or a
    channel laid flat — has no lateral-torsional buckling, so §F6 weighs only yielding
    against flange local buckling. Yielding gives M_p = F_y·Z_y but capped at 1.6·F_y·S_y
    so the plastic shape factor cannot run away (§F6.1). A noncompact flange interpolates
    linearly down to 0.7·F_y·S_y, M_n = M_p − (M_p − 0.7·F_y·S_y)·(λ − λ_pf)/(λ_rf − λ_pf),
    and a slender flange buckles elastically at M_n = 0.69·E/λ²·S_y (§F6.2), where the
    flange slenderness λ = b_f/(2·t_f) is read against λ_pf = 0.38·√(E/F_y) and
    λ_rf = 1.0·√(E/F_y). ``flange_width`` b_f, ``flange_thickness`` t_f,
    ``yield_strength`` F_y, ``elastic_modulus`` E, ``plastic_section_modulus`` Z_y, and
    ``elastic_section_modulus`` S_y are all about the minor axis. Returns M_n in kN·m.
    """
    _require(flange_width, "[length]", "flange_width")
    _require(flange_thickness, "[length]", "flange_thickness")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not isinstance(plastic_section_modulus, Quantity):
        raise ValueError(
            f"plastic_section_modulus must be a [length]**3 quantity; "
            f"got {plastic_section_modulus!r}"
        )
    if not plastic_section_modulus.has_dimension("[length]**3"):
        raise ValueError("plastic_section_modulus must be a [length]**3 quantity")
    # Through the module's own `_require`, which checks finiteness. Written as a raw
    # `has_dimension` these three functions let a NaN elastic modulus past, and
    # `min(fy*Z, 1.6*fy*S)` then deleted the §F6.1 (and local-buckling) cap: all three
    # returned the *exact same number* as the all-valid call, with a limit state silently
    # removed. S = 0 was refused and S = NaN was not, and a NaN plastic modulus propagated
    # correctly — that asymmetry is the tell.
    _require(elastic_section_modulus, "[length]**3", "elastic_section_modulus")
    bf = flange_width.to("mm").magnitude
    tf = flange_thickness.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    zy = plastic_section_modulus.to("mm**3").magnitude
    sy = elastic_section_modulus.to("mm**3").magnitude
    if bf <= 0 or tf <= 0 or fy <= 0 or e <= 0 or zy <= 0 or sy <= 0:
        raise ValueError(
            "flange_width, flange_thickness, yield_strength, elastic_modulus, and "
            "the section moduli must all be positive"
        )
    lam = bf / (2.0 * tf)
    root = (e / fy) ** 0.5
    lambda_pf = 0.38 * root
    lambda_rf = 1.0 * root
    m_p = min(fy * zy, 1.6 * fy * sy)
    if lam <= lambda_pf:
        m_n = m_p
    elif lam <= lambda_rf:
        m_n = m_p - (m_p - 0.7 * fy * sy) * (lam - lambda_pf) / (lambda_rf - lambda_pf)
    else:
        m_n = 0.69 * e / lam**2 * sy
    return Quantity(magnitude=m_n / 1.0e6, unit="kN*m")


def aisc_round_hss_shear_strength(
    *,
    gross_area: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    shear_length: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The AISC 360 §G4 shear strength V_n = F_cr·A_g/2 of a round HSS or pipe.

    A round tube shears differently from an I-shape web: only half the section is
    effective (the ``/2``), and the critical stress F_cr is the *larger* of two shell
    shear-buckling terms, F_cr = max(1.60·E/(√(L_v/D)·(D/t)^1.25), 0.78·E/(D/t)^1.5),
    but never more than the shear-yield stress 0.6·F_y. ``gross_area`` A_g,
    ``diameter`` D, ``thickness`` t (wall), ``shear_length`` L_v (the distance from the
    section of maximum shear to the section of zero shear), ``yield_strength`` F_y, and
    ``elastic_modulus`` E. A stocky wall yields (F_cr clamps to 0.6·F_y); a thin, long
    tube buckles below yield. Returns V_n in kN.
    """
    if not isinstance(gross_area, Quantity):
        raise ValueError(f"gross_area must be a [length]**2 quantity; got {gross_area!r}")
    if not gross_area.has_dimension("[length]**2"):
        raise ValueError("gross_area must be a [length]**2 quantity")
    _require(diameter, "[length]", "diameter")
    _require(thickness, "[length]", "thickness")
    _require(shear_length, "[length]", "shear_length")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    ag = gross_area.to("mm**2").magnitude
    d = diameter.to("mm").magnitude
    t = thickness.to("mm").magnitude
    lv = shear_length.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if ag <= 0 or d <= 0 or t <= 0 or lv <= 0 or fy <= 0 or e <= 0:
        raise ValueError(
            "gross_area, diameter, thickness, shear_length, yield_strength, and "
            "elastic_modulus must be positive"
        )
    dt = d / t
    f_cr_a = 1.60 * e / ((lv / d) ** 0.5 * dt**1.25)
    f_cr_b = 0.78 * e / dt**1.5
    f_cr = min(max(f_cr_a, f_cr_b), 0.6 * fy)
    v_n = f_cr * ag / 2.0
    return Quantity(magnitude=v_n / 1000.0, unit="kN")


def aisc_rectangular_hss_shear_strength(
    *,
    web_height: Quantity,
    thickness: Quantity,
    yield_strength: Quantity,
    elastic_modulus: Quantity,
    shear_buckling_coefficient: float = 5.0,
) -> Quantity:
    """The AISC 360 §G5 shear strength V_n = 0.6·F_y·A_w·C_v2 of a rectangular HSS.

    A box section shears through its two side walls, so A_w = 2·h·t, and §G5 uses the
    three-branch web shear coefficient C_v2 (not the two-branch C_v1 of an I-shape web):
    C_v2 = 1.0 while h/t ≤ 1.10·√(k_v·E/F_y); then 1.10·√(k_v·E/F_y)/(h/t) up to
    1.37·√(k_v·E/F_y); then 1.51·k_v·E/((h/t)²·F_y) beyond, where the thin wall buckles
    in the inelastic-then-elastic ranges. ``web_height`` h is the flat width of the wall
    resisting shear (conservatively the overall depth less three wall thicknesses),
    ``thickness`` t the wall thickness, ``yield_strength`` F_y, ``elastic_modulus`` E,
    and ``shear_buckling_coefficient`` k_v = 5.0 for a rectangular HSS. A stocky wall
    yields at 0.6·F_y·A_w; a slender wall buckles below it. Returns V_n in kN.
    """
    _require(web_height, "[length]", "web_height")
    _require(thickness, "[length]", "thickness")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    h = web_height.to("mm").magnitude
    t = thickness.to("mm").magnitude
    fy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if h <= 0 or t <= 0 or fy <= 0 or e <= 0:
        raise ValueError(
            "web_height, thickness, yield_strength, and elastic_modulus must be positive"
        )
    if shear_buckling_coefficient <= 0:
        raise ValueError("shear_buckling_coefficient must be positive")
    h_t = h / t
    kv = shear_buckling_coefficient
    limit_1 = 1.10 * (kv * e / fy) ** 0.5
    limit_2 = 1.37 * (kv * e / fy) ** 0.5
    if h_t <= limit_1:
        c_v2 = 1.0
    elif h_t <= limit_2:
        c_v2 = limit_1 / h_t
    else:
        c_v2 = 1.51 * kv * e / (h_t**2 * fy)
    a_w = 2.0 * h * t
    v_n = 0.6 * fy * a_w * c_v2
    return Quantity(magnitude=v_n / 1000.0, unit="kN")


def aisc_web_shear_strength(
    *,
    overall_depth: Quantity,
    web_thickness: Quantity,
    clear_web_depth: Quantity,
    web_yield: Quantity,
    elastic_modulus: Quantity,
    shear_buckling_coefficient: float = 5.34,
) -> Quantity:
    """The AISC 360 §G2.1 nominal web shear strength V_n = 0.6·F_y·A_w·C_v1.

    A beam's web carries the transverse shear, and §G checks it two ways in one formula.
    A stocky web reaches shear yielding at 0.6·F_y·A_w over the web area A_w = d·t_w; a
    slender web buckles in shear first, and the web shear coefficient C_v1 knocks the
    strength down: C_v1 = 1.0 while h/t_w ≤ 1.10·√(k_v·E/F_y), then 1.10·√(k_v·E/F_y)/(h/t_w)
    beyond it. ``overall_depth`` d, ``web_thickness`` t_w, ``clear_web_depth`` h (flat
    web between fillets), ``web_yield`` F_y, ``elastic_modulus`` E, and the plate
    ``shear_buckling_coefficient`` k_v — 5.34 for an unstiffened web (the default),
    higher with transverse stiffeners. (§G2.1(a) also grants φ_v = 1.00 to stocky rolled
    I-shapes; that is a resistance-factor bonus, not a change to this nominal strength.)
    Returns V_n in kN.
    """
    _require(overall_depth, "[length]", "overall_depth")
    _require(web_thickness, "[length]", "web_thickness")
    _require(clear_web_depth, "[length]", "clear_web_depth")
    _require(web_yield, "[pressure]", "web_yield")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    d = overall_depth.to("mm").magnitude
    tw = web_thickness.to("mm").magnitude
    h = clear_web_depth.to("mm").magnitude
    fy = web_yield.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if d <= 0 or tw <= 0 or h <= 0 or fy <= 0 or e <= 0:
        raise ValueError(
            "overall_depth, web_thickness, clear_web_depth, web_yield, and "
            "elastic_modulus must be positive"
        )
    if shear_buckling_coefficient <= 0:
        raise ValueError("shear_buckling_coefficient must be positive")
    h_tw = h / tw
    threshold = 1.10 * (shear_buckling_coefficient * e / fy) ** 0.5
    c_v1 = 1.0 if h_tw <= threshold else threshold / h_tw
    a_w = d * tw
    v_n = 0.6 * fy * a_w * c_v1
    return Quantity(magnitude=v_n / 1000.0, unit="kN")


def two_span_continuous_middle_moment(
    *,
    span_1: Quantity,
    span_2: Quantity,
    udl_1: Quantity,
    udl_2: Quantity,
) -> Quantity:
    """The interior-support moment of a two-span continuous beam (Clapeyron's three-moment).

    A beam continuous over three supports is statically indeterminate — the middle support
    is redundant — and Clapeyron's three-moment equation solves for the hogging moment it
    develops. With simply-supported ends and a uniform load on each span,
    M = −(w₁·L₁³ + w₂·L₂³)/(8·(L₁ + L₂)). ``span_1`` L₁ and ``span_2`` L₂ are the two span
    lengths and ``udl_1`` w₁, ``udl_2`` w₂ the uniform loads on them (force per length). The
    result is negative (hogging) — the top fibre over the support is in tension, which is
    where a continuous beam is checked and where its reinforcement or its heaviest section
    goes. For equal spans and loads it reduces to the classic −w·L²/8, larger in magnitude
    than either span's own w·L²/8 sagging peak. Returns the moment in kN·m.
    """
    _require(span_1, "[length]", "span_1")
    _require(span_2, "[length]", "span_2")
    if not isinstance(udl_1, Quantity):
        raise ValueError(f"udl_1 must be a [force] / [length] quantity; got {udl_1!r}")
    if not udl_1.has_dimension("[force] / [length]"):
        raise ValueError(f"udl_1 must be a force-per-length quantity; got {udl_1.dimensionality}")
    if not isinstance(udl_2, Quantity):
        raise ValueError(f"udl_2 must be a [force] / [length] quantity; got {udl_2!r}")
    if not udl_2.has_dimension("[force] / [length]"):
        raise ValueError(f"udl_2 must be a force-per-length quantity; got {udl_2.dimensionality}")
    l1 = span_1.to("m").magnitude
    l2 = span_2.to("m").magnitude
    w1 = udl_1.to("kN/m").magnitude
    w2 = udl_2.to("kN/m").magnitude
    if l1 <= 0 or l2 <= 0:
        raise ValueError("span_1 and span_2 must be positive")
    moment = -(w1 * l1**3 + w2 * l2**3) / (8.0 * (l1 + l2))
    return Quantity(magnitude=moment, unit="kN*m")


def two_span_continuous_interior_reaction(
    *,
    span_1: Quantity,
    span_2: Quantity,
    udl_1: Quantity,
    udl_2: Quantity,
) -> Quantity:
    """The interior-support reaction of a two-span continuous beam under uniform load.

    Continuity draws load *toward* the interior support: the hogging moment there
    (:func:`two_span_continuous_middle_moment`) reduces the end reactions and piles the
    difference onto the middle, so the interior support carries more than a pair of simple
    beams would. From the middle moment M and statics, R_int = w₁·L₁ + w₂·L₂ − (w₁·L₁/2 +
    M/L₁) − (w₂·L₂/2 + M/L₂). ``span_1`` L₁, ``span_2`` L₂, ``udl_1`` w₁, and ``udl_2`` w₂ as
    in the moment function. For equal spans and loads it is the classic 1.25·w·L — 25% more
    than the w·L a simple span puts on the support — which is why the interior column or
    bearing of a continuous beam is the one that governs. Returns the reaction in kN.
    """
    moment = (
        two_span_continuous_middle_moment(span_1=span_1, span_2=span_2, udl_1=udl_1, udl_2=udl_2)
        .to("kN*m")
        .magnitude
    )
    l1 = span_1.to("m").magnitude
    l2 = span_2.to("m").magnitude
    w1 = udl_1.to("kN/m").magnitude
    w2 = udl_2.to("kN/m").magnitude
    end_1 = w1 * l1 / 2.0 + moment / l1
    end_2 = w2 * l2 / 2.0 + moment / l2
    interior = w1 * l1 + w2 * l2 - end_1 - end_2
    return Quantity(magnitude=interior, unit="kN")


def shear_flow(
    *,
    shear_force: Quantity,
    first_moment_of_area: Quantity,
    second_moment_of_area: Quantity,
) -> Quantity:
    """The longitudinal shear flow q = V·Q/I at a cut in a built-up beam.

    Where two parts of a beam are joined — a plate welded to a flange, boards
    nailed into a box — the fasteners carry the shear that flows between them along
    the beam. That flow (force per unit length) is q = V·Q/I: ``shear_force`` V is
    the transverse shear at the section, ``first_moment_of_area`` Q the first moment
    (A·ȳ) of the joined area about the neutral axis, and ``second_moment_of_area`` I
    the whole section's second moment. Divide a fastener's shear capacity by q for
    its maximum spacing (:func:`fastener_spacing_for_shear_flow`). V must be a
    force, Q a length³, and I a length⁴ (both positive). Returns the shear flow in
    N/mm.
    """
    _require(shear_force, "[force]", "shear_force")
    if not isinstance(first_moment_of_area, Quantity):
        raise ValueError(
            f"first_moment_of_area must be a [length]**3 quantity; got {first_moment_of_area!r}"
        )
    if not first_moment_of_area.has_dimension("[length]**3"):
        raise ValueError(
            f"first_moment_of_area must be a [length]**3 quantity; got "
            f"{first_moment_of_area.dimensionality} ({first_moment_of_area})"
        )
    if not isinstance(second_moment_of_area, Quantity):
        raise ValueError(
            f"second_moment_of_area must be a [length]**4 quantity; got {second_moment_of_area!r}"
        )
    if not second_moment_of_area.has_dimension("[length]**4"):
        raise ValueError(
            f"second_moment_of_area must be a [length]**4 quantity; got "
            f"{second_moment_of_area.dimensionality} ({second_moment_of_area})"
        )
    if second_moment_of_area.to("mm**4").magnitude <= 0:
        raise ValueError(f"second_moment_of_area must be positive; got {second_moment_of_area}")
    q = shear_force.pint * first_moment_of_area.pint / second_moment_of_area.pint
    return _as_quantity(q, "N/mm")


def fastener_spacing_for_shear_flow(
    *,
    fastener_capacity: Quantity,
    shear_flow: Quantity,
) -> Quantity:
    """The maximum fastener spacing s = F/q along a built-up beam.

    A connector carrying shear capacity ``fastener_capacity`` F, spaced s apart,
    resists a shear flow F/s; setting that equal to the applied ``shear_flow`` q
    gives the largest spacing that keeps the joint from shearing, s = F/q. For a
    double row (two fasteners per station) pass twice the single-fastener capacity.
    F must be a force and q a force-per-length (positive). Returns the spacing in
    mm.
    """
    _require(fastener_capacity, "[force]", "fastener_capacity")
    if not isinstance(shear_flow, Quantity):
        raise ValueError(f"shear_flow must be a [force] / [length] quantity; got {shear_flow!r}")
    if not shear_flow.has_dimension("[force] / [length]"):
        raise ValueError(
            f"shear_flow must be a [force]/[length] quantity; got "
            f"{shear_flow.dimensionality} ({shear_flow})"
        )
    if shear_flow.to("N/mm").magnitude <= 0:
        raise ValueError(f"shear_flow must be positive; got {shear_flow}")
    spacing = fastener_capacity.pint / shear_flow.pint
    return _as_quantity(spacing, "mm")


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
        # Widened to keep the two figures apart, as `beam_deflection_scorecard` above
        # already does. At three fixed places a 15.0004 mm deflection against a 15 mm limit
        # printed "deflection 15.000 mm vs limit 15.000 mm" on a FAIL — the verdict and the
        # numbers beside it saying opposite things, on one of the two checks the README's
        # own quickstart shows.
        detail=(
            f"deflection {measured:.{decimals_distinguishing(measured, allowed, minimum=3)}f} "
            f"mm vs limit {allowed:.{decimals_distinguishing(measured, allowed, minimum=3)}f} mm"
        ),
    )


def span_deflection_limit(*, span: Quantity, ratio: float) -> Quantity:
    """The serviceability deflection limit L/``ratio`` for a member of ``span`` L.

    Deflection limits are conventionally a fraction of the span: the common
    building ratios are L/360 (floors carrying brittle plaster or the classic live
    load), L/240 (general floors), and L/180 (roofs) — a larger ratio is a tighter
    limit. This returns the allowable deflection to hand to
    :func:`deflection_scorecard` as its ``limit``. ``span`` must be a positive
    length and ``ratio`` positive. Returns the limit in mm.
    """
    _require(span, "[length]", "span")
    length = span.to("mm").magnitude
    if length <= 0:
        raise ValueError(f"span must be positive; got {span}")
    if ratio <= 0:
        raise ValueError(f"ratio must be positive; got {ratio}")
    return Quantity(magnitude=length / ratio, unit="mm")


class BeamBendingResult(BaseModel):
    """The result of a closed-form beam bending check.

    ``max_moment`` is the peak bending moment the load case makes — the number a
    reviewer checks first and the one that carries into a section-sizing or a
    connection design. ``max_bending_stress`` is the stress it makes on the section
    (σ = M·c/I); ``max_deflection`` is the peak deflection (at the free end for a
    cantilever, at mid-span for a simply-supported beam). All three are screening
    estimates for a prismatic linear-elastic beam under small deflections.
    """

    model_config = ConfigDict(frozen=True)

    max_moment: Quantity
    max_bending_stress: Quantity
    max_deflection: Quantity
    # The closed-form deflection expression for this case, when it has one a
    # reviewer can follow in a line — the full-span standard cases. Off-default
    # geometry (offset loads, partial patches, load pairs) solves for the peak
    # position numerically or through a series, so it declares no formula rather
    # than a tidy one that is not what was computed.
    deflection_formula: str | None = None

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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
        deflection_formula="δ = F·L³/(3·E·I)",
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
        deflection_formula="δ = w·L⁴/(8·E·I)",
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(m0, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def cantilever_offset_moment(
    *,
    moment: Quantity,
    load_position: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The cantilever with a couple applied short of the tip (Roark).

    A prismatic beam fixed at one end and free at the other, carrying an
    applied ``moment`` M₀ (a couple in the bending plane) at ``load_position``
    a measured from the fixed end, 0 < a ≤ length — a bracket or hub welded
    mid-span rather than at the tip. The wall reacts the couple directly (no
    force anywhere), so the segment from the wall to the couple is in pure
    bending at M₀ and the overhang beyond is straight, riding on the loaded
    segment's end slope. Generalizes :func:`cantilever_end_moment`, which
    this matches exactly at a = L.

    Returns the peak bending stress (σ = M₀·c/I, uniform over [0, a]) and the
    tip deflection δ = M₀·a·(2L − a)/(2·E·I) — the loaded segment's own
    M₀·a²/2EI plus the overhang's rigid rotation. Every argument is
    dimension-checked; verified against an independent numeric integration of
    the beam ODE.
    """
    _require(moment, "[force] * [length]", "moment")
    _require(load_position, "[length]", "load_position")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    m0 = moment.pint
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

    stress = m0 * c / inertia
    deflection = m0 * position * (2 * length_p - position) / (2 * e * inertia)
    return BeamBendingResult(
        max_moment=_as_quantity(m0, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
        deflection_formula="δ = F·L³/(48·E·I)",
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
        deflection_formula="δ = 5·w·L⁴/(384·E·I)",
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
    if distributed_load.magnitude == 0:
        raise ValueError(
            "distributed_load is zero: the peak moment of a partial uniform load is "
            "located by R/w, which has no location on an unloaded span. An unloaded bay "
            "in a pattern-loading sweep is a span with nothing to evaluate, not a span "
            "at zero stress — every other load case in this module returns zeros for it, "
            "and this one divided by zero instead."
        )
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(m0, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def simply_supported_offset_moment(
    *,
    moment: Quantity,
    load_position: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The simply-supported beam with a couple applied inside the span (Roark).

    A prismatic beam simply supported over a span ``length``, carrying an
    applied ``moment`` M₀ (a couple in the bending plane) at ``load_position``
    a from one support, strictly inside the span — a gearbox or brake hub
    clamped mid-span on a shaft, a bracket that hands its beam a couple. The
    reactions form the countering couple M₀/L, so the bending moment ramps
    from zero at each support toward the couple and JUMPS by M₀ across it:
    the peak |M| = M₀·max(a, b)/L sits just on the longer-segment side
    (b = L − a). A mid-span couple therefore stresses the beam only half as
    hard as the same couple at a support (M₀/2 vs M₀), the reverse of a point
    load's preference; the ends of that range are
    :func:`simply_supported_end_moment`.

    Returns the peak bending stress (σ = M₀·max(a, b)·c/(L·I)) and the true
    maximum deflection of the two-lobed elastic curve
    EI·v = −M₀·x³/(6L) + M₀·⟨x−a⟩²/2 + C₁·x, C₁ = M₀·(L² − 3b²)/(6L) — each
    lobe's stationary point is a closed-form quadratic root and the larger
    |v| governs. Every argument is dimension-checked; verified against an
    independent numeric integration of the beam ODE, and exactly symmetric
    under a ↔ b.
    """
    _require(moment, "[force] * [length]", "moment")
    _require(load_position, "[length]", "load_position")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    m0 = moment.pint
    length_p = length.pint
    position = load_position.pint.to(length_p.units)
    if not 0 < position.magnitude < length_p.magnitude:
        raise ValueError(
            f"load_position must lie strictly inside the span (0, {length}); got {load_position}"
        )
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    a = position
    b = length_p - a
    stress = m0 * max(a, b) / length_p * c / inertia

    c1 = m0 * (length_p**2 - 3 * b**2) / (6 * length_p)

    def _v(x, loaded: bool):
        out = -m0 * x**3 / (6 * length_p) + c1 * x
        if loaded:
            out = out + m0 * (x - a) ** 2 / 2
        return out

    candidates = []
    left_sq = (length_p**2 - 3 * b**2) / 3
    if left_sq.magnitude > 0 and (x1 := left_sq**0.5) < a:
        candidates.append(abs(_v(x1, loaded=False)))
    right_rad = 2 * length_p * b - b**2 - 2 * length_p**2 / 3
    if right_rad.magnitude >= 0 and (x2 := length_p - right_rad**0.5) > a:
        candidates.append(abs(_v(x2, loaded=True)))
    deflection = max(candidates) / (e * inertia)
    return BeamBendingResult(
        max_moment=_as_quantity(m0 * max(a, b) / length_p, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
        deflection_formula="δ = F·L³/(48·√5·E·I)",
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
        deflection_formula="δ = w·L⁴/(185·E·I)",
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(m0, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def overhang_tip_load(
    *,
    force: Quantity,
    back_span: Quantity,
    overhang: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The overhanging beam with a point load at its free tip (Roark).

    A prismatic beam simply supported over a ``back_span`` L whose section
    continues ``overhang`` c past one support, carrying a transverse ``force``
    at the free tip — a loading-dock edge, a crane-runway end, a balcony
    joist. The tip load hogs the beam over the inner support (|M|max = F·c
    there, falling to zero at both free ends) and levers the back span UPWARD.

    Returns the peak bending stress at the inner support (σ = F·c·cᶠ/I) and
    the larger of the two deflection extremes — the tip drop
    δ = F·c²·(L + c)/(3·E·I) or the back-span uplift F·c·L²/(9·√3·E·I) at
    L/√3 from the far support (the uplift governs for short overhangs,
    c ≲ 0.16·L). Every argument is dimension-checked; verified against an
    independent numeric integration of the beam ODE.
    """
    _require(force, "[force]", "force")
    _require(back_span, "[length]", "back_span")
    _require(overhang, "[length]", "overhang")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    span = back_span.pint
    c_len = overhang.pint.to(span.units)
    if c_len.magnitude <= 0 or span.magnitude <= 0:
        raise ValueError(f"back_span ({back_span}) and overhang ({overhang}) must be positive")
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    stress = f * c_len * c / inertia
    tip = f * c_len**2 * (span + c_len) / (3 * e * inertia)
    uplift = f * c_len * span**2 / (9 * sqrt(3) * e * inertia)
    deflection = max(tip, uplift)
    return BeamBendingResult(
        max_moment=_as_quantity(f * c_len, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def overhang_uniform_load(
    *,
    distributed_load: Quantity,
    back_span: Quantity,
    overhang: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The overhanging beam uniformly loaded over its overhang (Roark).

    A prismatic beam simply supported over a ``back_span`` L whose section
    continues ``overhang`` c past one support, carrying a uniform
    ``distributed_load`` w (force per unit length) on the OVERHANG only —
    pallets parked on a dock edge, snow on a canopy stub. The overhang load
    hogs the inner support (|M|max = w·c²/2) and levers the back span upward.

    Returns the peak bending stress at the inner support (σ = w·c²·cᶠ/(2·I))
    and the larger of the tip drop δ = w·c³·(4L + 3c)/(24·E·I) or the
    back-span uplift (w·c²/2)·L²/(9·√3·E·I) at L/√3 from the far support.
    Every argument is dimension-checked; verified against an independent
    numeric integration of the beam ODE.
    """
    _require(distributed_load, "[force] / [length]", "distributed_load")
    _require(back_span, "[length]", "back_span")
    _require(overhang, "[length]", "overhang")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    w = distributed_load.pint
    span = back_span.pint
    c_len = overhang.pint.to(span.units)
    if c_len.magnitude <= 0 or span.magnitude <= 0:
        raise ValueError(f"back_span ({back_span}) and overhang ({overhang}) must be positive")
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = w * c_len**2 / 2
    stress = moment * c / inertia
    tip = w * c_len**3 * (4 * span + 3 * c_len) / (24 * e * inertia)
    uplift = moment * span**2 / (9 * sqrt(3) * e * inertia)
    deflection = max(tip, uplift)
    return BeamBendingResult(
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
        deflection_formula="δ = F·L³/(192·E·I)",
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
        deflection_formula="δ = w·L⁴/(384·E·I)",
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
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
        max_moment=_as_quantity(moment, "N*m"),
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )
