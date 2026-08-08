"""T1 analytical shear-spinning (metal-spinning) checks (closed-form).

Shear spinning forms a cone or dished part by pressing a roller against a flat blank that spins on a
mandrel, flowing the metal down over the mandrel's face. Unlike deep drawing, the outer diameter of
the blank does not change — the metal is displaced entirely into the wall, which thins as it is
swept down the cone. It is a distinct member of the metal-forming family
(:mod:`anvilate.analysis.forging`, :mod:`anvilate.analysis.rolling`,
:mod:`anvilate.analysis.extrusion`), governed by one strikingly simple geometric law.

The sine law fixes the wall thickness from the cone angle alone: t_f = t₀·sin α, where t₀ is the
blank thickness and α is the half-angle of the cone measured from its axis. A shallow, near-flat
cone (α → 90°) barely thins the wall, while a steep cone (small α) thins it drastically — a 30°
half-angle halves the wall in a single pass. That gives the reduction r = 1 − sin α directly, and
inverting the law gives the half-angle a target wall needs, α = arcsin(t_f/t₀). The catch is
spinnability: too steep a cone demands more reduction than the metal can take in one pass without
tearing, so severe cones are shear-spun in stages.
"""

from __future__ import annotations

from math import asin, degrees, radians, sin

from ..units import Quantity

__all__ = [
    "shear_spinning_half_angle_for_thickness",
    "shear_spinning_reduction",
    "shear_spinning_wall_thickness",
]


def shear_spinning_wall_thickness(*, blank_thickness: Quantity, half_cone_angle: float) -> Quantity:
    """The spun wall thickness by the sine law, t_f = t₀·sin α.

    The wall thickness a shear-spun cone is left with: the ``blank_thickness`` t₀ times the sine of
    the ``half_cone_angle`` α (degrees, measured from the cone axis), t_f = t₀·sin α. Because the
    diameter is unchanged, all the deformation goes into thinning the wall, and the thinner the wall
    the steeper the cone. A near-flat cone (α → 90°) barely thins; a steep one thins severely.
    Returns the wall thickness in mm.
    """
    _check(blank_thickness, "[length]", "blank_thickness")
    t0 = blank_thickness.to("mm").magnitude
    if t0 <= 0:
        raise ValueError("blank_thickness must be positive")
    if not 0.0 < half_cone_angle < 90.0:
        raise ValueError("half_cone_angle must be in (0, 90) degrees")
    return Quantity(magnitude=t0 * sin(radians(half_cone_angle)), unit="mm")


def shear_spinning_reduction(*, half_cone_angle: float) -> float:
    """The thickness reduction, r = 1 − sin α.

    The fraction of wall thickness removed in a shear-spinning pass, straight from the sine law:
    with the wall thinned to t₀·sin α, the reduction is r = (t₀ − t_f)/t₀ = 1 − sin α, from the
    ``half_cone_angle`` α (degrees). A steep cone (small α) demands a large reduction — a 30° cone
    takes 50%, a 15° cone nearly 74% — and past what the metal can take in one pass it tears, so
    severe cones are spun in stages. Returns the thickness reduction as a fraction (0 to 1).
    """
    if not 0.0 < half_cone_angle < 90.0:
        raise ValueError("half_cone_angle must be in (0, 90) degrees")
    return 1.0 - sin(radians(half_cone_angle))


def shear_spinning_half_angle_for_thickness(
    *, blank_thickness: Quantity, final_thickness: Quantity
) -> float:
    """The cone half-angle for a target wall, α = arcsin(t_f/t₀).

    Inverting the sine law (:func:`shear_spinning_wall_thickness`) for angle: the cone half-angle
    that spins a ``blank_thickness`` t₀ down to a ``final_thickness`` t_f, α = arcsin(t_f/t₀) in
    degrees. It is how a spinning setup is chosen from the part's wall spec — a thinner target wall
    forces a steeper cone, and if the required angle is steeper than one pass allows, the part is
    spun in stages. Returns the half-cone angle in degrees.
    """
    _check(blank_thickness, "[length]", "blank_thickness")
    _check(final_thickness, "[length]", "final_thickness")
    t0 = blank_thickness.to("mm").magnitude
    tf = final_thickness.to("mm").magnitude
    if t0 <= 0:
        raise ValueError("blank_thickness must be positive")
    if tf <= 0:
        raise ValueError("final_thickness must be positive")
    if tf >= t0:
        raise ValueError("final_thickness must be smaller than blank_thickness (spinning thins)")
    return degrees(asin(tf / t0))


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
