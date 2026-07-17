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

This module encodes the rectangular, trapezoidal, and circular sections — the
general r_n = A/∫(dA/r) integral differs per shape:

    rectangle:  r_n = h / ln(r_o/r_i)
    trapezoid:  r_n = A / [ ((b_i·r_o − b_o·r_i)/h)·ln(r_o/r_i) − (b_i − b_o) ]
    circle:     r_n = (r_c + √(r_c² − c²)) / 2        (c = section radius)

Inputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import log, pi, sqrt

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "CurvedBeamStress",
    "rectangular_curved_beam_stress",
    "trapezoidal_curved_beam_stress",
    "circular_curved_beam_stress",
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
    return _winkler_stresses(m=m, area=b * h, rn=rn, rc=rc, ri=ri, ro=ro)


def _check_radii(inner_radius: Quantity, outer_radius: Quantity) -> tuple[float, float]:
    _require(inner_radius, "[length]", "inner_radius")
    _require(outer_radius, "[length]", "outer_radius")
    ri = inner_radius.to("mm").magnitude
    ro = outer_radius.to("mm").magnitude
    if ri <= 0:
        raise ValueError(f"inner_radius must be positive; got {inner_radius}")
    if ro <= ri:
        raise ValueError(f"outer_radius ({outer_radius}) must exceed inner_radius ({inner_radius})")
    return ri, ro


def _winkler_stresses(
    *, m: float, area: float, rn: float, rc: float, ri: float, ro: float
) -> CurvedBeamStress:
    e = rc - rn
    inner = m * (rn - ri) / (area * e * ri)
    outer = m * (rn - ro) / (area * e * ro)
    return CurvedBeamStress(
        neutral_radius=Quantity(magnitude=rn, unit="mm"),
        eccentricity=Quantity(magnitude=e, unit="mm"),
        inner_stress=Quantity(magnitude=inner, unit="MPa"),
        outer_stress=Quantity(magnitude=outer, unit="MPa"),
    )


def trapezoidal_curved_beam_stress(
    *,
    moment: Quantity,
    inner_radius: Quantity,
    outer_radius: Quantity,
    inner_width: Quantity,
    outer_width: Quantity,
) -> CurvedBeamStress:
    """The Winkler bending stresses of a trapezoidal-section curved beam.

    The trapezoid is *the* hook section: crane hooks widen the bore side
    (``inner_width`` b_i at r_i) and taper the back (``outer_width`` b_o at
    r_o) precisely because the inner fibre works hardest. The section's
    r_n = A/∫(dA/r) integral is

        ∫(dA/r) = ((b_i·r_o − b_o·r_i)/h)·ln(r_o/r_i) − (b_i − b_o)

    with A = h·(b_i + b_o)/2 and the centroid at
    r_c = r_i + h·(b_i + 2·b_o)/(3·(b_i + b_o)). ``moment`` M is positive when
    it opens the curve, putting the bore in tension. Either width (not both)
    may be zero — the triangular degenerate; b_i = b_o recovers the rectangle.
    r_i must be positive and r_o > r_i. Returns a :class:`CurvedBeamStress`;
    stresses in MPa.
    """
    _require(moment, "[force] * [length]", "moment")
    _require(inner_width, "[length]", "inner_width")
    _require(outer_width, "[length]", "outer_width")
    ri, ro = _check_radii(inner_radius, outer_radius)
    bi = inner_width.to("mm").magnitude
    bo = outer_width.to("mm").magnitude
    if bi < 0 or bo < 0 or bi + bo == 0:
        raise ValueError(
            f"inner_width and outer_width must be non-negative with a positive sum "
            f"(at most one may be zero); got {inner_width} and {outer_width}"
        )
    m = moment.to("N*mm").magnitude
    h = ro - ri
    area = h * (bi + bo) / 2.0
    rc = ri + h * (bi + 2.0 * bo) / (3.0 * (bi + bo))
    integral = ((bi * ro - bo * ri) / h) * log(ro / ri) - (bi - bo)
    rn = area / integral
    return _winkler_stresses(m=m, area=area, rn=rn, rc=rc, ri=ri, ro=ro)


def circular_curved_beam_stress(
    *,
    moment: Quantity,
    inner_radius: Quantity,
    outer_radius: Quantity,
) -> CurvedBeamStress:
    """The Winkler bending stresses of a circular-section curved beam.

    The round bar bent into a curve — a chain link, an eye bolt's ring, a
    proving ring. ``inner_radius`` r_i and ``outer_radius`` r_o locate the bore
    and back, so the section diameter is d = r_o − r_i (radius c = d/2) and the
    centroid sits at r_c = (r_i + r_o)/2. The circle's r_n = A/∫(dA/r)
    integral closes to

        r_n = (r_c + √(r_c² − c²)) / 2

    ``moment`` M is positive when it opens the curve, putting the bore in
    tension. r_i must be positive and r_o > r_i. Returns a
    :class:`CurvedBeamStress`; stresses in MPa.
    """
    _require(moment, "[force] * [length]", "moment")
    ri, ro = _check_radii(inner_radius, outer_radius)
    m = moment.to("N*mm").magnitude
    c = (ro - ri) / 2.0
    rc = (ri + ro) / 2.0
    rn = (rc + sqrt(rc**2 - c**2)) / 2.0
    return _winkler_stresses(m=m, area=pi * c**2, rn=rn, rc=rc, ri=ri, ro=ro)
