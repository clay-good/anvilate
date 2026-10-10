"""Everyday parts: the plates, brackets, spacers and shafts an engineer asks for most.

These are the parts a catalog sells by the page and a designer redraws every week: a
mounting plate, an angle bracket, a flange, a spacer, a stepped shaft, a sheet-metal bracket,
an enclosure and its lid. Each is a typed element a document can declare, with unit-checked
fields, and each has an audited geometry pattern in :mod:`anvilate.patterns`, so an agent
asked for one returns a picture and a STEP file.

**Drawn is not checked.** Most of these have no discipline screen yet, and each says so: its
screen returns one *not evaluated* entry stating that the part was drawn and not checked, so
a drawn part never reads as a validated one and its exports carry the unvalidated mark. Where
a load-bearing check exists for the same job (a lifting lug, a bolted connection, a shaft
key, a transmission shaft), declare that element as well, or instead.

Holes are declared once, in one vocabulary, and built by :mod:`anvilate.features`:
:class:`Hole`, :class:`HolePattern` and :class:`Slot`, positioned from the centre of the
face they are cut into.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from .._models import Named
from ..analysis.sheetmetal import bend_allowance, minimum_bend_radius
from ..scorecard import CheckStatus, Need, Scorecard, ScorecardEntry, ValueSource
from ..units import Quantity
from ._guarded import GuardedInputs, _guarded_pack_refusal

__all__ = [
    "AngleBracket",
    "Bushing",
    "Clevis",
    "Enclosure",
    "EnclosureLid",
    "FlatPattern",
    "Hole",
    "HolePattern",
    "Keyway",
    "MountingPlate",
    "PlateFlange",
    "Pulley",
    "ShaftCollar",
    "ShaftStep",
    "SheetMetalBracket",
    "Slot",
    "Spacer",
    "Standoff",
    "SteppedShaft",
    "TSlotExtrusion",
    "Tube",
    "flat_pattern",
    "screen_angle_bracket",
    "screen_bushing",
    "screen_clevis",
    "screen_enclosure",
    "screen_enclosure_lid",
    "screen_mounting_plate",
    "screen_plate_flange",
    "screen_pulley",
    "screen_shaft_collar",
    "screen_sheet_metal_bracket",
    "screen_spacer",
    "screen_standoff",
    "screen_stepped_shaft",
    "screen_t_slot_extrusion",
    "screen_tube",
]


_DECLARED = "the drawing or sketch the part's dimensions were taken from"


def _refuse(message: str, *, subject: str) -> ValueError:
    return _guarded_pack_refusal(message, subject=subject, source=_DECLARED)


class _Part(GuardedInputs):
    """Shared rules: nothing extra, nothing mutable, and every length is a length."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    #: Fields that may be anything but a length (a count, a factor, a designation).
    not_lengths: ClassVar[tuple[str, ...]] = ()

    #: The largest value a plain number may take, by field. Declared here rather than as a
    #: field constraint so that the refusal names the field the document wrote.
    at_most: ClassVar[Mapping[str, float]] = MappingProxyType({})

    @model_validator(mode="after")
    def _every_quantity_is_a_length(self) -> _Part:
        for name, limit in type(self).at_most.items():
            value = getattr(self, name)
            if value is not None and value > limit:
                raise _refuse(f"{name} must be at most {limit:g}; got {value:g}", subject=name)
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, Quantity) and name not in type(self).not_lengths:
                if not value.has_dimension("[length]"):
                    raise _refuse(
                        f"{name} must be a length; got {value} ({value.dimensionality})",
                        subject=name,
                    )
        return self


