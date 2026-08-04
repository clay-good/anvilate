"""Cross-section properties as one value object.

The beam, column, and axial checks each need a section's area, second moment, and
extreme-fibre distance. :class:`CrossSection` bundles them (plus the derived
section modulus and radius of gyration) and builds them for the common shapes —
rectangular, solid round, hollow round, hollow rectangular, and the doubly
symmetric I — so a caller constructs the section once and hands its properties
to any check. :func:`bending_stress` computes the stress a moment makes on a
section (σ = M/Z), and :func:`required_section_modulus` runs the sizing the other
way: the minimum section modulus a bending moment needs to stay within an
allowable stress.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import pi

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "CrossSection",
    "bending_stress",
    "required_section_modulus",
    "CompositeBeamStresses",
    "composite_beam_bending_stresses",
    "channel_shear_center",
    "CompoundSection",
    "compound_section_properties",
    "compound_plastic_section_modulus",
]


def bending_stress(*, moment: Quantity, section_modulus: Quantity) -> Quantity:
    """The bending stress σ = M/Z on a section of modulus Z under a ``moment``.

    The direct forward check for any known moment and section — pass
    :attr:`CrossSection.section_modulus` (or a hand value) as ``section_modulus``.
    ``moment`` M must be a moment (force·length) and ``section_modulus`` Z a
    volume (length³); ``Z`` must be positive. Returns the extreme-fibre bending
    stress in MPa.
    """
    if not moment.has_dimension("[force] * [length]"):
        raise ValueError(
            f"moment must be a [force]*[length] quantity; got {moment.dimensionality} ({moment})"
        )
    if not section_modulus.has_dimension("[length]**3"):
        raise ValueError(
            f"section_modulus must be a [length]**3 quantity; got "
            f"{section_modulus.dimensionality} ({section_modulus})"
        )
    if section_modulus.to("mm**3").magnitude <= 0:
        raise ValueError(f"section_modulus must be positive; got {section_modulus}")
    stress = moment.pint / section_modulus.pint
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def _mm(magnitude: float) -> Quantity:
    return Quantity(magnitude=magnitude, unit="mm")


def _require_length(value: Quantity, name: str) -> float:
    if not value.has_dimension("[length]"):
        raise ValueError(f"{name} must be a [length] quantity; got {value.dimensionality}")
    return value.to("mm").magnitude


def required_section_modulus(
    *,
    bending_moment: Quantity,
    allowable_stress: Quantity,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least section modulus Z a beam needs to carry ``bending_moment`` within
    an allowable bending stress.

    The inverse of the σ = M/Z bending check (and of
    :attr:`CrossSection.section_modulus`): demanding M/Z ≤ σ_allow/n gives
    Z_min = n·M/σ_allow — the first sizing step for a beam, before a trial section
    is picked and its Z compared against this floor. ``bending_moment`` M is the
    governing moment, ``allowable_stress`` σ_allow the material's allowable bending
    stress, and ``required_safety_factor`` n the margin on it (default 1.0, i.e.
    σ_allow already includes the margin). Returns the minimum Z in mm³; the moment
    and stress are dimension-checked and ``n`` / ``allowable_stress`` must be
    positive.
    """
    if not bending_moment.has_dimension("[force] * [length]"):
        raise ValueError(
            f"bending_moment must be a [force]*[length] quantity; got "
            f"{bending_moment.dimensionality} ({bending_moment})"
        )
    if not allowable_stress.has_dimension("[pressure]"):
        raise ValueError(
            f"allowable_stress must be a [pressure] quantity; got "
            f"{allowable_stress.dimensionality} ({allowable_stress})"
        )
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    if allowable_stress.to("MPa").magnitude <= 0:
        raise ValueError(f"allowable_stress must be positive; got {allowable_stress}")
    z = required_safety_factor * bending_moment.pint / allowable_stress.pint
    converted = z.to("mm**3")
    return Quantity(magnitude=float(converted.magnitude), unit="mm**3")


