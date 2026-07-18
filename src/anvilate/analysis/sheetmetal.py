"""T1 analytical sheet-metal bending checks (closed-form flat-pattern geometry).

Bending is the most common sheet-metal operation, and the flat blank a bent part
needs is not the sum of its finished flanges — the metal on the outside of a bend
stretches and the inside compresses, so the neutral fibre (which neither stretches
nor compresses) sits a fraction ``K`` of the thickness in from the inside surface.
Its arc length through the bend is the **bend allowance**

    BA = (π/180)·β·(R + K·t),

for a bend angle ``β`` (degrees, the angle the sheet turns *through* — 90° for a
right-angle bend), inner radius ``R``, thickness ``t``, and K-factor ``K`` (≈0.33
for a sharp bend, ≈0.5 for a generous one). The flat length is the tangent-line
flange lengths plus one BA per bend; equivalently, working from the outside mould
lines, it is the flange sum minus one **bend deduction** BD = 2·OSSB − BA per bend,
where the outside setback OSSB = (R + t)·tan(β/2) is the mould-line-to-tangent
offset. These two flat-length routes agree exactly (:func:`flat_pattern_length`
carries the tangent-line convention).

The module also screens two limits: the **minimum bend radius** R_min = t·(50/r − 1)
a material of tensile reduction-of-area ``r`` (%) can take without cracking the
outer fibre (a ductile r = 50 % bends dead sharp; a brittle r = 10 % needs 4·t of
radius), and the **air-bending force** F = k·σ_u·L·t²/V a press brake must supply
over a die opening ``V`` (k ≈ 1.33 for a wiping air bend).

Bend angles are plain-float degrees values (the units layer carries no angles);
every length, strength, and force is a dimension-checked :class:`~anvilate.units.Quantity`.
"""

from __future__ import annotations

from math import radians, tan

from ..units import Quantity