class Hole(_Part):
    """One hole, positioned from the centre of the face it is cut into.

    ``kind`` is ``through`` (the default), ``counterbore`` (give ``counterbore_diameter``
    and ``counterbore_depth``) or ``countersink`` (give ``head_diameter``). ``thread`` marks
    a tapped hole by its designation, such as ``M6x1``; the thread is data, never geometry.
    """

    signed_fields = ("x", "y")
    positive_fields = ("diameter", "counterbore_diameter", "counterbore_depth", "head_diameter")

    tag: Named
    x: Quantity
    y: Quantity
    diameter: Quantity
    kind: Literal["through", "counterbore", "countersink"] = "through"
    counterbore_diameter: Quantity | None = None
    counterbore_depth: Quantity | None = None
    head_diameter: Quantity | None = None
    thread: str | None = None

    @model_validator(mode="after")
    def _the_kind_has_its_dimensions(self) -> Hole:
        needs = {
            "counterbore": ("counterbore_diameter", "counterbore_depth"),
            "countersink": ("head_diameter",),
        }.get(self.kind, ())
        missing = [name for name in needs if getattr(self, name) is None]
        if missing:
            raise _refuse(f"a {self.kind} hole needs {missing}", subject=missing[0])
        return self


class HolePattern(_Part):
    """Several equal through holes: a ``rectangular`` grid or a ``bolt_circle``.

    A grid states ``count_x``, ``count_y`` and the pitches; a bolt circle states ``count``
    and ``circle_diameter``. Both are centred on the face unless ``centre_x`` and
    ``centre_y`` say otherwise.
    """

    signed_fields = ("centre_x", "centre_y")
    positive_fields = (
        "diameter",
        "pitch_x",
        "pitch_y",
        "circle_diameter",
        "count_x",
        "count_y",
        "count",
    )
    at_most = MappingProxyType({"count_x": 40, "count_y": 40, "count": 72})

    tag: Named
    kind: Literal["rectangular", "bolt_circle"]
    diameter: Quantity
    count_x: int | None = None
    count_y: int | None = None
    pitch_x: Quantity | None = None
    pitch_y: Quantity | None = None
    count: int | None = None
    circle_diameter: Quantity | None = None
    start_angle_deg: float = 0.0
    centre_x: Quantity | None = None
    centre_y: Quantity | None = None
    thread: str | None = None

    @model_validator(mode="after")
    def _the_kind_has_its_dimensions(self) -> HolePattern:
        if self.kind == "bolt_circle":
            missing = [n for n in ("count", "circle_diameter") if getattr(self, n) is None]
        else:
            missing = [n for n in ("count_x", "count_y") if getattr(self, n) is None]
            if (self.count_x or 1) > 1 and self.pitch_x is None:
                missing.append("pitch_x")
            if (self.count_y or 1) > 1 and self.pitch_y is None:
                missing.append("pitch_y")
        if missing:
            raise _refuse(f"a {self.kind} hole pattern needs {missing}", subject=missing[0])
        return self


class Slot(_Part):
    """A round-ended through slot: ``length`` overall, ``width`` across, turned by ``angle_deg``."""

    signed_fields = ("x", "y")
    positive_fields = ("length", "width")

    tag: Named
    x: Quantity
    y: Quantity
    length: Quantity
    width: Quantity
    angle_deg: float = 0.0


class MountingPlate(_Part):
    """A flat rectangular plate with holes and slots: ``width`` along x, ``length`` along y."""

    positive_fields = ("width", "length", "thickness", "corner_radius")

    name: Named
    width: Quantity
    length: Quantity
    thickness: Quantity
    corner_radius: Quantity | None = None
    holes: tuple[Hole, ...] = ()
    hole_patterns: tuple[HolePattern, ...] = ()
    slots: tuple[Slot, ...] = ()
    material: str | None = None


class AngleBracket(_Part):
    """An L bracket: a base leg lying flat and an upright leg, of one ``width`` and ``thickness``.

    ``base_length`` and ``upright_height`` are measured on the outside of the angle. Holes
    are declared per leg, positioned from the centre of that leg's clear inside face: the
    part of the leg beyond the other leg's thickness. ``rib_thickness`` and ``rib_leg``
    add a triangular stiffening rib in the middle of the inside corner, running ``rib_leg``
    along each leg.
    """

    positive_fields = (
        "base_length",
        "upright_height",
        "width",
        "thickness",
        "rib_thickness",
        "rib_leg",
    )

    name: Named
    base_length: Quantity
    upright_height: Quantity
    width: Quantity
    thickness: Quantity
    rib_thickness: Quantity | None = None
    rib_leg: Quantity | None = None
    base_holes: tuple[Hole, ...] = ()
    base_patterns: tuple[HolePattern, ...] = ()
    base_slots: tuple[Slot, ...] = ()
    upright_holes: tuple[Hole, ...] = ()
    upright_patterns: tuple[HolePattern, ...] = ()
    upright_slots: tuple[Slot, ...] = ()
    material: str | None = None

    @model_validator(mode="after")
    def _a_rib_has_both_dimensions(self) -> AngleBracket:
        if (self.rib_thickness is None) != (self.rib_leg is None):
            raise _refuse("a stiffening rib states rib_thickness and rib_leg", subject="rib_leg")
        return self


