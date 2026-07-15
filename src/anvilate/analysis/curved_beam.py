"""T1 analytical curved-beam (Winkler) bending — crane hooks, clamps, links.

Bend a beam that is *already curved* — a crane hook's shank, a C-clamp frame, a
chain link — and plane sections still rotate, but the fibres between them are
shorter on the inside of the curve than the outside. Equal fibre strains
therefore make *unequal* stresses, and the stress distribution across the depth
is hyperbolic, not linear: the neutral axis shifts inward from the centroid
toward the centre of curvature, and the inner fibre works hardest. Winkler's
theory puts the neutral axis at

    r_n = A / ∫(dA/r)        (for a rectangle: r_n = h / ln(r_o/r_i))

a distance e = r_c − r_n inside the centroid radius r_c, and the bending stress
at radius r is

    σ(r) = M·(r_n − r) / (A·e·r)

so the extreme-fibre stresses are σ_i = M·c_i/(A·e·r_i) at the bore and
σ_o = −M·c_o/(A·e·r_o) at the back (c_i = r_n − r_i, c_o = r_o − r_n). A
positive moment here *decreases* the curvature (opens the hook — the sense a
load hanging in a hook's saddle produces) and puts the inner fibre in tension.
As the curvature flattens (r_c ≫ h) both fibres recover the straight-beam
±6M/(b·h²); a sharply curved bore can work 1.5–2× harder than the straight
formula admits, which is why hooks crack on the inside.

For a hook carrying a load P, add the direct stress P/A (the moment about the
centroid is P·r_c) — the worked example composes exactly that.

This module encodes the rectangular section (the general r_n integral differs
per shape). Inputs are dimension-checked :class:`~anvilate.units.Quantity`
values.
"""

from __future__ import annotations

from math import log

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "CurvedBeamStress",
    "rectangular_curved_beam_stress",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


class CurvedBeamStress(BaseModel):
    """Winkler bending of a curved beam: the shifted neutral axis and both
    extreme-fibre stresses.

    ``neutral_radius`` r_n is where the bending stress crosses zero;
    ``eccentricity`` e = r_c − r_n is its inward shift from the centroid.
    ``inner_stress`` (at the bore, r_i) and ``outer_stress`` (at the back, r_o)
    are signed: a positive (curvature-opening) moment makes the inner fibre
    tensile and the outer compressive, and |inner| > |outer| — the curved bore
    always works harder.
    """

    model_config = ConfigDict(frozen=True)

    neutral_radius: Quantity
    eccentricity: Quantity
    inner_stress: Quantity
    outer_stress: Quantity


def rectangular_curved_beam_stress(
    *,
    moment: Quantity,
    inner_radius: Quantity,
    outer_radius: Quantity,
    width: Quantity,
) -> CurvedBeamStress:
    """The Winkler bending stresses of a rectangular-section curved beam.

    ``inner_radius`` r_i and ``outer_radius`` r_o locate the section's bore and
    back from the centre of curvature (depth h = r_o − r_i, ``width`` b), and
    ``moment`` M is taken positive when it opens the curve (a hook's working
    sense), putting the bore in tension. The neutral axis sits at
    r_n = h/ln(r_o/r_i), inside the centroid by e = r_c − r_n, and the fibre
    stresses are σ_i = M·(r_n − r_i)/(A·e·r_i), σ_o = M·(r_n − r_o)/(A·e·r_o).
    r_i must be positive (a curved beam has a hole side) and r_o > r_i. Returns
    a :class:`CurvedBeamStress`; stresses in MPa.
    """
    _require(moment, "[force] * [length]", "moment")
    _require(inner_radius, "[length]", "inner_radius")
    _require(outer_radius, "[length]", "outer_radius")
    _require(width, "[length]", "width")
    ri = inner_radius.to("mm").magnitude
    ro = outer_radius.to("mm").magnitude
    b = width.to("mm").magnitude
    if ri <= 0:
        raise ValueError(f"inner_radius must be positive; got {inner_radius}")
    if ro <= ri:
        raise ValueError(f"outer_radius ({outer_radius}) must exceed inner_radius ({inner_radius})")
    if b <= 0:
        raise ValueError(f"width must be positive; got {width}")
    m = moment.to("N*mm").magnitude
    h = ro - ri
    rc = (ri + ro) / 2.0
    rn = h / log(ro / ri)
    e = rc - rn
    area = b * h
    inner = m * (rn - ri) / (area * e * ri)
    outer = m * (rn - ro) / (area * e * ro)
    return CurvedBeamStress(
        neutral_radius=Quantity(magnitude=rn, unit="mm"),
        eccentricity=Quantity(magnitude=e, unit="mm"),
        inner_stress=Quantity(magnitude=inner, unit="MPa"),
        outer_stress=Quantity(magnitude=outer, unit="MPa"),
    )