__all__ = [
    "neutral_axis_radius",
    "bend_allowance",
    "outside_setback",
    "bend_deduction",
    "flat_pattern_length",
    "minimum_bend_radius",
    "air_bending_force",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _bend_geometry(inner_radius: Quantity, thickness: Quantity) -> tuple[float, float]:
    """Validate and return (R, t) in mm for a sheet-metal bend, both positive."""
    _require(inner_radius, "[length]", "inner_radius")
    _require(thickness, "[length]", "thickness")
    r = inner_radius.to("mm").magnitude
    t = thickness.to("mm").magnitude
    if r < 0 or t <= 0:
        raise ValueError("inner_radius must be non-negative and thickness positive")
    return r, t


def _check_bend_angle(bend_angle: float) -> float:
    if not 0 < bend_angle < 180:
        raise ValueError(f"bend_angle must be in (0, 180) degrees; got {bend_angle}")
    return bend_angle


def neutral_axis_radius(
    *, inner_radius: Quantity, thickness: Quantity, k_factor: float
) -> Quantity:
    """The neutral-fibre radius R_n = R + K·t of a bend.

    The neutral fibre neither stretches nor compresses; it lies a fraction ``k_factor``
    K of the ``thickness`` t out from the ``inner_radius`` R, so its radius is
    R_n = R + K·t and its arc length is the bend allowance. K runs 0 (inner surface)
    to 0.5 (mid-thickness); a tighter bend pushes it inward (smaller K). Returns R_n
    in mm.
    """
    r, t = _bend_geometry(inner_radius, thickness)
    if not 0 <= k_factor <= 0.5:
        raise ValueError(f"k_factor must be in [0, 0.5]; got {k_factor}")
    return Quantity(magnitude=r + k_factor * t, unit="mm")


def bend_allowance(
    *, bend_angle: float, inner_radius: Quantity, thickness: Quantity, k_factor: float
) -> Quantity:
    """The bend allowance BA = (π/180)·β·(R + K·t), the neutral-fibre arc length.

    The length of material consumed by the bend itself, measured along the neutral
    fibre, which is what a flat pattern adds between the tangent lines. ``bend_angle``
    β is the angle the sheet turns through in degrees (90° for a right angle),
    ``inner_radius`` R and ``thickness`` t the bend section, and ``k_factor`` K the
    neutral-axis position (see :func:`neutral_axis_radius`). Returns BA in mm.
    """
    beta = _check_bend_angle(bend_angle)
    r_n = neutral_axis_radius(
        inner_radius=inner_radius, thickness=thickness, k_factor=k_factor
    ).magnitude
    return Quantity(magnitude=radians(beta) * r_n, unit="mm")


def outside_setback(*, bend_angle: float, inner_radius: Quantity, thickness: Quantity) -> Quantity:
    """The outside setback OSSB = (R + t)·tan(β/2), mould-line to tangent line.

    The distance along a flange from the outside mould line (where the two outside
    faces would meet if extended) back to the bend's tangent line. ``bend_angle`` β
    (degrees), ``inner_radius`` R, and ``thickness`` t describe the bend. Returns
    OSSB in mm.
    """
    beta = _check_bend_angle(bend_angle)
    r, t = _bend_geometry(inner_radius, thickness)
    return Quantity(magnitude=(r + t) * tan(radians(beta) / 2.0), unit="mm")


def bend_deduction(
    *, bend_angle: float, inner_radius: Quantity, thickness: Quantity, k_factor: float
) -> Quantity:
    """The bend deduction BD = 2·OSSB − BA, subtracted from the outside flanges.

    Working from the outside mould-line flange lengths, the flat blank is their sum
    minus one bend deduction per bend: BD = 2·(R + t)·tan(β/2) − BA. It is the
    outside-dimension counterpart of the bend allowance and is what a CAM flat
    pattern uses when flanges are dimensioned to the outside. ``bend_angle`` β
    (degrees), ``inner_radius`` R, ``thickness`` t, and ``k_factor`` K describe the
    bend. Returns BD in mm (positive for the usual ductile bend).
    """
    ossb = outside_setback(
        bend_angle=bend_angle, inner_radius=inner_radius, thickness=thickness
    ).magnitude
    ba = bend_allowance(
        bend_angle=bend_angle, inner_radius=inner_radius, thickness=thickness, k_factor=k_factor
    ).magnitude
    return Quantity(magnitude=2.0 * ossb - ba, unit="mm")


def flat_pattern_length(
    *,
    flange_lengths: list[Quantity] | tuple[Quantity, ...],
    bend_angle: float,
    inner_radius: Quantity,
    thickness: Quantity,
    k_factor: float,
) -> Quantity:
    """The developed (flat) blank length of a strip bent by a series of equal bends.

    Each flange is measured to its tangent lines (the start/end of the straight
    sections), and every bend contributes one bend allowance, so the flat length is
    Σ(flanges) + (n_bends)·BA, with n_bends = n_flanges − 1. All bends share the same
    ``bend_angle`` β (degrees), ``inner_radius`` R, ``thickness`` t, and ``k_factor``
    K. Give at least two flanges. Returns the flat length in mm.

    (Dimensioning the flanges to the outside mould lines instead gives the same
    result as Σ(outside flanges) − n_bends·:func:`bend_deduction`.)
    """
    if len(flange_lengths) < 2:
        raise ValueError("flat_pattern_length needs at least two flanges (one bend)")
    total = 0.0
    for i, flange in enumerate(flange_lengths):
        _require(flange, "[length]", f"flange_lengths[{i}]")
        length = flange.to("mm").magnitude
        if length <= 0:
            raise ValueError(f"flange_lengths[{i}] must be positive; got {flange}")
        total += length
    ba = bend_allowance(
        bend_angle=bend_angle, inner_radius=inner_radius, thickness=thickness, k_factor=k_factor
    ).magnitude
    return Quantity(magnitude=total + (len(flange_lengths) - 1) * ba, unit="mm")


def minimum_bend_radius(*, thickness: Quantity, reduction_of_area_percent: float) -> Quantity:
    """The minimum inner bend radius R_min = t·(50/r − 1) that avoids outer-fibre cracking.

    A tighter bend stretches the outer fibre more; past the material's ductility it
    cracks. The empirical screen (Kalpakjian) ties the minimum radius to the tensile
    ``reduction_of_area_percent`` r: R_min = t·(50/r − 1). A very ductile metal
    (r = 50 %) bends dead sharp (R_min = 0); a marginal one (r = 10 %) needs 4·t.
    ``thickness`` t must be positive and r in (0, 50] %. Returns R_min in mm
    (clamped at 0 for r ≥ 50 %).
    """
    _require(thickness, "[length]", "thickness")
    t = thickness.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"thickness must be positive; got {thickness}")
    if not 0 < reduction_of_area_percent <= 100:
        raise ValueError(
            f"reduction_of_area_percent must be in (0, 100]; got {reduction_of_area_percent}"
        )
    r_min = t * (50.0 / reduction_of_area_percent - 1.0)
    return Quantity(magnitude=max(0.0, r_min), unit="mm")


def air_bending_force(
    *,
    ultimate_tensile_strength: Quantity,
    bend_length: Quantity,
    thickness: Quantity,
    die_opening: Quantity,
    force_coefficient: float = 1.33,
) -> Quantity:
    """The press-brake force F = k·σ_u·L·t²/V an air (V-die) bend requires.

    In air bending the sheet spans a V-die of width ``die_opening`` V and is pressed
    to depth by the punch; the tonnage scales with the material's
    ``ultimate_tensile_strength`` σ_u, the ``bend_length`` L, the square of the
    ``thickness`` t, and inversely with V: F = k·σ_u·L·t²/V. The ``force_coefficient``
    k (default 1.33 for a wiping air bend) folds in the die geometry — supply the
    press or die maker's value if it differs. All quantities must be positive.
    Returns the force in kN.
    """
    _require(ultimate_tensile_strength, "[pressure]", "ultimate_tensile_strength")
    _require(bend_length, "[length]", "bend_length")
    _require(thickness, "[length]", "thickness")
    _require(die_opening, "[length]", "die_opening")
    su = ultimate_tensile_strength.to("MPa").magnitude
    length = bend_length.to("mm").magnitude
    t = thickness.to("mm").magnitude
    v = die_opening.to("mm").magnitude
    if su <= 0 or length <= 0 or t <= 0 or v <= 0:
        raise ValueError("strength, bend_length, thickness, and die_opening must be positive")
    if force_coefficient <= 0:
        raise ValueError(f"force_coefficient must be positive; got {force_coefficient}")
    force_n = force_coefficient * su * length * t**2 / v
    return Quantity(magnitude=force_n / 1000.0, unit="kN")