class PlateFlange(_Part):
    """A flat ring flange: a disc with a central bore and a circle of bolt holes."""

    positive_fields = (
        "outer_diameter",
        "bore_diameter",
        "thickness",
        "bolt_circle_diameter",
        "bolt_hole_diameter",
        "bolt_count",
    )
    at_most = MappingProxyType({"bolt_count": 72})

    name: Named
    outer_diameter: Quantity
    bore_diameter: Quantity
    thickness: Quantity
    bolt_circle_diameter: Quantity
    bolt_count: int
    bolt_hole_diameter: Quantity
    material: str | None = None


class Spacer(_Part):
    """A plain round spacer: outside diameter, bore and length."""

    positive_fields = ("outer_diameter", "inner_diameter", "length")

    name: Named
    outer_diameter: Quantity
    inner_diameter: Quantity
    length: Quantity
    material: str | None = None


class Bushing(_Part):
    """A sleeve bushing, optionally flanged at one end."""

    positive_fields = (
        "outer_diameter",
        "inner_diameter",
        "length",
        "flange_diameter",
        "flange_thickness",
    )

    name: Named
    outer_diameter: Quantity
    inner_diameter: Quantity
    length: Quantity
    flange_diameter: Quantity | None = None
    flange_thickness: Quantity | None = None
    material: str | None = None

    @model_validator(mode="after")
    def _a_flange_has_both_dimensions(self) -> Bushing:
        if (self.flange_diameter is None) != (self.flange_thickness is None):
            raise _refuse(
                "a flanged bushing states flange_diameter and flange_thickness",
                subject="flange_thickness",
            )
        return self


class Standoff(_Part):
    """A hexagonal standoff: ``across_flats``, ``length`` and a through hole, tapped as data."""

    positive_fields = ("across_flats", "length", "hole_diameter")

    name: Named
    across_flats: Quantity
    length: Quantity
    hole_diameter: Quantity
    thread: str | None = None
    material: str | None = None


class ShaftCollar(_Part):
    """A plain shaft collar: a ring of ``bore``, ``outer_diameter`` and ``width``."""

    positive_fields = ("bore", "outer_diameter", "width")

    name: Named
    bore: Quantity
    outer_diameter: Quantity
    width: Quantity
    material: str | None = None


class ShaftStep(_Part):
    """One step of a shaft: its ``diameter`` and ``length``."""

    positive_fields = ("diameter", "length")

    diameter: Quantity
    length: Quantity


class Keyway(_Part):
    """A keyway milled into one shaft step: ``step`` counts from 1 at the drive end.

    ``offset`` is the distance from the start of that step to the start of the keyway.
    """

    positive_fields = ("width", "depth", "length", "step")

    step: int
    width: Quantity
    depth: Quantity
    length: Quantity
    offset: Quantity | None = None


class SteppedShaft(_Part):
    """A solid round shaft of several diameters along its axis, with optional keyways."""

    positive_fields = ("end_chamfer",)

    name: Named
    steps: tuple[ShaftStep, ...] = Field(min_length=1, max_length=20)
    keyways: tuple[Keyway, ...] = ()
    end_chamfer: Quantity | None = None
    material: str | None = None

    @model_validator(mode="after")
    def _keyways_name_real_steps(self) -> SteppedShaft:
        for keyway in self.keyways:
            if keyway.step > len(self.steps):
                raise _refuse(
                    f"a keyway names step {keyway.step} and the shaft has {len(self.steps)}",
                    subject="keyways",
                )
        return self