class CrossSection(BaseModel):
    """A prismatic cross-section's properties, all about the bending neutral axis.

    ``area`` A, ``second_moment`` I, and ``extreme_fibre`` c (neutral axis to the
    outermost fibre) are the trio the stress checks consume;
    :attr:`section_modulus` (I/c) and :attr:`radius_of_gyration` (√(I/A)) derive
    from them. ``second_moment_transverse`` is I about the perpendicular
    centroidal axis — the weak axis of a section oriented depth-into-the-load —
    which :attr:`least_radius_of_gyration` folds in for column slenderness.
    ``shear_form_factor`` is the peak-over-average transverse-shear ratio k in
    τ_max = k·V/A (1.5 for a rectangle, 4/3 for a solid round, exact for a
    tube, the web-area ratio for I and box shapes); a hand-built section
    leaves it ``None`` and a shear screen must report NOT_EVALUATED rather
    than guess. Build one with :meth:`rectangular`, :meth:`solid_circular`,
    :meth:`hollow_circular`, :meth:`hollow_rectangular`, or :meth:`i_section`
    (the builders fill both second moments and the form factor).
    """

    model_config = ConfigDict(frozen=True)

    area: Quantity
    second_moment: Quantity
    extreme_fibre: Quantity
    second_moment_transverse: Quantity | None = None
    shear_form_factor: float | None = None

    @property
    def section_modulus(self) -> Quantity:
        """The elastic section modulus Z = I/c — a bending stress is M/Z."""
        z = self.second_moment.to("mm**4").magnitude / self.extreme_fibre.to("mm").magnitude
        return Quantity(magnitude=z, unit="mm**3")

    @property
    def radius_of_gyration(self) -> Quantity:
        """The radius of gyration r = √(I/A), for slenderness."""
        r = (self.second_moment.to("mm**4").magnitude / self.area.to("mm**2").magnitude) ** 0.5
        return _mm(r)

    @property
    def radius_of_gyration_transverse(self) -> Quantity | None:
        """r about the transverse axis, or None when the section doesn't carry it."""
        if self.second_moment_transverse is None:
            return None
        i_t = self.second_moment_transverse.to("mm**4").magnitude
        return _mm((i_t / self.area.to("mm**2").magnitude) ** 0.5)

    @property
    def least_radius_of_gyration(self) -> Quantity:
        """The governing column slenderness r = √(min(I)/A) over both axes.

        A column buckles about whichever centroidal axis is weaker, so this is
        the value a buckling check should use. Falls back to the bending-axis
        value when the section carries no transverse second moment.
        """
        i = self.second_moment.to("mm**4").magnitude
        if self.second_moment_transverse is not None:
            i = min(i, self.second_moment_transverse.to("mm**4").magnitude)
        return _mm((i / self.area.to("mm**2").magnitude) ** 0.5)

    @classmethod
    def rectangular(cls, *, width: Quantity, height: Quantity) -> CrossSection:
        """A solid rectangle, bending about the axis normal to ``height`` (the load
        direction): A = b·h, I = b·h³/12, c = h/2, I_t = h·b³/12."""
        b = _require_length(width, "width")
        h = _require_length(height, "height")
        return cls(
            area=Quantity(magnitude=b * h, unit="mm**2"),
            second_moment=Quantity(magnitude=b * h**3 / 12, unit="mm**4"),
            extreme_fibre=_mm(h / 2),
            second_moment_transverse=Quantity(magnitude=h * b**3 / 12, unit="mm**4"),
            shear_form_factor=1.5,
        )

    @classmethod
    def solid_circular(cls, *, diameter: Quantity) -> CrossSection:
        """A solid round bar: A = π·d²/4, I = π·d⁴/64 (both axes), c = d/2."""
        d = _require_length(diameter, "diameter")
        i = Quantity(magnitude=pi * d**4 / 64, unit="mm**4")
        return cls(
            area=Quantity(magnitude=pi * d**2 / 4, unit="mm**2"),
            second_moment=i,
            extreme_fibre=_mm(d / 2),
            second_moment_transverse=i,
            shear_form_factor=4.0 / 3.0,
        )

    @classmethod
    def hollow_circular(cls, *, outer_diameter: Quantity, inner_diameter: Quantity) -> CrossSection:
        """A round tube: A = π·(D²−d²)/4, I = π·(D⁴−d⁴)/64 (both axes), c = D/2."""
        do = _require_length(outer_diameter, "outer_diameter")
        di = _require_length(inner_diameter, "inner_diameter")
        if not 0 <= di < do:
            raise ValueError(
                f"inner_diameter ({inner_diameter}) must be non-negative and below "
                f"outer_diameter ({outer_diameter})"
            )
        i = Quantity(magnitude=pi * (do**4 - di**4) / 64, unit="mm**4")
        return cls(
            area=Quantity(magnitude=pi * (do**2 - di**2) / 4, unit="mm**2"),
            second_moment=i,
            extreme_fibre=_mm(do / 2),
            second_moment_transverse=i,
            # exact neutral-axis peak for an annulus: 4/3 solid -> 2.0 thin tube
            shear_form_factor=(4.0 / 3.0) * (do**2 + do * di + di**2) / (do**2 + di**2),
        )

    @classmethod
    def hollow_rectangular(
        cls, *, width: Quantity, height: Quantity, wall_thickness: Quantity
    ) -> CrossSection:
        """A rectangular box tube of uniform ``wall_thickness``, bending about the
        axis normal to ``height``: A = b·h − (b−2t)·(h−2t),
        I = (b·h³ − (b−2t)·(h−2t)³)/12, c = h/2, I_t with b and h swapped."""
        b = _require_length(width, "width")
        h = _require_length(height, "height")
        t = _require_length(wall_thickness, "wall_thickness")
        if not 0 < 2 * t < min(b, h):
            raise ValueError(
                f"wall_thickness ({wall_thickness}) must be positive and below half "
                f"the smaller outside dimension ({width} x {height})"
            )
        bi, hi = b - 2 * t, h - 2 * t
        area = b * h - bi * hi
        return cls(
            area=Quantity(magnitude=area, unit="mm**2"),
            second_moment=Quantity(magnitude=(b * h**3 - bi * hi**3) / 12, unit="mm**4"),
            extreme_fibre=_mm(h / 2),
            second_moment_transverse=Quantity(magnitude=(h * b**3 - hi * bi**3) / 12, unit="mm**4"),
            # web-area approximation: the two side walls carry the shear
            shear_form_factor=area / (2 * t * h),
        )

    @classmethod
    def i_section(
        cls,
        *,
        depth: Quantity,
        flange_width: Quantity,
        flange_thickness: Quantity,
        web_thickness: Quantity,
    ) -> CrossSection:
        """A doubly symmetric I-shape bending about its strong axis: overall
        ``depth`` h, two ``flange_width`` × ``flange_thickness`` flanges, and a web
        of ``web_thickness`` between them. A = 2·bf·tf + (h−2·tf)·tw,
        I = (bf·h³ − (bf−tw)·(h−2·tf)³)/12, c = h/2,
        I_t = (2·tf·bf³ + (h−2·tf)·tw³)/12."""
        h = _require_length(depth, "depth")
        bf = _require_length(flange_width, "flange_width")
        tf = _require_length(flange_thickness, "flange_thickness")
        tw = _require_length(web_thickness, "web_thickness")
        if not 0 < 2 * tf < h:
            raise ValueError(
                f"flange_thickness ({flange_thickness}) must be positive and below "
                f"half the depth ({depth})"
            )
        if not 0 < tw <= bf:
            raise ValueError(
                f"web_thickness ({web_thickness}) must be positive and at most the "
                f"flange_width ({flange_width})"
            )
        hw = h - 2 * tf  # clear web height between the flanges
        area = 2 * bf * tf + hw * tw
        return cls(
            area=Quantity(magnitude=area, unit="mm**2"),
            second_moment=Quantity(magnitude=(bf * h**3 - (bf - tw) * hw**3) / 12, unit="mm**4"),
            extreme_fibre=_mm(h / 2),
            second_moment_transverse=Quantity(
                magnitude=(2 * tf * bf**3 + hw * tw**3) / 12, unit="mm**4"
            ),
            # web-area approximation on the full-depth web (the AISC G2 area)
            shear_form_factor=area / (h * tw),
        )


