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

Sources: Roark's *Formulas for Stress and Strain* and the AISC *Steel
Construction Manual* for the section-property and shear-centre relations.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import hypot, isfinite, pi
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import RevalidatedModel
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_DRAWING_SOURCE = "the member drawing or the rolled-profile table (EN 10365, AISC Manual)"
_LOAD_SOURCE = "the bending moment from the structural analysis load case"
_MATERIAL_SOURCE = "the material certificate or design code allowable stress and modulus"
_CRITERIA_SOURCE = "the project design basis required safety factor"


class _SectionInputError(RefusalError, ValueError):
    """A cross-section input that cannot be used without correction."""


def _section_refusal(message: str, *, subject: str, source: str) -> _SectionInputError:
    return _SectionInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _section_input_source(name: str) -> str:
    if name in {"bending_moment", "moment"}:
        return _LOAD_SOURCE
    if name in {"allowable_stress", "bottom_modulus", "top_modulus"}:
        return _MATERIAL_SOURCE
    if name == "required_safety_factor":
        return _CRITERIA_SOURCE
    return _DRAWING_SOURCE


__all__ = [
    "CrossSection",
    "bending_stress",
    "required_section_modulus",
    "CompositeBeamStresses",
    "composite_beam_bending_stresses",
    "channel_shear_center",
    "warping_constant_doubly_symmetric",
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
    require_finite(moment, name="moment")
    require_finite(section_modulus, name="section_modulus")
    if not isinstance(moment, Quantity):
        raise _section_refusal(
            f"moment must be a [force] * [length] quantity; got {moment!r}",
            subject="moment",
            source=_LOAD_SOURCE,
        )
    if not moment.has_dimension("[force] * [length]"):
        raise _section_refusal(
            f"moment must be a [force]*[length] quantity; got {moment.dimensionality} ({moment})",
            subject="moment",
            source=_LOAD_SOURCE,
        )
    if not isinstance(section_modulus, Quantity):
        raise _section_refusal(
            f"section_modulus must be a [length]**3 quantity; got {section_modulus!r}",
            subject="section_modulus",
            source=_DRAWING_SOURCE,
        )
    if not section_modulus.has_dimension("[length]**3"):
        raise _section_refusal(
            f"section_modulus must be a [length]**3 quantity; got "
            f"{section_modulus.dimensionality} ({section_modulus})",
            subject="section_modulus",
            source=_DRAWING_SOURCE,
        )
    if section_modulus.to("mm**3").magnitude <= 0:
        raise _section_refusal(
            f"section_modulus must be positive; got {section_modulus}",
            subject="section_modulus",
            source=_DRAWING_SOURCE,
        )
    stress = moment.pint / section_modulus.pint
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def _mm(magnitude: float) -> Quantity:
    return Quantity(magnitude=magnitude, unit="mm")


def _require_length(
    value: Quantity, name: str, *, sign: Literal["positive", "non_negative", "any"] = "positive"
) -> float:
    """One length in mm, refusing a size that is not one.

    ``sign`` is ``"positive"`` for a size, because a rectangle 50 mm wide the wrong way
    round returned a NEGATIVE area and second moment — and a negative second moment divides
    into a deflection, which then clears any limit. ``"non_negative"`` is for a radius that
    may be absent (a zero fillet is the plate-built shape), and ``"any"`` for a position,
    which is measured from an origin and is signed.
    """
    if not isinstance(value, Quantity):
        raise _section_refusal(
            f"{name} must be a [length] quantity; got {value!r}",
            subject=name,
            source=_section_input_source(name),
        )
    if not value.has_dimension("[length]"):
        raise _section_refusal(
            f"{name} must be a [length] quantity; got {value.dimensionality}",
            subject=name,
            source=_section_input_source(name),
        )
    require_finite(value, name=name)
    magnitude = value.to("mm").magnitude
    if sign == "positive" and magnitude <= 0:
        raise _section_refusal(
            f"{name} must be positive; got {value}. A section dimension of zero or "
            "below is not a smaller section — it inverts the area and second moment it "
            "computes, and a negative second moment clears every deflection limit",
            subject=name,
            source=_section_input_source(name),
        )
    if sign == "non_negative" and magnitude < 0:
        raise _section_refusal(
            f"{name} must be zero or positive; got {value}",
            subject=name,
            source=_section_input_source(name),
        )
    return magnitude


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
    Z_min = n·|M|/σ_allow — the first sizing step for a beam, before a trial section
    is picked and its Z compared against this floor. ``bending_moment`` M is the
    governing moment (magnitude; a hogging moment needs the same section modulus as
    the sagging one, so the sign is irrelevant to the size — the same convention
    :func:`~anvilate.analysis.axial.required_axial_area` uses), ``allowable_stress``
    σ_allow the material's allowable bending stress, and ``required_safety_factor`` n
    the margin on it (default 1.0, i.e.
    σ_allow already includes the margin). Returns the minimum Z in mm³; the moment
    and stress are dimension-checked and ``required_safety_factor`` /
    ``allowable_stress`` must be
    positive.
    """
    require_finite(allowable_stress, name="allowable_stress")
    require_finite(bending_moment, name="bending_moment")
    require_finite(required_safety_factor, name="required_safety_factor")
    if not isinstance(bending_moment, Quantity):
        raise _section_refusal(
            f"bending_moment must be a [force] * [length] quantity; got {bending_moment!r}",
            subject="bending_moment",
            source=_LOAD_SOURCE,
        )
    if not bending_moment.has_dimension("[force] * [length]"):
        raise _section_refusal(
            f"bending_moment must be a [force]*[length] quantity; got "
            f"{bending_moment.dimensionality} ({bending_moment})",
            subject="bending_moment",
            source=_LOAD_SOURCE,
        )
    if not isinstance(allowable_stress, Quantity):
        raise _section_refusal(
            f"allowable_stress must be a [pressure] quantity; got {allowable_stress!r}",
            subject="allowable_stress",
            source=_MATERIAL_SOURCE,
        )
    if not allowable_stress.has_dimension("[pressure]"):
        raise _section_refusal(
            f"allowable_stress must be a [pressure] quantity; got "
            f"{allowable_stress.dimensionality} ({allowable_stress})",
            subject="allowable_stress",
            source=_MATERIAL_SOURCE,
        )
    if required_safety_factor <= 0:
        raise _section_refusal(
            f"required_safety_factor must be positive; got {required_safety_factor}",
            subject="required_safety_factor",
            source=_CRITERIA_SOURCE,
        )
    if allowable_stress.to("MPa").magnitude <= 0:
        raise _section_refusal(
            f"allowable_stress must be positive; got {allowable_stress}",
            subject="allowable_stress",
            source=_MATERIAL_SOURCE,
        )
    # Without abs() a routine hogging moment (a cantilever root, a continuous beam over a
    # support) sized the beam at a NEGATIVE section modulus, which this module's own
    # bending_stress then refuses.
    z = required_safety_factor * abs(bending_moment.pint) / allowable_stress.pint
    converted = z.to("mm**3")
    return Quantity(magnitude=float(converted.magnitude), unit="mm**3")


def _tube_properties(outer: float, inner: float) -> tuple[float, float, float]:
    """A round tube's area, second moment and extreme fibre, in mm units."""
    return pi * (outer**2 - inner**2) / 4, pi * (outer**4 - inner**4) / 64, outer / 2


def _rounded_rectangle(breadth: float, depth: float, radius: float) -> tuple[float, float, float]:
    """A solid rectangle with its four corners rounded: area, second moment about the axis
    parallel to its breadth, and plastic modulus about the same axis.

    The rectangle, less a square at each corner, plus the quarter circle that replaces it.
    A quarter circle's centroid is 4r/(3π) from the circle's centre and its own second
    moment about that centroid is (π/16 − 4/(9π))·r⁴. A radius of zero is the rectangle.
    """
    square = radius**2
    quarter = pi * square / 4
    to_square = depth / 2 - radius / 2
    to_quarter = depth / 2 - radius + 4 * radius / (3 * pi)
    area = breadth * depth - (4 - pi) * square
    second_moment = (
        breadth * depth**3 / 12
        - 4 * (radius**4 / 12 + square * to_square**2)
        + 4 * ((pi / 16 - 4 / (9 * pi)) * radius**4 + quarter * to_quarter**2)
    )
    plastic = breadth * depth**2 / 4 - 4 * square * to_square + 4 * quarter * to_quarter
    return area, second_moment, plastic


def _box_properties(
    breadth: float, depth: float, wall: float, corner: float = 0.0
) -> tuple[float, float, float]:
    """A box's area, second moment about its breadth and extreme fibre.

    ``corner`` is the outside corner radius: zero for a box welded from four plates. The
    inside corner is then rounded to ``corner − wall``, which keeps the wall one thickness
    round the bend, and is square when that is not positive.
    """
    outer = _rounded_rectangle(breadth, depth, corner)
    inner = _rounded_rectangle(breadth - 2 * wall, depth - 2 * wall, max(corner - wall, 0.0))
    return outer[0] - inner[0], outer[1] - inner[1], depth / 2


class CrossSection(RevalidatedModel):
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

    The three numbers a stress check reads do not say how thin the wall that carries them
    is, and a thin wall buckles before the section yields. The two hollow builders
    therefore record what they were built from: ``outside`` is a round tube's one outside
    diameter or a box's breadth and depth, and ``wall_thickness`` its wall. A section that
    states them is held to them, so the properties are that tube's or that box's. A box
    welded from plates has square corners; a rolled one states its outside
    ``corner_radius``, which takes a little metal out of each corner.
    """

    model_config = ConfigDict(frozen=True)

    area: Quantity
    second_moment: Quantity
    extreme_fibre: Quantity
    second_moment_transverse: Quantity | None = None
    shear_form_factor: float | None = None
    outside: tuple[Quantity, ...] | None = None
    wall_thickness: Quantity | None = None
    corner_radius: Quantity | None = None
    shear_centre_offset: Quantity | None = None
    minor_principal_second_moment: Quantity | None = None
    principal_axis_tangent: float | None = None

    @model_validator(mode="after")
    def _every_property_is_a_number(self) -> CrossSection:
        # A non-finite transverse I is the worst case this guards. It passes the builders'
        # `<= 0` checks, and `least_radius_of_gyration` picks the smaller axis with `min()`,
        # which DROPS the NaN — so the property documented as governing over both axes
        # silently returns the STRONG-axis value. On an I-section that is 4.5x too large,
        # and it divides straight into the column slenderness.
        for name in ("area", "second_moment", "extreme_fibre", "second_moment_transverse"):
            value = getattr(self, name)
            if value is not None:
                require_finite(value, name=name)
                # The builders refuse `<= 0`, and a section built by hand did not: a zero
                # area or extreme fibre divided straight into a stress and ended a column
                # screen with ZeroDivisionError. A section has no zero dimension.
                if value.magnitude <= 0:
                    raise _section_refusal(
                        f"{name} must be greater than zero; got {value}",
                        subject=name,
                        source=_section_input_source(name),
                    )
        # An open section's shear centre lies outside its web, so this is a positive
        # length. A non-finite one would reach the twist entry and read as a distance.
        if self.shear_centre_offset is not None:
            require_finite(self.shear_centre_offset, name="shear_centre_offset")
            # A force here validated and then ended the beam screen converting it to mm.
            if not self.shear_centre_offset.has_dimension("[length]"):
                raise _section_refusal(
                    "shear_centre_offset is a distance from the back of the web, so it is a "
                    f"[length]; got {self.shear_centre_offset.dimensionality}",
                    subject="shear_centre_offset",
                    source=_DRAWING_SOURCE,
                )
            if self.shear_centre_offset.magnitude <= 0:
                raise _section_refusal(
                    "shear_centre_offset is measured from the back of the web to a shear "
                    f"centre outside it, so it is positive; got {self.shear_centre_offset}",
                    subject="shear_centre_offset",
                    source=_DRAWING_SOURCE,
                )
        # The minor principal moment is the smallest second moment the section has, so a
        # value above the reference axis's would make `least_radius_of_gyration` return the
        # reference axis and read as though the principal one had been considered.
        if self.minor_principal_second_moment is not None:
            require_finite(self.minor_principal_second_moment, name="minor_principal_second_moment")
            minor = self.minor_principal_second_moment.to("mm**4").magnitude
            if minor <= 0:
                raise _section_refusal(
                    "minor_principal_second_moment must be greater than zero; got "
                    f"{self.minor_principal_second_moment}",
                    subject="minor_principal_second_moment",
                    source=_DRAWING_SOURCE,
                )
            others = [self.second_moment] + (
                [self.second_moment_transverse] if self.second_moment_transverse else []
            )
            if minor > min(one.to("mm**4").magnitude for one in others) * (1 + 1e-9):
                raise _section_refusal(
                    f"minor_principal_second_moment ({self.minor_principal_second_moment}) is "
                    "the smallest second moment the section has, and this one is above an "
                    "axis the section already states",
                    subject="minor_principal_second_moment",
                    source=_DRAWING_SOURCE,
                )
        if self.principal_axis_tangent is not None and not isfinite(self.principal_axis_tangent):
            raise _section_refusal(
                f"principal_axis_tangent must be finite; got {self.principal_axis_tangent}",
                subject="principal_axis_tangent",
                source=_DRAWING_SOURCE,
            )
        # The two describe one thing, the tilt of the principal axes off the reference ones,
        # and the flexural screens refuse on the tangent. So a minor moment below both
        # reference axes, which is what a tilt is, has to come with a tangent that says so:
        # without one, a hand-built angle passed a beam screen on M/S about a leg.
        tilted = bool(self.principal_axis_tangent)
        if tilted and self.minor_principal_second_moment is None:
            raise _section_refusal(
                f"principal_axis_tangent is {self.principal_axis_tangent:g}, which says the "
                "principal axes are tilted, and no minor_principal_second_moment says how "
                "weak the axis it names is; state both",
                subject="minor_principal_second_moment",
                source=_DRAWING_SOURCE,
            )
        if self.minor_principal_second_moment is not None and not tilted:
            minor = self.minor_principal_second_moment.to("mm**4").magnitude
            stated = [self.second_moment] + (
                [self.second_moment_transverse] if self.second_moment_transverse else []
            )
            if minor < min(one.to("mm**4").magnitude for one in stated) * (1 - 1e-6):
                raise _section_refusal(
                    "minor_principal_second_moment is below every axis the section states, so "
                    "its principal axes are tilted off them, and no principal_axis_tangent "
                    "says by how much; state principal_axis_tangent beside it, or a bending "
                    "screen reads M/S about an axis that is not principal",
                    subject="principal_axis_tangent",
                    source=_DRAWING_SOURCE,
                )
        if self.shear_form_factor is not None and not isfinite(self.shear_form_factor):
            raise _section_refusal(
                f"shear_form_factor must be finite; got {self.shear_form_factor}",
                subject="shear_form_factor",
                source=_DRAWING_SOURCE,
            )
        if self.shear_form_factor is not None and not self.shear_form_factor > 0:
            raise _section_refusal(
                f"shear_form_factor must be positive; got {self.shear_form_factor}. It is the "
                "peak transverse shear over the average, which a section cannot make zero",
                subject="shear_form_factor",
                source=_DRAWING_SOURCE,
            )
        return self

    @model_validator(mode="after")
    def _a_stated_wall_is_the_wall_of_this_section(self) -> CrossSection:
        if self.outside is None and self.wall_thickness is None:
            if self.corner_radius is not None:
                raise _section_refusal(
                    "corner_radius is the corner of a box, which states outside and wall_thickness",
                    subject="corner_radius",
                    source=_DRAWING_SOURCE,
                )
            return self
        if self.outside is None or self.wall_thickness is None:
            raise _section_refusal(
                "a hollow section states both outside and wall_thickness, or neither",
                subject="outside and wall_thickness",
                source=_DRAWING_SOURCE,
            )
        if len(self.outside) not in (1, 2):
            raise _section_refusal(
                "outside is one diameter for a round tube or a breadth and a depth for a "
                f"box; got {len(self.outside)} lengths",
                subject="outside",
                source=_DRAWING_SOURCE,
            )
        sizes = [_require_length(size, "outside") for size in self.outside]
        wall = _require_length(self.wall_thickness, "wall_thickness")
        if not 2 * wall < min(sizes):
            raise _section_refusal(
                f"wall_thickness ({self.wall_thickness}) must be below half the smaller "
                f"outside dimension ({min(sizes):g} mm), to leave a bore",
                subject="wall_thickness and outside",
                source=_DRAWING_SOURCE,
            )
        corner = 0.0
        if self.corner_radius is not None:
            corner = _require_length(self.corner_radius, "corner_radius")
            if len(sizes) == 1 or not corner <= min(sizes) / 2:
                raise _section_refusal(
                    f"corner_radius ({self.corner_radius}) is the outside corner of a box, "
                    "at most half its smaller outside dimension; a round tube has none",
                    subject="corner_radius and outside",
                    source=_DRAWING_SOURCE,
                )
        if len(sizes) == 1:
            expected = _tube_properties(sizes[0], sizes[0] - 2 * wall)
        else:
            expected = _box_properties(sizes[0], sizes[1], wall, corner)
        stated = (
            self.area.to("mm**2").magnitude,
            self.second_moment.to("mm**4").magnitude,
            self.extreme_fibre.to("mm").magnitude,
        )
        # What is stated beside a wall is checked against it. Without this a section could
        # be screened for local buckling as one tube and for stress as another.
        for name, have, want in zip(
            ("area", "second_moment", "extreme_fibre"), stated, expected, strict=True
        ):
            if abs(have - want) > 1e-9 * want:
                shape = "tube" if len(sizes) == 1 else "box"
                raise _section_refusal(
                    f"{name} is {have:.6g} and the {shape} that outside and wall_thickness "
                    f"describe has {want:.6g}",
                    subject=f"{name}, outside and wall_thickness",
                    source=_DRAWING_SOURCE,
                )
        return self

    @property
    def section_modulus(self) -> Quantity:
        """The elastic section modulus Z = I/c — a bending stress is M/Z."""
        z = self.second_moment.to("mm**4").magnitude / self.extreme_fibre.to("mm").magnitude
        return Quantity(magnitude=z, unit="mm**3")

    @property
    def plastic_modulus(self) -> Quantity | None:
        """The plastic section modulus Z of a section that records its tube or box, else None.

        (D³ − d³)/6 for a round tube; for a box, the first moment of each half about the
        bending axis, corners included.
        """
        if self.outside is None or self.wall_thickness is None:
            return None
        wall = self.wall_thickness.to("mm").magnitude
        sizes = [size.to("mm").magnitude for size in self.outside]
        if len(sizes) == 1:
            plastic = (sizes[0] ** 3 - (sizes[0] - 2 * wall) ** 3) / 6
        else:
            corner = 0.0 if self.corner_radius is None else self.corner_radius.to("mm").magnitude
            breadth, depth = sizes
            plastic = (
                _rounded_rectangle(breadth, depth, corner)[2]
                - _rounded_rectangle(breadth - 2 * wall, depth - 2 * wall, max(corner - wall, 0.0))[
                    2
                ]
            )
        return Quantity(magnitude=plastic, unit="mm**3")

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
        """The governing column slenderness r = √(min(I)/A) over every axis stated.

        A column buckles about whichever centroidal axis is weaker, so this is
        the value a buckling check should use. Falls back to the bending-axis
        value when the section carries no transverse second moment.

        For a section whose weakest axis is neither of its reference axes — an angle, whose
        principal axes lie across its legs — that axis is
        ``minor_principal_second_moment``, and it governs here. Without it a single angle
        would be buckled about the weaker of its two legs, which is not the way it goes.
        """
        i = self.second_moment.to("mm**4").magnitude
        for other in (self.second_moment_transverse, self.minor_principal_second_moment):
            if other is not None:
                i = min(i, other.to("mm**4").magnitude)
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
            raise _section_refusal(
                f"inner_diameter ({inner_diameter}) must be non-negative and below "
                f"outer_diameter ({outer_diameter})",
                subject="inner_diameter and outer_diameter",
                source=_DRAWING_SOURCE,
            )
        area, second_moment, fibre = _tube_properties(do, di)
        i = Quantity(magnitude=second_moment, unit="mm**4")
        return cls(
            area=Quantity(magnitude=area, unit="mm**2"),
            second_moment=i,
            extreme_fibre=_mm(fibre),
            second_moment_transverse=i,
            # exact neutral-axis peak for an annulus: 4/3 solid -> 2.0 thin tube
            shear_form_factor=(4.0 / 3.0) * (do**2 + do * di + di**2) / (do**2 + di**2),
            outside=(_mm(do),),
            wall_thickness=_mm((do - di) / 2),
        )

    @classmethod
    def hollow_rectangular(
        cls,
        *,
        width: Quantity,
        height: Quantity,
        wall_thickness: Quantity,
        corner_radius: Quantity | None = None,
    ) -> CrossSection:
        """A rectangular box tube of uniform ``wall_thickness``, bending about the
        axis normal to ``height``: A = b·h − (b−2t)·(h−2t),
        I = (b·h³ − (b−2t)·(h−2t)³)/12, c = h/2, I_t with b and h swapped.

        ``corner_radius`` is the outside corner radius of a rolled box, with the inside
        corner rounded to keep the wall; each of those properties then loses what the
        corners do."""
        b = _require_length(width, "width")
        h = _require_length(height, "height")
        t = _require_length(wall_thickness, "wall_thickness")
        if not 0 < 2 * t < min(b, h):
            raise _section_refusal(
                f"wall_thickness ({wall_thickness}) must be positive and below half "
                f"the smaller outside dimension ({width} x {height})",
                subject="wall_thickness, width, and height",
                source=_DRAWING_SOURCE,
            )
        corner = 0.0 if corner_radius is None else _require_length(corner_radius, "corner_radius")
        if not corner <= min(b, h) / 2:
            raise _section_refusal(
                f"corner_radius ({corner_radius}) must be at most half the smaller outside "
                f"dimension ({width} x {height})",
                subject="corner_radius, width, and height",
                source=_DRAWING_SOURCE,
            )
        area, second_moment, fibre = _box_properties(b, h, t, corner)
        transverse = _box_properties(h, b, t, corner)[1]
        return cls(
            area=Quantity(magnitude=area, unit="mm**2"),
            second_moment=Quantity(magnitude=second_moment, unit="mm**4"),
            extreme_fibre=_mm(fibre),
            second_moment_transverse=Quantity(magnitude=transverse, unit="mm**4"),
            # web-area approximation: the two side walls carry the shear
            shear_form_factor=area / (2 * t * h),
            outside=(_mm(b), _mm(h)),
            wall_thickness=_mm(t),
            corner_radius=None if corner_radius is None else _mm(corner),
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
            raise _section_refusal(
                f"flange_thickness ({flange_thickness}) must be positive and below "
                f"half the depth ({depth})",
                subject="flange_thickness and depth",
                source=_DRAWING_SOURCE,
            )
        if not 0 < tw <= bf:
            raise _section_refusal(
                f"web_thickness ({web_thickness}) must be positive and at most the "
                f"flange_width ({flange_width})",
                subject="web_thickness and flange_width",
                source=_DRAWING_SOURCE,
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

    @classmethod
    def rolled_i_section(
        cls,
        *,
        depth: Quantity,
        flange_width: Quantity,
        flange_thickness: Quantity,
        web_thickness: Quantity,
        root_radius: Quantity,
    ) -> CrossSection:
        """A hot-rolled I or H profile: :meth:`i_section` plus its four root fillets.

        A rolled section is not three rectangles. Each web-to-flange junction carries a
        fillet of ``root_radius`` r, and on an IPE 200 the four of them are 4% of the area —
        the plate-built :meth:`i_section` gives 2,725 mm² where the profile has 2,848. Each
        fillet is the spandrel between an r × r square and a quarter circle, area
        (1 − π/4)·r², centroid e = r·(10 − 3π)/(12 − 3π) from each face it meets, and it adds
        to both second moments by the parallel-axis theorem.

        Anchored against EN 10365 profile tables: for all eighteen IPE sizes these
        formulas reproduce the published A, I_y and I_z to within 0.05%.
        """
        plated = cls.i_section(
            depth=depth,
            flange_width=flange_width,
            flange_thickness=flange_thickness,
            web_thickness=web_thickness,
        )
        h = _require_length(depth, "depth")
        tf = _require_length(flange_thickness, "flange_thickness")
        tw = _require_length(web_thickness, "web_thickness")
        r = _require_length(root_radius, "root_radius", sign="non_negative")
        bf = _require_length(flange_width, "flange_width")
        if 2 * r > bf - tw or 2 * (tf + r) > h:
            raise _section_refusal(
                f"root_radius ({root_radius}) does not fit the section: two fillets need "
                f"2·r of the flange outstand ({bf - tw:g} mm) and of the clear web height",
                subject="root_radius, depth, flange_width, flange_thickness, and web_thickness",
                source=_DRAWING_SOURCE,
            )
        fillet = (1 - pi / 4) * r * r
        e = r * (10 - 3 * pi) / (12 - 3 * pi)
        # The spandrel about its own centroid, parallel to a face: the r × r square about
        # that face, less the quarter disk (centred at the far corner) about the same face,
        # shifted to the centroid. Identical for both axes by symmetry.
        quarter, arm = pi * r * r / 4, 4 * r / (3 * pi)
        about_face = r**4 / 3 - ((pi * r**4 / 16 - quarter * arm * arm) + quarter * (r - arm) ** 2)
        own = about_face - fillet * e * e
        strong = 4 * (own + fillet * (h / 2 - tf - e) ** 2)
        weak = 4 * (own + fillet * (tw / 2 + e) ** 2)
        area = plated.area.to("mm**2").magnitude + 4 * fillet
        plated_weak = (2 * tf * bf**3 + (h - 2 * tf) * tw**3) / 12
        return cls(
            area=Quantity(magnitude=area, unit="mm**2"),
            second_moment=Quantity(
                magnitude=plated.second_moment.to("mm**4").magnitude + strong, unit="mm**4"
            ),
            extreme_fibre=_mm(h / 2),
            second_moment_transverse=Quantity(magnitude=plated_weak + weak, unit="mm**4"),
            # The same AISC G2 web-area ratio as :meth:`i_section`, over the filleted area.
            shear_form_factor=area / (h * tw),
        )

    @classmethod
    def channel(
        cls,
        *,
        depth: Quantity,
        flange_width: Quantity,
        flange_thickness: Quantity,
        web_thickness: Quantity,
    ) -> CrossSection:
        """A rolled channel about its strong axis, and where its shear centre is.

        Three rectangles: a web of the full ``depth`` d by ``web_thickness`` tw, and two
        flanges of ``flange_thickness`` tf reaching ``flange_width`` bf from the back of the
        web. The corners are sharp, which is why the properties come out a little under a
        rolled channel's: against the AISC Shapes Database's 32 C and 40 MC rows this gives
        the tabulated A, I_x and S_x between 1.8% low and 0.2% high, and low on at least 64
        of the 72, because the root fillets add metal the sharp corner does not. The handful
        that read high do so inside the three figures the database prints. Low is the
        conservative side for all three.

        It reports **no** ``second_moment_transverse``, deliberately. A channel's weak axis
        turns on how the flange metal is spread across bf, and a rolled flange tapers from
        root to toe — which these four dimensions do not say. Modelled as sharp rectangles
        the weak-axis I_y comes out up to 30% *above* the tabulated value, and the best
        single taper constant over those 72 rows still leaves it 10% above. High is the
        unconservative side for a column, so the number is withheld rather than guessed:
        :attr:`least_radius_of_gyration` falls back to the bending axis when it is absent,
        so the structural pack refuses a channel column rather than screening one.

        ``shear_centre_offset`` is where a transverse load has to act to bend the channel
        without twisting it, measured from the back of the web as AISC's ``eo`` column is:
        e = 3·tf·b²/(6·b·tf + h·tw) − tw/2, with b = bf − tw/2 to the flange tip and
        h = d − tf between flange centrelines. Taking the flange and web thicknesses apart
        matters: the uniform-thickness 3·b²/(h + 6·b) misses those 72 rows by 23% on average,
        and this form reproduces them within 0.65%.
        """
        d = _require_length(depth, "depth")
        bf = _require_length(flange_width, "flange_width")
        tf = _require_length(flange_thickness, "flange_thickness")
        tw = _require_length(web_thickness, "web_thickness")
        if 2 * tf >= d:
            raise _section_refusal(
                f"two flanges of {tf:g} mm leave no web in a {d:g} mm depth",
                subject="flange_thickness and depth",
                source=_DRAWING_SOURCE,
            )
        if tw >= bf:
            raise _section_refusal(
                f"a {tw:g} mm web leaves no flange inside a {bf:g} mm flange_width",
                subject="web_thickness and flange_width",
                source=_DRAWING_SOURCE,
            )
        outstand = bf - tw
        flange = outstand * tf
        area = d * tw + 2 * flange
        strong = tw * d**3 / 12 + 2 * (outstand * tf**3 / 12 + flange * ((d - tf) / 2) ** 2)
        b, h = bf - tw / 2, d - tf
        offset = 3 * tf * b**2 / (6 * b * tf + h * tw) - tw / 2
        return cls(
            area=Quantity(magnitude=area, unit="mm**2"),
            second_moment=Quantity(magnitude=strong, unit="mm**4"),
            extreme_fibre=_mm(d / 2),
            # The web carries the shear, as it does in an I-section (AISC G2).
            shear_form_factor=area / (d * tw),
            shear_centre_offset=_mm(offset),
        )

    @classmethod
    def angle(
        cls,
        *,
        depth: Quantity,
        width: Quantity,
        thickness: Quantity,
    ) -> CrossSection:
        """A rolled single angle, with the principal axes its legs are not.

        Two sharp-cornered rectangles meeting at the heel: a leg of ``depth`` standing up the
        reference y axis and a leg of ``width`` running out along x, both ``thickness``
        thick. ``second_moment`` is about the horizontal centroidal axis and
        ``second_moment_transverse`` about the vertical one, as they are for any other
        section here.

        An angle's own axes, though, are neither of those. It has no axis of symmetry
        unless its legs are equal, and even then the symmetry is the diagonal, so its
        principal axes lie across the legs: ``minor_principal_second_moment`` is the
        smallest second moment it has, from the eigenvalues of its inertia tensor, and
        ``principal_axis_tangent`` is the slope of the axis that goes with it — AISC's
        ``tan(α)``. The minor principal axis is what a single angle buckles about, and
        :attr:`least_radius_of_gyration` takes it from here, so a strut is screened on the
        axis it actually bows about rather than on the weaker of its two legs.

        Anchored on the AISC Shapes Database's 137 L rows. Unlike a channel, an angle's legs
        are not tapered, so sharp rectangles reproduce it closely: area within 1.4%, both
        geometric second moments within 2.4%, the minor principal moment within 6.0% and the
        radius of gyration that comes from it within 2.7%, and ``tan(α)`` within 1.2% —
        0.11% on average, which is what confirms the axis orientation rather than the
        magnitudes. The residual is the heel fillet and the toe radii, which a sharp corner
        has none of; the small sections are the loose ones.
        """
        d = _require_length(depth, "depth")
        b = _require_length(width, "width")
        t = _require_length(thickness, "thickness")
        if t >= min(d, b):
            raise _section_refusal(
                f"a {t:g} mm thickness leaves no angle inside legs of {d:g} and {b:g} mm",
                subject="thickness, depth and width",
                source=_DRAWING_SOURCE,
            )
        # Heel at the origin: the depth leg up y, the width leg out along x.
        outstand = b - t
        # (area, x of its centroid, y of it, its own I about x, its own I about y)
        legs = (
            (t * d, t / 2, d / 2, t * d**3 / 12, d * t**3 / 12),
            (outstand * t, t + outstand / 2, t / 2, outstand * t**3 / 12, t * outstand**3 / 12),
        )
        area = sum(leg[0] for leg in legs)
        across = sum(leg[0] * leg[1] for leg in legs) / area
        up = sum(leg[0] * leg[2] for leg in legs) / area
        strong = sum(leg[3] + leg[0] * (leg[2] - up) ** 2 for leg in legs)
        weak = sum(leg[4] + leg[0] * (leg[1] - across) ** 2 for leg in legs)
        # A rectangle has no product of inertia about its own axes, so only the offsets
        # contribute. It is what tilts the principal axes off the legs.
        product = sum(leg[0] * (leg[1] - across) * (leg[2] - up) for leg in legs)
        middle = (strong + weak) / 2
        half = hypot((strong - weak) / 2, product)
        minor = middle - half
        tangent = (minor - weak) / product if product else 0.0
        return cls(
            area=Quantity(magnitude=area, unit="mm**2"),
            second_moment=Quantity(magnitude=strong, unit="mm**4"),
            extreme_fibre=_mm(max(up, d - up)),
            second_moment_transverse=Quantity(magnitude=weak, unit="mm**4"),
            minor_principal_second_moment=Quantity(magnitude=minor, unit="mm**4"),
            principal_axis_tangent=abs(tangent),
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
    require_finite(bottom_height, name="bottom_height")
    require_finite(bottom_modulus, name="bottom_modulus")
    require_finite(bottom_width, name="bottom_width")
    require_finite(moment, name="moment")
    require_finite(top_height, name="top_height")
    require_finite(top_modulus, name="top_modulus")
    require_finite(top_width, name="top_width")
    if not isinstance(moment, Quantity):
        raise _section_refusal(
            f"moment must be a [force] * [length] quantity; got {moment!r}",
            subject="moment",
            source=_LOAD_SOURCE,
        )
    if not moment.has_dimension("[force] * [length]"):
        raise _section_refusal(
            f"moment must be a [force]*[length] quantity; got {moment.dimensionality} ({moment})",
            subject="moment",
            source=_LOAD_SOURCE,
        )
    for value, name in (
        (bottom_width, "bottom_width"),
        (bottom_height, "bottom_height"),
        (top_width, "top_width"),
        (top_height, "top_height"),
    ):
        if not isinstance(value, Quantity):
            raise _section_refusal(
                f"{name} must be a [length] quantity; got {value!r}",
                subject=name,
                source=_section_input_source(name),
            )
        if not value.has_dimension("[length]"):
            raise _section_refusal(
                f"{name} must be a [length] quantity; got {value.dimensionality}",
                subject=name,
                source=_section_input_source(name),
            )
    for value, name in ((bottom_modulus, "bottom_modulus"), (top_modulus, "top_modulus")):
        if not isinstance(value, Quantity):
            raise _section_refusal(
                f"{name} must be a [pressure] quantity; got {value!r}",
                subject=name,
                source=_section_input_source(name),
            )
        if not value.has_dimension("[pressure]"):
            raise _section_refusal(
                f"{name} must be a [pressure] quantity; got {value.dimensionality}",
                subject=name,
                source=_section_input_source(name),
            )
    m = moment.to("N*mm").magnitude
    b1 = bottom_width.to("mm").magnitude
    h1 = bottom_height.to("mm").magnitude
    b2 = top_width.to("mm").magnitude
    h2 = top_height.to("mm").magnitude
    e1 = bottom_modulus.to("MPa").magnitude
    e2 = top_modulus.to("MPa").magnitude
    if min(b1, h1, b2, h2, e1, e2) <= 0:
        raise _section_refusal(
            "all widths, heights, and moduli must be positive",
            subject=(
                "bottom_width, bottom_height, bottom_modulus, top_width, top_height, and "
                "top_modulus"
            ),
            source=_DRAWING_SOURCE,
        )
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
        raise _section_refusal(
            "flange_width and web_height must be positive",
            subject="flange_width and web_height",
            source=_DRAWING_SOURCE,
        )
    return _mm(3.0 * b**2 / (h + 6.0 * b))


def warping_constant_doubly_symmetric(
    *,
    weak_axis_moment_of_inertia: Quantity,
    flange_centroid_distance: Quantity,
) -> Quantity:
    """The warping constant of a doubly-symmetric I-section, C_w = I_y·h²/4.

    When an open section twists, its flanges bend in their own plane and resist the twist by
    *warping* — a stiffness the St-Venant torsion constant J does not capture. For a
    doubly-symmetric I-shape the warping constant is C_w = I_y·h²/4, from the
    ``weak_axis_moment_of_inertia`` I_y and the ``flange_centroid_distance`` h (the distance between
    the two flange centroids, ≈ d − t_f). It is the companion to
    :func:`~anvilate.analysis.open_section_torsion_constant` J: together they set a beam's
    lateral-torsional buckling resistance and its response to non-uniform torsion — a deep,
    wide-flange section warps far more stiffly than a shallow one. Returns C_w as a length⁶ value.
    """
    require_finite(weak_axis_moment_of_inertia, name="weak_axis_moment_of_inertia")
    if not isinstance(weak_axis_moment_of_inertia, Quantity):
        raise _section_refusal(
            f"weak_axis_moment_of_inertia must be a [length]**4 quantity; "
            f"got {weak_axis_moment_of_inertia!r}",
            subject="weak_axis_moment_of_inertia",
            source=_DRAWING_SOURCE,
        )
    if not weak_axis_moment_of_inertia.has_dimension("[length]**4"):
        raise _section_refusal(
            f"weak_axis_moment_of_inertia must be a [length]**4 quantity; got "
            f"{weak_axis_moment_of_inertia.dimensionality}",
            subject="weak_axis_moment_of_inertia",
            source=_DRAWING_SOURCE,
        )
    h = _require_length(flange_centroid_distance, "flange_centroid_distance")
    if weak_axis_moment_of_inertia.to("mm**4").magnitude <= 0:
        raise _section_refusal(
            "weak_axis_moment_of_inertia must be positive",
            subject="weak_axis_moment_of_inertia",
            source=_DRAWING_SOURCE,
        )
    if h <= 0:
        raise _section_refusal(
            "flange_centroid_distance must be positive",
            subject="flange_centroid_distance",
            source=_DRAWING_SOURCE,
        )
    cw = weak_axis_moment_of_inertia.pint * flange_centroid_distance.pint**2 / 4.0
    return Quantity(magnitude=float(cw.to("mm**6").magnitude), unit="mm**6")


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
    if not isinstance(rectangles, Sequence):
        raise _section_refusal(
            f"rectangles must be a sequence, not a single value; got {rectangles!r}",
            subject="rectangles",
            source=_DRAWING_SOURCE,
        )
    if not rectangles:
        raise _section_refusal(
            "rectangles must be a non-empty sequence", subject="rectangles", source=_DRAWING_SOURCE
        )
    parts = []
    for i, rect in enumerate(rectangles):
        if not isinstance(rect, Sequence) or len(rect) != 3:
            raise _section_refusal(
                f"rectangles[{i}] must be a (width, height, centroid) triple; got {rect!r}",
                subject="rectangles",
                source=_DRAWING_SOURCE,
            )
        width, height, centroid = rect
        b = _require_length(width, f"rectangles[{i}].width")
        h = _require_length(height, f"rectangles[{i}].height")
        y = _require_length(centroid, f"rectangles[{i}].centroid", sign="any")
        if b <= 0 or h <= 0:
            raise _section_refusal(
                f"rectangles[{i}] width and height must be positive",
                subject="rectangles",
                source=_DRAWING_SOURCE,
            )
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
    if not isinstance(rectangles, Sequence):
        raise _section_refusal(
            f"rectangles must be a sequence, not a single value; got {rectangles!r}",
            subject="rectangles",
            source=_DRAWING_SOURCE,
        )
    if not rectangles:
        raise _section_refusal(
            "rectangles must be a non-empty sequence", subject="rectangles", source=_DRAWING_SOURCE
        )
    parts = []
    for i, rect in enumerate(rectangles):
        if not isinstance(rect, Sequence) or len(rect) != 3:
            raise _section_refusal(
                f"rectangles[{i}] must be a (width, height, centroid) triple; got {rect!r}",
                subject="rectangles",
                source=_DRAWING_SOURCE,
            )
        b = _require_length(rect[0], f"rectangles[{i}].width")
        h = _require_length(rect[1], f"rectangles[{i}].height")
        y = _require_length(rect[2], f"rectangles[{i}].centroid", sign="any")
        if b <= 0 or h <= 0:
            raise _section_refusal(
                f"rectangles[{i}] width and height must be positive",
                subject="rectangles",
                source=_DRAWING_SOURCE,
            )
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