class Pulley(_Part):
    """A V-belt pulley: a disc with a bore and one V groove in its rim.

    ``groove_width`` is the groove's opening at the rim and ``groove_angle_deg`` the
    included angle between its flanks, which the belt section sets.
    """

    positive_fields = (
        "outer_diameter",
        "bore",
        "width",
        "groove_depth",
        "groove_width",
        "groove_angle_deg",
    )
    at_most = MappingProxyType({"groove_angle_deg": 120.0})

    name: Named
    outer_diameter: Quantity
    bore: Quantity
    width: Quantity
    groove_depth: Quantity
    groove_width: Quantity
    groove_angle_deg: float
    material: str | None = None


class Clevis(_Part):
    """A fork: a base block and two ears with a pin hole through both.

    ``width`` is the overall width across the ears and ``gap`` the opening between them.
    ``height`` runs from the bottom of the base to the top of the ears, and the pin hole is
    ``pin_height`` above the bottom.
    """

    positive_fields = (
        "width",
        "gap",
        "depth",
        "height",
        "base_thickness",
        "pin_diameter",
        "pin_height",
    )

    name: Named
    width: Quantity
    gap: Quantity
    depth: Quantity
    height: Quantity
    base_thickness: Quantity
    pin_diameter: Quantity
    pin_height: Quantity
    material: str | None = None


class Tube(_Part):
    """A straight tube cut to ``length``: ``round`` (outer diameter) or ``rectangular``."""

    positive_fields = ("outer_diameter", "width", "height", "wall", "length")

    name: Named
    shape: Literal["round", "rectangular"] = "round"
    wall: Quantity
    length: Quantity
    outer_diameter: Quantity | None = None
    width: Quantity | None = None
    height: Quantity | None = None
    material: str | None = None

    @model_validator(mode="after")
    def _the_shape_has_its_dimensions(self) -> Tube:
        needs = ("outer_diameter",) if self.shape == "round" else ("width", "height")
        missing = [name for name in needs if getattr(self, name) is None]
        if missing:
            raise _refuse(f"a {self.shape} tube needs {missing}", subject=missing[0])
        return self


class TSlotExtrusion(_Part):
    """A T-slot aluminium extrusion cut to ``length``, by its bundled ``designation``."""

    positive_fields = ("length",)

    name: Named
    designation: str
    length: Quantity


class SheetMetalBracket(_Part):
    """A bracket bent from one sheet: an ``L``, a ``U`` or a ``Z``.

    Flange lengths are outside dimensions. ``inside_radius`` is the bend's inside radius.
    ``k_factor`` locates the neutral axis for the flat pattern; it depends on the material,
    the thickness and the tooling, so it is an input with its ``k_factor_source`` and is
    never assumed. Without it the formed part is still drawn and the flat pattern is not.
    ``reduction_of_area_percent`` is the sheet's tensile reduction of area, with its
    ``reduction_of_area_source``; given one, the inside radius is compared with the smallest
    the material bends to without cracking.
    """

    not_lengths = ("k_factor", "reduction_of_area_percent")
    positive_fields = (
        "thickness",
        "inside_radius",
        "width",
        "flange_a",
        "flange_b",
        "flange_c",
        "k_factor",
        "reduction_of_area_percent",
    )
    at_most = MappingProxyType({"k_factor": 0.5, "reduction_of_area_percent": 100.0})

    name: Named
    shape: Literal["L", "U", "Z"] = "L"
    thickness: Quantity
    inside_radius: Quantity
    width: Quantity
    flange_a: Quantity
    flange_b: Quantity
    flange_c: Quantity | None = None
    k_factor: float | None = None
    k_factor_source: str | None = None
    reduction_of_area_percent: float | None = None
    reduction_of_area_source: str | None = None
    material: str | None = None

    @model_validator(mode="after")
    def _the_shape_has_its_flanges(self) -> SheetMetalBracket:
        if self.shape in ("U", "Z") and self.flange_c is None:
            raise _refuse(f"a {self.shape} bracket needs flange_c", subject="flange_c")
        if self.shape == "L" and self.flange_c is not None:
            raise _refuse(
                "an L bracket has two flanges; flange_c is for U and Z", subject="flange_c"
            )
        for name, straight in zip(_FLANGES, _straights(self), strict=False):
            if straight <= 0:
                raise _refuse(
                    f"{name} ({getattr(self, name)}) is shorter than its bends take up: each "
                    "bend uses inside_radius + thickness of the flange on either side of it",
                    subject=name,
                )
        if self.k_factor is not None and not (self.k_factor_source or "").strip():
            raise _refuse(
                "k_factor needs k_factor_source: the bend table or test it was read from",
                subject="k_factor_source",
            )
        if (
            self.reduction_of_area_percent is not None
            and not (self.reduction_of_area_source or "").strip()
        ):
            raise _refuse(
                "reduction_of_area_percent needs reduction_of_area_source: the material "
                "certificate or tensile test it was read from",
                subject="reduction_of_area_source",
            )
        return self