class CompositeBeamStresses(BaseModel):
    """The bending stresses of a two-material composite (flitch) beam under a moment.

    ``neutral_axis_from_bottom`` is the height of the transformed-section neutral axis
    above the bottom fibre, ``transformed_second_moment`` the second moment of the section
    transformed into the *bottom* material, and ``bottom_fibre_stress`` /
    ``top_fibre_stress`` the extreme-fibre bending stresses in the bottom and top
    materials. The top stress carries the modular-ratio factor n = E_top/E_bottom, which
    is why a stiff top layer (a steel plate on timber) draws far more stress than its
    depth alone suggests.
    """

    model_config = ConfigDict(frozen=True)

    neutral_axis_from_bottom: Quantity
    transformed_second_moment: Quantity
    bottom_fibre_stress: Quantity
    top_fibre_stress: Quantity


def composite_beam_bending_stresses(
    *,
    moment: Quantity,
    bottom_width: Quantity,
    bottom_height: Quantity,
    bottom_modulus: Quantity,
    top_width: Quantity,
    top_height: Quantity,
    top_modulus: Quantity,
) -> CompositeBeamStresses:
    """The bending stresses in a two-layer composite beam by the transformed-section method.

    Two rectangular layers bonded one on top of the other — a steel plate on a timber
    joist (a flitch beam), a bimetallic strip, a stiffened cover — bend as one section but
    do not share stress evenly: the stiffer material draws load in proportion to its
    modulus. The transformed-section method scales the top layer's width by the modular
    ratio n = E_top/E_bottom into an equivalent all-bottom-material section, finds its
    neutral axis and second moment I_t, and reads the stresses σ_bottom = M·y_b/I_t and
    σ_top = n·M·y_t/I_t at the extreme fibres. ``moment`` M is the applied bending moment;
    ``bottom_width``/``bottom_height``/``bottom_modulus`` and
    ``top_width``/``top_height``/``top_modulus`` are the two layers, bottom listed first.
    When both moduli are equal it reduces to the ordinary solid-section stress. Returns a
    :class:`CompositeBeamStresses` with the neutral axis, transformed I, and both fibre
    stresses.
    """
    if not moment.has_dimension("[force] * [length]"):
        raise ValueError(
            f"moment must be a [force]*[length] quantity; got {moment.dimensionality} ({moment})"
        )
    for value, name in (
        (bottom_width, "bottom_width"),
        (bottom_height, "bottom_height"),
        (top_width, "top_width"),
        (top_height, "top_height"),
    ):
        if not value.has_dimension("[length]"):
            raise ValueError(f"{name} must be a [length] quantity; got {value.dimensionality}")
    for value, name in ((bottom_modulus, "bottom_modulus"), (top_modulus, "top_modulus")):
        if not value.has_dimension("[pressure]"):
            raise ValueError(f"{name} must be a [pressure] quantity; got {value.dimensionality}")
    m = moment.to("N*mm").magnitude
    b1 = bottom_width.to("mm").magnitude
    h1 = bottom_height.to("mm").magnitude
    b2 = top_width.to("mm").magnitude
    h2 = top_height.to("mm").magnitude
    e1 = bottom_modulus.to("MPa").magnitude
    e2 = top_modulus.to("MPa").magnitude
    if min(b1, h1, b2, h2, e1, e2) <= 0:
        raise ValueError("all widths, heights, and moduli must be positive")
    n = e2 / e1
    a1 = b1 * h1
    a2 = b2 * h2
    y1 = h1 / 2.0
    y2 = h1 + h2 / 2.0
    neutral = (a1 * y1 + n * a2 * y2) / (a1 + n * a2)  # from bottom
    i_t = (
        b1 * h1**3 / 12.0
        + a1 * (neutral - y1) ** 2
        + n * (b2 * h2**3 / 12.0 + a2 * (y2 - neutral) ** 2)
    )
    total_height = h1 + h2
    sigma_bottom = m * neutral / i_t
    sigma_top = n * m * (total_height - neutral) / i_t
    return CompositeBeamStresses(
        neutral_axis_from_bottom=Quantity(magnitude=neutral, unit="mm"),
        transformed_second_moment=Quantity(magnitude=i_t, unit="mm**4"),
        bottom_fibre_stress=Quantity(magnitude=sigma_bottom, unit="MPa"),
        top_fibre_stress=Quantity(magnitude=sigma_top, unit="MPa"),
    )


