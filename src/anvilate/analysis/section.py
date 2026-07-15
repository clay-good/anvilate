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

from math import pi

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = ["CrossSection", "bending_stress", "required_section_modulus"]


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