_FLANGES = ("flange_a", "flange_b", "flange_c")


def _straights(bracket: SheetMetalBracket) -> tuple[float, ...]:
    """The flat length of each flange between its bends, in mm.

    A flange length is an outside dimension, so every bend at an end of a flange takes
    ``inside_radius + thickness`` off it.
    """
    setback = bracket.inside_radius.to("mm").magnitude + bracket.thickness.to("mm").magnitude
    lengths = [getattr(bracket, name) for name in _FLANGES]
    lengths = [length.to("mm").magnitude for length in lengths if length is not None]
    return tuple(
        length - ((index > 0) + (index < len(lengths) - 1)) * setback
        for index, length in enumerate(lengths)
    )


class FlatPattern(_Part):
    """A bent bracket laid flat: its straights, its bends and the length they add up to."""

    not_lengths = ("k_factor",)

    straights: tuple[Quantity, ...]
    bends: int
    k_factor: float
    k_factor_source: str
    bend_allowance: Quantity
    developed_length: Quantity

    def __str__(self) -> str:
        return (
            f"flat pattern {self.developed_length.to('mm').magnitude:.2f} mm long: "
            f"{len(self.straights)} straights and {self.bends} bends of "
            f"{self.bend_allowance.to('mm').magnitude:.2f} mm allowance each, "
            f"K = {self.k_factor:g} from {self.k_factor_source}"
        )


def flat_pattern(bracket: SheetMetalBracket) -> FlatPattern | None:
    """The developed flat pattern of ``bracket``, or ``None`` when it states no K-factor.

    Each 90 degree bend adds the arc of its neutral fibre, the bend allowance
    ``(pi/2) * (inside_radius + k_factor * thickness)`` from
    :func:`anvilate.analysis.sheetmetal.bend_allowance`, to the straights between the bends.
    The K-factor is the declared one and is never assumed.
    """
    if bracket.k_factor is None:
        return None
    allowance = bend_allowance(
        bend_angle=90.0,
        inner_radius=bracket.inside_radius,
        thickness=bracket.thickness,
        k_factor=bracket.k_factor,
    )
    straights = _straights(bracket)
    bends = len(straights) - 1
    return FlatPattern(
        straights=tuple(Quantity(magnitude=value, unit="mm") for value in straights),
        bends=bends,
        k_factor=bracket.k_factor,
        k_factor_source=str(bracket.k_factor_source),
        bend_allowance=allowance,
        developed_length=Quantity(
            magnitude=sum(straights) + bends * allowance.to("mm").magnitude, unit="mm"
        ),
    )


class Enclosure(_Part):
    """An open-topped box: outside ``width``, ``length`` and ``height`` with a ``wall``."""

    positive_fields = ("width", "length", "height", "wall", "floor", "corner_radius")

    name: Named
    width: Quantity
    length: Quantity
    height: Quantity
    wall: Quantity
    floor: Quantity | None = None
    corner_radius: Quantity | None = None
    floor_holes: tuple[Hole, ...] = ()
    floor_patterns: tuple[HolePattern, ...] = ()
    material: str | None = None