def channel_shear_center(*, flange_width: Quantity, web_height: Quantity) -> Quantity:
    """The shear-centre offset e = 3·b²/(h + 6·b) of a thin-walled channel from its web.

    An open section like a channel has no closed shear path, so a transverse load that does
    not pass through its *shear centre* twists it as well as bends it — the reason a channel
    purlin or girt loaded through its web rotates unless it is restrained. For a uniform
    thin-walled channel the shear centre lies outside the web, on the side away from the
    flanges, at e = 3·b²/(h + 6·b) from the web centreline (thickness cancels out).
    ``flange_width`` b is the flange width from the web centreline to the flange tip, and
    ``web_height`` h the web depth between the flange centrelines. A wider flange pushes the
    shear centre further out; a deep web pulls it back toward the web. Load through this
    point (or restrain the twist) to keep the channel in pure bending. Returns e in mm.
    """
    b = _require_length(flange_width, "flange_width")
    h = _require_length(web_height, "web_height")
    if b <= 0 or h <= 0:
        raise ValueError("flange_width and web_height must be positive")
    return _mm(3.0 * b**2 / (h + 6.0 * b))


class CompoundSection(BaseModel):
    """The properties of a built-up section assembled from rectangular elements.

    ``area`` A is the total cross-sectional area, ``centroid`` the height of the combined
    neutral axis above the datum the element centroids were measured from,
    ``second_moment`` I the second moment about that combined neutral axis (by the
    parallel-axis theorem), and ``extreme_fibre_top`` / ``extreme_fibre_bottom`` the
    distances from the neutral axis to the topmost and bottommost fibres — divide I by the
    larger of the two for the governing section modulus.
    """

    model_config = ConfigDict(frozen=True)

    area: Quantity
    centroid: Quantity
    second_moment: Quantity
    extreme_fibre_top: Quantity
    extreme_fibre_bottom: Quantity

    @property
    def section_modulus(self) -> Quantity:
        """The governing elastic section modulus Z = I/c_max over the two extreme fibres."""
        c = max(
            self.extreme_fibre_top.to("mm").magnitude,
            self.extreme_fibre_bottom.to("mm").magnitude,
        )
        return Quantity(magnitude=self.second_moment.to("mm**4").magnitude / c, unit="mm**3")


