"""T1 analytical wire-rope-over-sheave checks (closed-form).

A wire rope running over a sheave or drum is loaded twice: by the tension it carries and by
the bending forced on every wire as the rope conforms to the sheave's curvature. Bending a
wire of diameter ``d_w`` around a sheave of diameter ``D`` imposes an outer-fibre strain of
about d_w/D (the beam-curvature relation σ = E·c/ρ with c = d_w/2 and ρ = D/2), so the
bending stress in the wire is

    σ_b = E_r · d_w / D,

with ``E_r`` the *rope's* effective modulus of elasticity — well below solid steel's,
because a rope is a helical assembly of strands (about 83 GPa / 12 Mpsi for a typical
steel-core rope; read it from the rope's datasheet). The same relation inverted gives the
smallest sheave a bending-stress allowable permits, D_min = E_r·d_w/σ_allow — why every
rope catalogue lists a minimum sheave-to-rope ratio.

Multiplying the bending stress by the rope's metal cross-section ``A_m`` (the summed wire
areas, another datasheet number) expresses the bending as an *equivalent tension*
F_b = σ_b·A_m — the standard way (Shigley) to fold sheave bending into the rope's
strength margin: the rope is screened against F + F_b, not F alone, and on a small sheave
F_b can rival the payload itself.

The rope also bears on the sheave groove. On the projected area (rope diameter ``d`` times
the wrapped diameter ``D``), the capstan normal load 2F/D per unit arc spread over the
rope's width gives the bearing pressure

    p = 2·F / (d · D),

screened against the tabulated allowable for the rope construction and sheave material —
past it, the groove peens and the rope's wires fatigue from the outside in.

All four forms are exact closed-form mechanics; the rope properties (``E_r``, ``A_m``,
allowable stress and pressure) are the caller's datasheet or handbook values. Inputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity, require_finite

__all__ = [
    "wire_rope_bending_stress",
    "minimum_sheave_diameter_for_bending_stress",
    "wire_rope_equivalent_bending_load",
    "wire_rope_sheave_pressure",
]


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


def _positive_mm(value: Quantity, name: str) -> float:
    _require(value, "[length]", name)
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def _positive_mpa(value: Quantity, name: str) -> float:
    _require(value, "[pressure]", name)
    magnitude = value.to("MPa").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def wire_rope_bending_stress(
    *,
    wire_diameter: Quantity,
    sheave_diameter: Quantity,
    rope_modulus: Quantity,
) -> Quantity:
    """The bending stress σ_b = E_r·d_w/D in a rope's wires as it wraps a sheave.

    ``wire_diameter`` d_w is the rope's outer-wire diameter and ``sheave_diameter`` D the
    sheave or drum tread diameter, both from the rope and reeving geometry;
    ``rope_modulus`` E_r is the rope's effective modulus from its datasheet (≈ 83 GPa for
    a typical steel rope — not solid steel's 200 GPa). A smaller sheave bends every wire
    harder; the stress is inverse in D. The wire must be smaller than the sheave.
    Returns the bending stress in MPa.
    """
    d_w = _positive_mm(wire_diameter, "wire_diameter")
    d_sheave = _positive_mm(sheave_diameter, "sheave_diameter")
    e_r = _positive_mpa(rope_modulus, "rope_modulus")
    if d_w >= d_sheave:
        raise ValueError(
            f"wire_diameter ({wire_diameter}) must be below the sheave_diameter ({sheave_diameter})"
        )
    return Quantity(magnitude=e_r * d_w / d_sheave, unit="MPa")


def minimum_sheave_diameter_for_bending_stress(
    *,
    wire_diameter: Quantity,
    rope_modulus: Quantity,
    allowable_bending_stress: Quantity,
) -> Quantity:
    """The smallest sheave D_min = E_r·d_w/σ_allow a bending-stress allowable permits.

    The sizing inverse of :func:`wire_rope_bending_stress`: given the rope's outer
    ``wire_diameter`` d_w and effective ``rope_modulus`` E_r, the sheave that keeps the
    wire bending stress at the caller's ``allowable_bending_stress`` — a tighter
    allowable (a fatigue-rated reeving) calls for a larger sheave. This is the mechanics
    behind the minimum sheave-to-rope-diameter ratios rope catalogues tabulate.
    Returns the minimum sheave tread diameter in mm.
    """
    d_w = _positive_mm(wire_diameter, "wire_diameter")
    e_r = _positive_mpa(rope_modulus, "rope_modulus")
    allowable = _positive_mpa(allowable_bending_stress, "allowable_bending_stress")
    return Quantity(magnitude=e_r * d_w / allowable, unit="mm")


def wire_rope_equivalent_bending_load(
    *,
    wire_diameter: Quantity,
    sheave_diameter: Quantity,
    rope_modulus: Quantity,
    metal_area: Quantity,
) -> Quantity:
    """The equivalent tension F_b = E_r·d_w·A_m/D a sheave's bending adds to a rope.

    The wire bending stress from wrapping the sheave, spread over the rope's metal
    cross-section ``metal_area`` A_m (the summed wire areas from the datasheet — well
    below the circumscribed circle's area), expressed as the extra tension that would
    stress the rope equally. Screen the rope's strength against the working tension
    *plus* this load: on a small sheave it can rival the payload itself, which is why a
    rope that is amply strong in a straight pull still fails over an undersized sheave.
    Returns the equivalent bending load in N.
    """
    stress = wire_rope_bending_stress(
        wire_diameter=wire_diameter,
        sheave_diameter=sheave_diameter,
        rope_modulus=rope_modulus,
    )
    _require(metal_area, "[area]", "metal_area")
    a_m = metal_area.to("mm**2").magnitude
    if a_m <= 0:
        raise ValueError(f"metal_area must be positive; got {metal_area}")
    return Quantity(magnitude=stress.to("MPa").magnitude * a_m, unit="N")


def wire_rope_sheave_pressure(
    *,
    tension: Quantity,
    rope_diameter: Quantity,
    sheave_diameter: Quantity,
) -> Quantity:
    """The rope-on-sheave bearing pressure p = 2F/(d·D) on the projected area.

    The capstan normal load of a rope under ``tension`` F wrapped on a sheave of tread
    diameter ``sheave_diameter`` D, spread over the projected bearing area (the
    ``rope_diameter`` d times D). Screened against the tabulated allowable pressure for
    the rope construction and sheave material — exceeding it peens the groove and
    fatigues the rope's outer wires. The rope must be smaller than the sheave.
    Returns the bearing pressure in MPa.
    """
    _require(tension, "[force]", "tension")
    force = tension.to("N").magnitude
    if force <= 0:
        raise ValueError(f"tension must be positive; got {tension}")
    d_rope = _positive_mm(rope_diameter, "rope_diameter")
    d_sheave = _positive_mm(sheave_diameter, "sheave_diameter")
    if d_rope >= d_sheave:
        raise ValueError(
            f"rope_diameter ({rope_diameter}) must be below the sheave_diameter ({sheave_diameter})"
        )
    return Quantity(magnitude=2 * force / (d_rope * d_sheave), unit="MPa")