class EnclosureLid(_Part):
    """A flat lid: a plate ``width`` by ``length``, with an optional lip under it.

    The lip is a rectangular rim that drops into the box's opening and locates the lid. It
    states three dimensions together: ``lip_inset``, how far its outside face sits in from
    the plate's edge (the box's wall plus the clearance wanted); ``lip_wall``, its own
    thickness; and ``lip_height``, how far it drops below the plate. Holes are positioned
    from the centre of the top face and go through the plate.
    """

    positive_fields = (
        "width",
        "length",
        "thickness",
        "corner_radius",
        "lip_inset",
        "lip_wall",
        "lip_height",
    )

    name: Named
    width: Quantity
    length: Quantity
    thickness: Quantity
    corner_radius: Quantity | None = None
    lip_inset: Quantity | None = None
    lip_wall: Quantity | None = None
    lip_height: Quantity | None = None
    holes: tuple[Hole, ...] = ()
    hole_patterns: tuple[HolePattern, ...] = ()
    material: str | None = None

    @model_validator(mode="after")
    def _a_lip_has_all_three_dimensions(self) -> EnclosureLid:
        lip = ("lip_inset", "lip_wall", "lip_height")
        missing = [name for name in lip if getattr(self, name) is None]
        if missing and len(missing) < len(lip):
            raise _refuse("a lip states lip_inset, lip_wall and lip_height", subject=missing[0])
        return self


def _drawn_not_checked(what: str, name: str) -> Scorecard:
    """The one entry a part with no screen carries: drawn, and not checked."""
    return Scorecard(
        entries=(
            ScorecardEntry(
                name=f"{name} screening",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"this {what} is drawn, and no strength or fit check ships for it; the "
                    "picture and the STEP file are its geometry, not a verdict on it"
                ),
            ),
        )
    )


def screen_mounting_plate(plate: MountingPlate) -> Scorecard:
    """A mounting plate is drawn and not checked."""
    return _drawn_not_checked("mounting plate", str(plate.name))


def screen_angle_bracket(bracket: AngleBracket) -> Scorecard:
    """An angle bracket is drawn and not checked."""
    return _drawn_not_checked("angle bracket", str(bracket.name))


def screen_plate_flange(flange: PlateFlange) -> Scorecard:
    """A plate flange is drawn and not checked."""
    return _drawn_not_checked("plate flange", str(flange.name))


def screen_spacer(spacer: Spacer) -> Scorecard:
    """A spacer is drawn and not checked."""
    return _drawn_not_checked("spacer", str(spacer.name))


def screen_bushing(bushing: Bushing) -> Scorecard:
    """A bushing is drawn and not checked."""
    return _drawn_not_checked("bushing", str(bushing.name))


def screen_standoff(standoff: Standoff) -> Scorecard:
    """A standoff is drawn and not checked."""
    return _drawn_not_checked("standoff", str(standoff.name))


def screen_shaft_collar(collar: ShaftCollar) -> Scorecard:
    """A shaft collar is drawn and not checked."""
    return _drawn_not_checked("shaft collar", str(collar.name))


def screen_stepped_shaft(shaft: SteppedShaft) -> Scorecard:
    """A stepped shaft is drawn and not checked; `transmission_shaft` screens one section."""
    return _drawn_not_checked("stepped shaft", str(shaft.name))


def screen_pulley(pulley: Pulley) -> Scorecard:
    """A pulley is drawn and not checked."""
    return _drawn_not_checked("pulley", str(pulley.name))


def screen_clevis(clevis: Clevis) -> Scorecard:
    """A clevis is drawn and not checked; `lifting_lug` screens a pin joint."""
    return _drawn_not_checked("clevis", str(clevis.name))


def screen_tube(tube: Tube) -> Scorecard:
    """A tube is drawn and not checked."""
    return _drawn_not_checked("tube", str(tube.name))


def screen_t_slot_extrusion(profile: TSlotExtrusion) -> Scorecard:
    """An extrusion profile is drawn and not checked."""
    return _drawn_not_checked("extrusion profile", str(profile.name))