def compound_section_properties(
    *,
    rectangles: Sequence[tuple[Quantity, Quantity, Quantity]],
) -> CompoundSection:
    """The area, neutral axis, and second moment of a built-up section (parallel-axis theorem).

    Any welded or built-up section — a plate girder, a custom I or box, a tee, a
    cover-plated beam — is a stack of rectangles, and its bending properties come from the
    parallel-axis theorem: the combined neutral axis is the area-weighted mean of the part
    centroids, ȳ = Σ(A_i·y_i)/ΣA_i, and the second moment about it is
    I = Σ(I_i + A_i·(y_i − ȳ)²) with each part's own I_i = b_i·h_i³/12. ``rectangles`` is a
    sequence of ``(width, height, centroid)`` triples — the width, the height (in the
    bending direction), and the height of each rectangle's own centroid above a common
    datum. This turns a sketch of plates into the A, I, and section modulus the bending and
    buckling checks need, for sections the standard-shape builders do not cover. Returns a
    :class:`CompoundSection`.
    """
    if not rectangles:
        raise ValueError("rectangles must be a non-empty sequence")
    parts = []
    for i, rect in enumerate(rectangles):
        if len(rect) != 3:
            raise ValueError(f"rectangles[{i}] must be a (width, height, centroid) triple")
        width, height, centroid = rect
        b = _require_length(width, f"rectangles[{i}].width")
        h = _require_length(height, f"rectangles[{i}].height")
        y = _require_length(centroid, f"rectangles[{i}].centroid")
        if b <= 0 or h <= 0:
            raise ValueError(f"rectangles[{i}] width and height must be positive")
        parts.append((b, h, y))
    total_area = sum(b * h for b, h, _ in parts)
    centroid = sum(b * h * y for b, h, y in parts) / total_area
    second_moment = sum(b * h**3 / 12.0 + b * h * (y - centroid) ** 2 for b, h, y in parts)
    top = max(y + h / 2.0 for _, h, y in parts)
    bottom = min(y - h / 2.0 for _, h, y in parts)
    return CompoundSection(
        area=Quantity(magnitude=total_area, unit="mm**2"),
        centroid=_mm(centroid),
        second_moment=Quantity(magnitude=second_moment, unit="mm**4"),
        extreme_fibre_top=_mm(top - centroid),
        extreme_fibre_bottom=_mm(centroid - bottom),
    )