_NEEDS_A_K_FACTOR = Need(
    declaration="element_params.k_factor",
    takes=(
        "the neutral-axis position for this material, thickness and tooling, from the "
        "shop's bend table, with element_params.k_factor_source naming that table"
    ),
    sources=(ValueSource.USER, ValueSource.MEASUREMENT),
)


def screen_sheet_metal_bracket(bracket: SheetMetalBracket) -> Scorecard:
    """A sheet-metal bracket is drawn and not checked, and its flat pattern is stated.

    With a K-factor the developed length is stated beside the drawn part, with the K-factor
    and bend allowance behind it. Without one the flat pattern is not evaluated, and the
    entry names the K-factor as what it needs. The inside radius is compared with the
    smallest the sheet bends to when its reduction of area is declared.
    """
    (drawn,) = _drawn_not_checked("sheet-metal bracket", str(bracket.name)).entries
    radius = _bend_radius_entry(bracket)
    flat = flat_pattern(bracket)
    if flat is not None:
        stated = drawn.model_copy(update={"detail": f"{drawn.detail}. Its {flat}"})
        return Scorecard(entries=(stated, radius))
    missing = ScorecardEntry(
        name=f"{bracket.name} flat pattern",
        status=CheckStatus.NOT_EVALUATED,
        detail=(
            "not evaluated — the developed length needs k_factor, and none is assumed: it "
            "depends on the material, the thickness and the tooling"
        ),
        needs=(_NEEDS_A_K_FACTOR,),
    )
    return Scorecard(entries=(drawn, missing, radius))


_NEEDS_A_REDUCTION_OF_AREA = Need(
    declaration="element_params.reduction_of_area_percent",
    takes=(
        "the sheet's tensile reduction of area in percent, from its material certificate "
        "or a tensile test, with element_params.reduction_of_area_source naming it"
    ),
    sources=(ValueSource.USER, ValueSource.MEASUREMENT),
)


def _bend_radius_entry(bracket: SheetMetalBracket) -> ScorecardEntry:
    """The inside radius against the smallest the sheet bends to without cracking.

    The minimum is :func:`anvilate.analysis.sheetmetal.minimum_bend_radius`, an empirical
    rule on the declared reduction of area. A radius under it fails. A radius over it is
    stated and not passed: the rule is a screen for the outer fibre cracking, and grain
    direction, edge condition and temper move the real limit.
    """
    name = f"{bracket.name} bend radius"
    if bracket.reduction_of_area_percent is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "not evaluated — the smallest radius this sheet bends to needs its "
                "reduction_of_area_percent, and none is assumed for a material"
            ),
            needs=(_NEEDS_A_REDUCTION_OF_AREA,),
        )
    minimum = minimum_bend_radius(
        thickness=bracket.thickness,
        reduction_of_area_percent=bracket.reduction_of_area_percent,
    )
    basis = (
        f"minimum {minimum.to('mm').magnitude:g} mm = thickness x (50 / "
        f"{bracket.reduction_of_area_percent:g} - 1), reduction of area from "
        f"{bracket.reduction_of_area_source}"
    )
    if bracket.inside_radius.to("mm").magnitude < minimum.to("mm").magnitude:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.FAIL,
            detail=(
                f"inside_radius {bracket.inside_radius} is under the smallest this sheet "
                f"bends to without cracking its outer fibre ({basis}). Raise inside_radius "
                "to the minimum or more, or bend a more ductile sheet"
            ),
        )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.NOT_EVALUATED,
        detail=(
            f"inside_radius {bracket.inside_radius} is at or over the empirical minimum "
            f"({basis}) — which is not a pass: grain direction, edge condition and temper "
            "move the real limit, and the shop's bend table decides it"
        ),
    )


def screen_enclosure(enclosure: Enclosure) -> Scorecard:
    """An enclosure is drawn and not checked."""
    return _drawn_not_checked("enclosure", str(enclosure.name))


def screen_enclosure_lid(lid: EnclosureLid) -> Scorecard:
    """An enclosure lid is drawn and not checked."""
    return _drawn_not_checked("enclosure lid", str(lid.name))