def compound_plastic_section_modulus(
    *,
    rectangles: Sequence[tuple[Quantity, Quantity, Quantity]],
) -> Quantity:
    """The plastic section modulus Z of a built-up section (for the plastic moment M_p = F_y·Z).

    Where the elastic :func:`compound_section_properties` gives I about the neutral axis, this
    gives the *plastic* modulus, the property behind a section's full plastic moment. At M_p
    the whole section has yielded, so the plastic neutral axis (PNA) splits it into equal
    areas, and Z is the first moment of area taken as positive on both sides of the PNA,
    Z = Σ|A_i·(ȳ_i − y_PNA)| with any part straddling the PNA split. ``rectangles`` is the same
    sequence of ``(width, height, centroid)`` triples as
    :func:`compound_section_properties` — the plates that make up a plate girder, tee, or
    cover-plated beam. For a doubly-symmetric section the PNA is the centroid; for an
    unsymmetric one it shifts to equalize the areas. Returns Z in mm³ (multiply by F_y for M_p).
    """
    if not rectangles:
        raise ValueError("rectangles must be a non-empty sequence")
    parts = []
    for i, rect in enumerate(rectangles):
        if len(rect) != 3:
            raise ValueError(f"rectangles[{i}] must be a (width, height, centroid) triple")
        b = _require_length(rect[0], f"rectangles[{i}].width")
        h = _require_length(rect[1], f"rectangles[{i}].height")
        y = _require_length(rect[2], f"rectangles[{i}].centroid")
        if b <= 0 or h <= 0:
            raise ValueError(f"rectangles[{i}] width and height must be positive")
        parts.append((b, h, y))
    total_area = sum(b * h for b, h, _ in parts)
    half_area = total_area / 2.0

    def area_below(y_p: float) -> float:
        return sum(b * max(0.0, min(y_p - (y - h / 2.0), h)) for b, h, y in parts)

    lo = min(y - h / 2.0 for _, h, y in parts)
    hi = max(y + h / 2.0 for _, h, y in parts)
    for _ in range(200):  # bisection on the monotonic area-below function
        mid = (lo + hi) / 2.0
        if area_below(mid) < half_area:
            lo = mid
        else:
            hi = mid
    pna = (lo + hi) / 2.0

    modulus = 0.0
    for b, h, y in parts:
        bottom, top = y - h / 2.0, y + h / 2.0
        below_hi = min(pna, top)
        if below_hi > bottom:
            modulus += b * (below_hi - bottom) * abs((bottom + below_hi) / 2.0 - pna)
        above_lo = max(pna, bottom)
        if top > above_lo:
            modulus += b * (top - above_lo) * abs((above_lo + top) / 2.0 - pna)
    return Quantity(magnitude=modulus, unit="mm**3")
