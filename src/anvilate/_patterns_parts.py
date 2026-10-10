"""Builders and registrations for the everyday parts in :mod:`anvilate.packs.parts`.

Each builder takes the validated element and returns one valid solid with its faces tagged
by direction and its holes cut by :mod:`anvilate.features`. Nothing here cuts a hole of its
own: a bore that other holes must clear is declared as a feature too, so the same overlap
and edge checks cover it.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from . import features, geometry
from .geometry import BuiltGeometry, FlatProfile, GeometryError
from .packs import parts
from .patterns import Pattern, register

__all__: list[str] = []

_DIRECTIONS = {
    "top": (0.0, 0.0, 1.0),
    "bottom": (0.0, 0.0, -1.0),
    "right": (1.0, 0.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "front": (0.0, -1.0, 0.0),
}

_X, _Y, _Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def _refuse(message: str, *, element: str, field: str) -> GeometryError:
    return GeometryError(
        f"{element}: {message}",
        action="replace",
        subject=f"the {element} element_params.{field}",
        source=f"dimensions that describe one solid {element.replace('_', ' ')}",
    )


def _mm(value: Any, field: str, element: str) -> float:
    return geometry._positive_mm(value, field, element=element)


def _signed(value: Any) -> float:
    return 0.0 if value is None else float(value.to("mm").magnitude)


def _tag_faces(shape: Any) -> Mapping[str, tuple[Any, ...]]:
    """Name every face by what it is and which way it points, never by kernel order."""
    tagged: dict[str, list[Any]] = defaultdict(list)
    for face in shape.faces():
        kind = face.geom_type.name
        if kind == "PLANE":
            normal = face.normal_at()
            name = next(
                (
                    tag
                    for tag, (x, y, z) in _DIRECTIONS.items()
                    if normal.X * x + normal.Y * y + normal.Z * z > 0.999
                ),
                "inclined",
            )
        else:
            name = "round" if kind == "CYLINDER" else "curved"
        tagged[name].append(face)
    return MappingProxyType({name: tuple(faces) for name, faces in sorted(tagged.items())})


def _built(
    element: Any,
    element_type: str,
    shape: Any,
    dimensions: Mapping[str, float],
    cut: Sequence[features.Feature] = (),
    *,
    envelope: bool = False,
    name: str | None = None,
    profile: FlatProfile | None = None,
) -> BuiltGeometry:
    tags = [feature.tag for feature in cut]
    repeated = sorted({tag for tag in tags if tags.count(tag) > 1})
    if repeated:
        raise _refuse(
            f"these feature tags are used twice: {repeated}", element=element_type, field="holes"
        )
    built = BuiltGeometry(
        name=str(name if name is not None else element.name),
        pattern=f"{element_type}/1",
        shape=shape,
        faces=_tag_faces(shape),
        dimensions_mm=MappingProxyType(dict(dimensions)),
        features=tuple(cut),
        envelope=envelope,
        profile=profile,
    )
    if not built.is_valid:
        raise GeometryError(
            f"{element_type} did not produce one valid positive-volume solid; a feature "
            "may have cut the part in two",
            action="correct",
            subject=f"the {element_type} element_params",
            source="dimensions and features that leave one connected solid",
        )
    return built


# The bulge of a quarter-circle corner: the tangent of a quarter of ninety degrees.
_QUARTER = math.tan(math.pi / 8)


def _rounded_rectangle(
    width: float, height: float, radius: float
) -> tuple[tuple[float, float, float], ...]:
    """A centred rectangle as polyline vertices, its corners arcs of ``radius`` when it has one."""
    w, h = width / 2, height / 2
    if radius <= 0:
        return ((-w, -h, 0.0), (w, -h, 0.0), (w, h, 0.0), (-w, h, 0.0))
    r = radius
    return (
        (-w + r, -h, 0.0),
        (w - r, -h, _QUARTER),
        (w, -h + r, 0.0),
        (w, h - r, _QUARTER),
        (w - r, h, 0.0),
        (-w + r, h, _QUARTER),
        (-w, h - r, 0.0),
        (-w, -h + r, _QUARTER),
    )


def _flat_cuts(
    cut: Sequence[features.Feature], x: int = 0, y: int = 1
) -> tuple[
    tuple[tuple[float, float, float], ...], tuple[tuple[float, float, float, float, float], ...]
]:
    """The features of one face as the circles and slots of its flat profile.

    ``x`` and ``y`` are which of a feature's three coordinates lie in the profile's plane.
    A counterbore or a countersink is cut at its through diameter; the recess is machined.
    """
    circles, slots = [], []
    for feature in cut:
        at = (feature.position_mm[x], feature.position_mm[y])
        if feature.kind == "slot":
            slots.append(
                (*at, feature.extra["length"], feature.diameter_mm, feature.extra["angle_deg"])
            )
        elif feature.kind != "blind_hole":
            circles.append((*at, feature.diameter_mm))
    return tuple(circles), tuple(slots)


def _cuts(
    element: str,
    holes: Sequence[parts.Hole] = (),
    hole_patterns: Sequence[parts.HolePattern] = (),
    slots: Sequence[parts.Slot] = (),
) -> tuple[features.Cut, ...]:
    """The declared holes, patterns and slots as cuts in the shared feature library."""
    cuts: list[features.Cut] = []
    for hole in holes:
        tag, u, v = str(hole.tag), _signed(hole.x), _signed(hole.y)
        diameter = _mm(hole.diameter, "diameter", element)
        if hole.kind == "counterbore":
            cuts.append(
                features.counterbore(
                    tag,
                    u,
                    v,
                    diameter,
                    _mm(hole.counterbore_diameter, "counterbore_diameter", element),
                    _mm(hole.counterbore_depth, "counterbore_depth", element),
                )
            )
        elif hole.kind == "countersink":
            cuts.append(
                features.countersink(
                    tag, u, v, diameter, _mm(hole.head_diameter, "head_diameter", element)
                )
            )
        else:
            cuts.append(features.through_hole(tag, u, v, diameter, thread=hole.thread))
    for pattern in hole_patterns:
        tag = str(pattern.tag)
        diameter = _mm(pattern.diameter, "diameter", element)
        centre = (_signed(pattern.centre_x), _signed(pattern.centre_y))
        if pattern.kind == "bolt_circle":
            assert pattern.count is not None
            cuts += features.bolt_circle(
                tag,
                count=pattern.count,
                circle_diameter=_mm(pattern.circle_diameter, "circle_diameter", element),
                diameter=diameter,
                start_angle_deg=pattern.start_angle_deg,
                centre=centre,
                thread=pattern.thread,
            )
        else:
            assert pattern.count_x is not None and pattern.count_y is not None
            cuts += features.rectangular_pattern(
                tag,
                count_u=pattern.count_x,
                count_v=pattern.count_y,
                pitch_u=_signed(pattern.pitch_x),
                pitch_v=_signed(pattern.pitch_y),
                diameter=diameter,
                centre=centre,
                thread=pattern.thread,
            )
    for slot in slots:
        cuts.append(
            features.slot(
                str(slot.tag),
                _signed(slot.x),
                _signed(slot.y),
                _mm(slot.length, "length", element),
                _mm(slot.width, "width", element),
                angle_deg=slot.angle_deg,
            )
        )
    return tuple(cuts)


def _low():
    from build123d import Align

    return (Align.CENTER, Align.CENTER, Align.MIN)


def _ring(outer: float, inner: float, length: float) -> Any:
    from build123d import Cylinder

    return Cylinder(outer / 2, length, align=_low()) - Cylinder(inner / 2, length, align=_low())


def _inside(inner: float, outer: float, *, element: str, inner_field: str, outer_field: str):
    if inner >= outer:
        raise _refuse(
            f"{inner_field} ({inner:g} mm) must be below {outer_field} ({outer:g} mm)",
            element=element,
            field=inner_field,
        )


def build_mounting_plate(plate: parts.MountingPlate) -> BuiltGeometry:
    """A rectangular plate lying on z = 0, with its holes and slots cut from the top."""
    from build123d import Box

    geometry._kernel()
    tag = "mounting_plate"
    width, length = _mm(plate.width, "width", tag), _mm(plate.length, "length", tag)
    thickness = _mm(plate.thickness, "thickness", tag)
    shape = Box(width, length, thickness, align=_low())
    dimensions = {"width": width, "length": length, "thickness": thickness}
    if plate.corner_radius is not None:
        radius = _mm(plate.corner_radius, "corner_radius", tag)
        if radius >= min(width, length) / 2:
            raise _refuse(
                f"corner_radius ({radius:g} mm) must be below half the shorter side "
                f"({min(width, length) / 2:g} mm)",
                element=tag,
                field="corner_radius",
            )
        shape = features.round_corners(shape, radius)
        dimensions["corner_radius"] = radius
    host = features.Host(
        "the plate's top face", (0.0, 0.0, thickness), _X, _Y, _Z, thickness, width, length
    )
    shape, cut = features.apply(
        shape, host, _cuts(tag, plate.holes, plate.hole_patterns, plate.slots)
    )
    circles, slots = _flat_cuts(cut)
    profile = FlatProfile(
        outline=_rounded_rectangle(width, length, dimensions.get("corner_radius", 0.0)),
        circles=circles,
        slots=slots,
    )
    return _built(plate, tag, shape, dimensions, cut, profile=profile)


def build_angle_bracket(bracket: parts.AngleBracket) -> BuiltGeometry:
    """An L: the base leg along +x on z = 0, the upright along +z at x = 0."""
    from build123d import Align, Box, Plane, Polygon, Pos, extrude

    geometry._kernel()
    tag = "angle_bracket"
    base = _mm(bracket.base_length, "base_length", tag)
    height = _mm(bracket.upright_height, "upright_height", tag)
    width = _mm(bracket.width, "width", tag)
    thickness = _mm(bracket.thickness, "thickness", tag)
    for leg, field in ((base, "base_length"), (height, "upright_height")):
        _inside(thickness, leg, element=tag, inner_field="thickness", outer_field=field)
    corner = (Align.MIN, Align.CENTER, Align.MIN)
    shape = Box(base, width, thickness, align=corner) + Box(thickness, width, height, align=corner)
    dimensions = {
        "base_length": base,
        "upright_height": height,
        "width": width,
        "thickness": thickness,
    }
    base_cuts = _cuts(tag, bracket.base_holes, bracket.base_patterns, bracket.base_slots)
    upright_cuts = _cuts(
        tag, bracket.upright_holes, bracket.upright_patterns, bracket.upright_slots
    )
    clear_base, clear_upright = base - thickness, height - thickness
    if bracket.rib_thickness is not None:
        rib = _mm(bracket.rib_thickness, "rib_thickness", tag)
        leg = _mm(bracket.rib_leg, "rib_leg", tag)
        _inside(rib, width, element=tag, inner_field="rib_thickness", outer_field="width")
        if leg > min(clear_base, clear_upright):
            raise _refuse(
                f"rib_leg ({leg:g} mm) is longer than the shorter leg's inside length "
                f"({min(clear_base, clear_upright):g} mm)",
                element=tag,
                field="rib_leg",
            )
        # Each leg's holes are positioned from the centre of its clear inside face, where
        # the rib stands on the first `leg` from the corner, `rib` wide about the middle.
        for cuts, clear, along in ((base_cuts, clear_base, 0), (upright_cuts, clear_upright, 1)):
            for cut in cuts:
                reach = min(point[along] for point in cut.spine) - cut.radius
                across = [point[1 - along] for point in cut.spine]
                if (
                    reach < -clear / 2 + leg
                    and min(across) - cut.radius < rib / 2
                    and max(across) + cut.radius > -rib / 2
                ):
                    raise _refuse(
                        f"{cut.tag} runs into the stiffening rib", element=tag, field="rib_leg"
                    )
        triangle = Polygon(
            (thickness, thickness),
            (thickness + leg, thickness),
            (thickness, thickness + leg),
            align=None,
        )
        shape = shape + Pos(0, rib / 2, 0) * extrude(Plane.XZ * triangle, amount=rib)
        dimensions |= {"rib_thickness": rib, "rib_leg": leg}
    base_host = features.Host(
        "the base leg's inside face",
        (thickness + clear_base / 2, 0.0, thickness),
        _X,
        _Y,
        _Z,
        thickness,
        clear_base,
        width,
    )
    upright_host = features.Host(
        "the upright leg's inside face",
        (thickness, 0.0, thickness + clear_upright / 2),
        _Y,
        _Z,
        _X,
        thickness,
        width,
        clear_upright,
    )
    shape, cut_base = features.apply(shape, base_host, base_cuts)
    shape, cut_upright = features.apply(shape, upright_host, upright_cuts)
    return _built(bracket, tag, shape, dimensions, cut_base + cut_upright)


def build_plate_flange(flange: parts.PlateFlange) -> BuiltGeometry:
    """A disc on z = 0 with its bore and bolt circle cut from the top."""
    from build123d import Cylinder

    geometry._kernel()
    tag = "plate_flange"
    outer = _mm(flange.outer_diameter, "outer_diameter", tag)
    bore = _mm(flange.bore_diameter, "bore_diameter", tag)
    thickness = _mm(flange.thickness, "thickness", tag)
    circle = _mm(flange.bolt_circle_diameter, "bolt_circle_diameter", tag)
    hole = _mm(flange.bolt_hole_diameter, "bolt_hole_diameter", tag)
    _inside(bore, outer, element=tag, inner_field="bore_diameter", outer_field="outer_diameter")
    host = features.Host(
        "the flange face", (0.0, 0.0, thickness), _X, _Y, _Z, thickness, radius=outer / 2
    )
    cuts = (
        features.through_hole("bore", 0.0, 0.0, bore),
        *features.bolt_circle(
            "bolt", count=flange.bolt_count, circle_diameter=circle, diameter=hole
        ),
    )
    shape, cut = features.apply(Cylinder(outer / 2, thickness, align=_low()), host, cuts)
    dimensions = {
        "outer_diameter": outer,
        "bore_diameter": bore,
        "thickness": thickness,
        "bolt_circle_diameter": circle,
        "bolt_hole_diameter": hole,
    }
    profile = FlatProfile(diameter=outer, circles=_flat_cuts(cut)[0])
    return _built(flange, tag, shape, dimensions, cut, profile=profile)


def build_spacer(spacer: parts.Spacer) -> BuiltGeometry:
    """A plain ring standing on z = 0."""
    geometry._kernel()
    tag = "spacer"
    outer = _mm(spacer.outer_diameter, "outer_diameter", tag)
    inner = _mm(spacer.inner_diameter, "inner_diameter", tag)
    length = _mm(spacer.length, "length", tag)
    _inside(inner, outer, element=tag, inner_field="inner_diameter", outer_field="outer_diameter")
    dimensions = {"outer_diameter": outer, "inner_diameter": inner, "length": length}
    return _built(spacer, tag, _ring(outer, inner, length), dimensions)


def build_bushing(bushing: parts.Bushing) -> BuiltGeometry:
    """A sleeve standing on z = 0, its flange (when it has one) at the bottom."""
    geometry._kernel()
    tag = "bushing"
    outer = _mm(bushing.outer_diameter, "outer_diameter", tag)
    inner = _mm(bushing.inner_diameter, "inner_diameter", tag)
    length = _mm(bushing.length, "length", tag)
    _inside(inner, outer, element=tag, inner_field="inner_diameter", outer_field="outer_diameter")
    shape = _ring(outer, inner, length)
    dimensions = {"outer_diameter": outer, "inner_diameter": inner, "length": length}
    if bushing.flange_diameter is not None:
        flange = _mm(bushing.flange_diameter, "flange_diameter", tag)
        flange_thickness = _mm(bushing.flange_thickness, "flange_thickness", tag)
        _inside(
            outer, flange, element=tag, inner_field="outer_diameter", outer_field="flange_diameter"
        )
        _inside(
            flange_thickness,
            length,
            element=tag,
            inner_field="flange_thickness",
            outer_field="length",
        )
        shape = shape + _ring(flange, inner, flange_thickness)
        dimensions |= {"flange_diameter": flange, "flange_thickness": flange_thickness}
    return _built(bushing, tag, shape, dimensions)


def build_standoff(standoff: parts.Standoff) -> BuiltGeometry:
    """A hexagonal prism standing on z = 0 with a hole along its axis."""
    from build123d import RegularPolygon, extrude

    geometry._kernel()
    tag = "standoff"
    flats = _mm(standoff.across_flats, "across_flats", tag)
    length = _mm(standoff.length, "length", tag)
    hole = _mm(standoff.hole_diameter, "hole_diameter", tag)
    _inside(hole, flats, element=tag, inner_field="hole_diameter", outer_field="across_flats")
    prism = extrude(RegularPolygon(flats / 2, 6, major_radius=False), amount=length)
    host = features.Host(
        "the standoff's end face", (0.0, 0.0, length), _X, _Y, _Z, length, radius=flats / 2
    )
    shape, cut = features.apply(
        prism, host, [features.through_hole("hole", 0.0, 0.0, hole, thread=standoff.thread)]
    )
    dimensions = {"across_flats": flats, "length": length, "hole_diameter": hole}
    return _built(standoff, tag, shape, dimensions, cut)


def build_shaft_collar(collar: parts.ShaftCollar) -> BuiltGeometry:
    """A plain ring standing on z = 0."""
    geometry._kernel()
    tag = "shaft_collar"
    bore = _mm(collar.bore, "bore", tag)
    outer = _mm(collar.outer_diameter, "outer_diameter", tag)
    width = _mm(collar.width, "width", tag)
    _inside(bore, outer, element=tag, inner_field="bore", outer_field="outer_diameter")
    dimensions = {"bore": bore, "outer_diameter": outer, "width": width}
    shape = _ring(outer, bore, width)
    if collar.keyway_width is not None:
        from build123d import Align, Box

        key_width = _mm(collar.keyway_width, "keyway_width", tag)
        depth = _mm(collar.keyway_depth, "keyway_depth", tag)
        _inside(key_width, bore, element=tag, inner_field="keyway_width", outer_field="bore")
        if bore / 2 + depth >= outer / 2:
            raise _refuse(
                f"keyway_depth ({depth:g} mm) cuts through the collar's {(outer - bore) / 2:g} mm "
                "wall",
                element=tag,
                field="keyway_depth",
            )
        # From inside the bore out to `depth` beyond its surface on the +x side, where a
        # stepped shaft's keyways are milled.
        tool = Box(bore / 2 + depth, key_width, width, align=(Align.MIN, Align.CENTER, Align.MIN))
        shape = shape - tool
        dimensions |= {"keyway_width": key_width, "keyway_depth": depth}
    return _built(collar, tag, shape, dimensions)


def build_stepped_shaft(shaft: parts.SteppedShaft) -> BuiltGeometry:
    """Cylinders end to end along +z from the drive end, keyways milled on the +x side."""
    from build123d import Align, Axis, Box, Cylinder, Pos, chamfer

    geometry._kernel()
    tag = "stepped_shaft"
    steps = [
        (
            _mm(step.diameter, f"steps[{i}].diameter", tag),
            _mm(step.length, f"steps[{i}].length", tag),
        )
        for i, step in enumerate(shaft.steps)
    ]
    starts, shape, position = [], None, 0.0
    for diameter, length in steps:
        piece = Pos(0, 0, position) * Cylinder(diameter / 2, length, align=_low())
        shape = piece if shape is None else shape + piece
        starts.append(position)
        position += length
    dimensions = {"length": position, "largest_diameter": max(d for d, _ in steps)}
    for index, (diameter, length) in enumerate(steps, start=1):
        dimensions |= {f"step_{index}_diameter": diameter, f"step_{index}_length": length}
    if shaft.end_chamfer is not None:
        size = _mm(shaft.end_chamfer, "end_chamfer", tag)
        if size >= min(steps[0][0], steps[-1][0]) / 2 or size >= min(steps[0][1], steps[-1][1]):
            raise _refuse(
                f"end_chamfer ({size:g} mm) does not fit on the shaft's end steps",
                element=tag,
                field="end_chamfer",
            )
        ends = [
            edge
            for edge in shape.edges().filter_by(lambda e: e.geom_type.name == "CIRCLE")
            if min(abs(edge.center().Z), abs(edge.center().Z - position)) < 1e-6
        ]
        shape = chamfer(ends, size)
        dimensions["end_chamfer"] = size
    for number, keyway in enumerate(shaft.keyways, start=1):
        diameter, length = steps[keyway.step - 1]
        key_width = _mm(keyway.width, f"keyways[{number - 1}].width", tag)
        depth = _mm(keyway.depth, f"keyways[{number - 1}].depth", tag)
        key_length = _mm(keyway.length, f"keyways[{number - 1}].length", tag)
        offset = _signed(keyway.offset)
        field = f"keyways[{number - 1}]"
        if key_width >= diameter or depth >= diameter / 2:
            raise _refuse(
                f"keyway {number} ({key_width:g} mm wide, {depth:g} mm deep) does not fit a "
                f"{diameter:g} mm step",
                element=tag,
                field=field,
            )
        if offset < 0 or offset + key_length > length + 1e-9:
            raise _refuse(
                f"keyway {number} runs {offset + key_length:g} mm along a step {length:g} mm long",
                element=tag,
                field=field,
            )
        # The cutter reaches past the surface, so the flat bottom is `depth` below the
        # step's crown at the keyway's centreline.
        tool = Box(diameter, key_width, key_length, align=(Align.MIN, Align.CENTER, Align.MIN))
        shape = shape - Pos(diameter / 2 - depth, 0, starts[keyway.step - 1] + offset) * tool
        dimensions |= {
            f"keyway_{number}_width": key_width,
            f"keyway_{number}_depth": depth,
            f"keyway_{number}_length": key_length,
            # Where it is, for what seats in it: from the drive end, on this diameter.
            f"keyway_{number}_start": starts[keyway.step - 1] + offset,
            f"keyway_{number}_diameter": diameter,
        }
    del Axis
    return _built(shaft, tag, shape, dimensions)


def build_pulley(pulley: parts.Pulley) -> BuiltGeometry:
    """A disc on z = 0 turned about z, with one V groove centred in its rim."""
    from build123d import Axis, Plane, Polygon, revolve

    geometry._kernel()
    tag = "pulley"
    outer = _mm(pulley.outer_diameter, "outer_diameter", tag)
    bore = _mm(pulley.bore, "bore", tag)
    width = _mm(pulley.width, "width", tag)
    depth = _mm(pulley.groove_depth, "groove_depth", tag)
    top = _mm(pulley.groove_width, "groove_width", tag)
    angle = pulley.groove_angle_deg
    bottom = top - 2 * depth * math.tan(math.radians(angle) / 2)
    _inside(top, width, element=tag, inner_field="groove_width", outer_field="width")
    if bottom < 0:
        raise _refuse(
            f"a {angle:g} degree groove {top:g} mm wide closes before it is {depth:g} mm deep",
            element=tag,
            field="groove_depth",
        )
    if bore / 2 >= outer / 2 - depth:
        raise _refuse(
            f"the bore ({bore:g} mm) reaches the bottom of the groove "
            f"({outer - 2 * depth:g} mm across)",
            element=tag,
            field="bore",
        )
    r_in, r_out, mid = bore / 2, outer / 2, width / 2
    profile = [
        (r_in, 0.0),
        (r_out, 0.0),
        (r_out, mid - top / 2),
        (r_out - depth, mid - bottom / 2),
    ]
    if bottom > 1e-9:
        profile.append((r_out - depth, mid + bottom / 2))
    profile += [(r_out, mid + top / 2), (r_out, width), (r_in, width)]
    shape = revolve(Plane.XZ * Polygon(*profile, align=None), Axis.Z)
    dimensions = {
        "outer_diameter": outer,
        "bore": bore,
        "width": width,
        "groove_depth": depth,
        "groove_width": top,
        "root_diameter": outer - 2 * depth,
    }
    return _built(pulley, tag, shape, dimensions)


def build_clevis(clevis: parts.Clevis) -> BuiltGeometry:
    """A block on z = 0 slotted from the top along y, with a pin hole along x through both ears."""
    from build123d import Align, Box, Pos

    geometry._kernel()
    tag = "clevis"
    width, gap = _mm(clevis.width, "width", tag), _mm(clevis.gap, "gap", tag)
    depth, height = _mm(clevis.depth, "depth", tag), _mm(clevis.height, "height", tag)
    base = _mm(clevis.base_thickness, "base_thickness", tag)
    pin = _mm(clevis.pin_diameter, "pin_diameter", tag)
    pin_height = _mm(clevis.pin_height, "pin_height", tag)
    _inside(gap, width, element=tag, inner_field="gap", outer_field="width")
    _inside(base, height, element=tag, inner_field="base_thickness", outer_field="height")
    ear = height - base
    shape = Box(width, depth, height, align=_low()) - Pos(0, 0, base) * Box(
        gap, depth, ear, align=_low()
    )
    host = features.Host(
        "the ear's outside face",
        (width / 2, 0.0, base + ear / 2),
        _Y,
        _Z,
        _X,
        width,
        depth,
        ear,
    )
    shape, cut = features.apply(
        shape, host, [features.through_hole("pin", 0.0, pin_height - (base + ear / 2), pin)]
    )
    dimensions = {
        "width": width,
        "gap": gap,
        "depth": depth,
        "height": height,
        "base_thickness": base,
        "pin_diameter": pin,
        "pin_height": pin_height,
        "ear_thickness": (width - gap) / 2,
    }
    del Align
    return _built(clevis, tag, shape, dimensions, cut)


def build_tube(tube: parts.Tube) -> BuiltGeometry:
    """A round or rectangular tube standing on z = 0, its length along +z."""
    from build123d import Box

    geometry._kernel()
    tag = "tube"
    wall, length = _mm(tube.wall, "wall", tag), _mm(tube.length, "length", tag)
    if tube.shape == "round":
        outer = _mm(tube.outer_diameter, "outer_diameter", tag)
        _inside(2 * wall, outer, element=tag, inner_field="wall", outer_field="outer_diameter")
        shape = _ring(outer, outer - 2 * wall, length)
        dimensions = {"outer_diameter": outer, "wall": wall, "length": length}
    else:
        width, height = _mm(tube.width, "width", tag), _mm(tube.height, "height", tag)
        _inside(2 * wall, min(width, height), element=tag, inner_field="wall", outer_field="width")
        shape = Box(width, height, length, align=_low()) - Box(
            width - 2 * wall, height - 2 * wall, length, align=_low()
        )
        dimensions = {"width": width, "height": height, "wall": wall, "length": length}
    return _built(tube, tag, shape, dimensions)


def build_t_slot_extrusion(profile: parts.TSlotExtrusion) -> BuiltGeometry:
    """An envelope: the profile's square module with a groove where each T-slot opens.

    The module width and the slot's mouth are tabulated; the slot's inside is the vendor's,
    so the groove is drawn one mouth-width deep to show where the slot is and no more.
    """
    from build123d import Align, Box, Pos, Rot

    from .standards.extrusions import default_extrusion_table

    geometry._kernel()
    tag = "t_slot_extrusion"
    table = default_extrusion_table()
    if not table.has_profile(profile.designation):
        raise GeometryError(
            f"t_slot_extrusion: no bundled profile is named {profile.designation!r}; the "
            f"table carries {', '.join(table.designations())}",
            action="select",
            subject="the t_slot_extrusion element_params.designation",
            source="the bundled T-slot extrusion table",
        )
    record = table.get(profile.designation)
    side = float(record.profile_width.quantity.to("mm").magnitude)
    mouth = float(record.slot_width.quantity.to("mm").magnitude)
    length = _mm(profile.length, "length", tag)
    shape = Box(side, side, length, align=_low())
    groove = Pos(side / 2, 0, 0) * Box(
        mouth, mouth, length, align=(Align.MAX, Align.CENTER, Align.MIN)
    )
    for turn in (0, 90, 180, 270):
        shape = shape - Rot(0, 0, turn) * groove
    dimensions = {"profile_width": side, "slot_width": mouth, "length": length}
    return _built(profile, tag, shape, dimensions, envelope=True)


# Each bracket as a walk along its sheet: flange, quarter turn, flange. +1 turns left.
_WALKS = {"L": ((1.0, 0.0), (1,)), "U": ((0.0, -1.0), (1, 1)), "Z": ((1.0, 0.0), (1, -1))}


def build_sheet_metal_bracket(bracket: parts.SheetMetalBracket) -> BuiltGeometry:
    """The formed bracket: flat flanges joined by quarter bends of the stated inside radius."""
    from build123d import Align, Circle, Location, Plane, Pos, Rectangle, extrude

    geometry._kernel()
    tag = "sheet_metal_bracket"
    thickness = _mm(bracket.thickness, "thickness", tag)
    radius = _mm(bracket.inside_radius, "inside_radius", tag)
    width = _mm(bracket.width, "width", tag)
    straights = parts._straights(bracket)
    start, turns = _WALKS[bracket.shape]
    neutral, outer = radius + thickness / 2, radius + thickness
    position, heading = (0.0, 0.0), start
    sketch = None

    def add(piece: Any) -> None:
        nonlocal sketch
        sketch = piece if sketch is None else sketch + piece

    for index, straight in enumerate(straights):
        end = (position[0] + heading[0] * straight, position[1] + heading[1] * straight)
        angle = math.degrees(math.atan2(heading[1], heading[0]))
        add(
            Location(((position[0] + end[0]) / 2, (position[1] + end[1]) / 2, 0), (0, 0, angle))
            * Rectangle(straight, thickness)
        )
        position = end
        if index < len(turns):
            turn = turns[index]
            left = (-heading[1] * turn, heading[0] * turn)
            centre = (position[0] + left[0] * neutral, position[1] + left[1] * neutral)
            after = left
            # The bend fills the quarter between the point it starts at and the one it
            # ends at, seen from its centre: back along `left`, and back along the heading.
            quarter = Pos(
                centre[0] + (-left[0] + heading[0]) * outer / 2,
                centre[1] + (-left[1] + heading[1]) * outer / 2,
            ) * Rectangle(outer, outer)
            ring = Pos(*centre) * (Circle(outer) - Circle(radius))
            add(ring & quarter)
            position = (
                centre[0] + heading[0] * neutral,
                centre[1] + heading[1] * neutral,
            )
            heading = after
    # The sketch is moved to the origin before it is extruded, and never the solid after: a
    # solid carrying a placement is written to STEP as an assembly of one, not as a part.
    box = sketch.bounding_box()
    sketch = Pos(-box.min.X, -box.min.Y, 0) * sketch
    shape = extrude(Plane.XZ * sketch, amount=width / 2, both=True)
    dimensions = {
        "thickness": thickness,
        "inside_radius": radius,
        "width": width,
        **{
            name: _mm(getattr(bracket, name), name, tag)
            for name in ("flange_a", "flange_b", "flange_c")
            if getattr(bracket, name) is not None
        },
    }
    flat = parts.flat_pattern(bracket)
    profile = None
    if flat is not None:
        allowance = flat.bend_allowance.to("mm").magnitude
        developed = flat.developed_length.to("mm").magnitude
        dimensions["bend_allowance"] = allowance
        dimensions["flat_length"] = developed
        # The blank, laid out along x from one free edge, with a line down the middle of
        # each bend's allowance: where the brake's tool lands.
        lines, travelled = [], 0.0
        for straight in straights[:-1]:
            travelled += straight + allowance / 2
            lines.append(((travelled, -width / 2), (travelled, width / 2)))
            travelled += allowance / 2
        profile = FlatProfile(
            outline=(
                (0.0, -width / 2, 0.0),
                (developed, -width / 2, 0.0),
                (developed, width / 2, 0.0),
                (0.0, width / 2, 0.0),
            ),
            bends=tuple(lines),
        )
    del Align
    return _built(bracket, tag, shape, dimensions, profile=profile)


def build_enclosure(box: parts.Enclosure) -> BuiltGeometry:
    """An open-topped box on z = 0, its floor holes cut from the inside."""
    from build123d import Box, Pos

    geometry._kernel()
    tag = "enclosure"
    width, length = _mm(box.width, "width", tag), _mm(box.length, "length", tag)
    height, wall = _mm(box.height, "height", tag), _mm(box.wall, "wall", tag)
    floor = wall if box.floor is None else _mm(box.floor, "floor", tag)
    _inside(2 * wall, min(width, length), element=tag, inner_field="wall", outer_field="width")
    _inside(floor, height, element=tag, inner_field="floor", outer_field="height")
    outside = Box(width, length, height, align=_low())
    inside = Box(width - 2 * wall, length - 2 * wall, height - floor, align=_low())
    dimensions = {
        "width": width,
        "length": length,
        "height": height,
        "wall": wall,
        "floor": floor,
    }
    if box.corner_radius is not None:
        radius = _mm(box.corner_radius, "corner_radius", tag)
        if radius >= min(width, length) / 2:
            raise _refuse(
                f"corner_radius ({radius:g} mm) must be below half the shorter side "
                f"({min(width, length) / 2:g} mm)",
                element=tag,
                field="corner_radius",
            )
        outside = features.round_corners(outside, radius)
        if radius > wall:
            inside = features.round_corners(inside, radius - wall)
        dimensions["corner_radius"] = radius
    shape = outside - Pos(0, 0, floor) * inside
    host = features.Host(
        "the enclosure's floor",
        (0.0, 0.0, floor),
        _X,
        _Y,
        _Z,
        floor,
        width - 2 * wall,
        length - 2 * wall,
    )
    shape, cut = features.apply(shape, host, _cuts(tag, box.floor_holes, box.floor_patterns))
    return _built(box, tag, shape, dimensions, cut)


def build_enclosure_lid(lid: parts.EnclosureLid) -> BuiltGeometry:
    """A plate with its lip, if it has one, below it on z = 0; holes cut from the top."""
    from build123d import Box, Pos

    geometry._kernel()
    tag = "enclosure_lid"
    width, length = _mm(lid.width, "width", tag), _mm(lid.length, "length", tag)
    thickness = _mm(lid.thickness, "thickness", tag)
    dimensions = {"width": width, "length": length, "thickness": thickness}
    radius = 0.0
    if lid.corner_radius is not None:
        radius = _mm(lid.corner_radius, "corner_radius", tag)
        if radius >= min(width, length) / 2:
            raise _refuse(
                f"corner_radius ({radius:g} mm) must be below half the shorter side "
                f"({min(width, length) / 2:g} mm)",
                element=tag,
                field="corner_radius",
            )
        dimensions["corner_radius"] = radius

    def slab(inset: float, height: float) -> Any:
        box = Box(width - 2 * inset, length - 2 * inset, height, align=_low())
        return features.round_corners(box, radius - inset) if radius > inset else box

    shape, drop = slab(0.0, thickness), 0.0
    cuts = _cuts(tag, lid.holes, lid.hole_patterns)
    if lid.lip_height is not None:
        drop = _mm(lid.lip_height, "lip_height", tag)
        inset = _mm(lid.lip_inset, "lip_inset", tag)
        wall = _mm(lid.lip_wall, "lip_wall", tag)
        if 2 * (inset + wall) >= min(width, length):
            raise _refuse(
                f"lip_inset ({inset:g} mm) and lip_wall ({wall:g} mm) on both sides leave no "
                f"opening inside the lip across the shorter side ({min(width, length):g} mm)",
                element=tag,
                field="lip_wall",
            )
        # A hole is clear of the lip when it is wholly inside the lip's opening or wholly
        # outside its outer rectangle; the lip's round corners are read as square, which
        # refuses a little more than it must and never less.
        for cut in cuts:
            reach = [abs(cut.u) + cut.radius, abs(cut.v) + cut.radius]
            clear = [abs(cut.u) - cut.radius, abs(cut.v) - cut.radius]
            halves = [width / 2 - inset, length / 2 - inset]
            inside = all(r < half - wall for r, half in zip(reach, halves, strict=True))
            outside = any(c > half for c, half in zip(clear, halves, strict=True))
            if not (inside or outside):
                raise _refuse(f"{cut.tag} runs into the lip", element=tag, field="lip_inset")
        shape = Pos(0, 0, drop) * shape + (slab(inset, drop) - slab(inset + wall, drop))
        dimensions |= {"lip_inset": inset, "lip_wall": wall, "lip_height": drop}
    host = features.Host(
        "the lid's top face", (0.0, 0.0, drop + thickness), _X, _Y, _Z, thickness, width, length
    )
    shape, cut = features.apply(shape, host, cuts)
    return _built(lid, tag, shape, dimensions, cut)


def _register(element_type: str, model: type, builder: Any, summary: str, **options: Any) -> None:
    register(
        Pattern(
            name=f"{element_type}/1",
            element_type=element_type,
            model=model,
            build=lambda element, name, params: builder(element),
            summary=summary,
            example=f"parts/{element_type}.spec.yaml",
            **{"screened": False, **options},
        )
    )


_register(
    "mounting_plate",
    parts.MountingPlate,
    build_mounting_plate,
    "A flat rectangular plate with holes, hole patterns and slots, and optional round corners.",
    outputs=("views", "step", "3mf", "dxf"),
)
_register(
    "angle_bracket",
    parts.AngleBracket,
    build_angle_bracket,
    "An L bracket: two legs with holes and slots in each, and an optional stiffening rib.",
)
_register(
    "plate_flange",
    parts.PlateFlange,
    build_plate_flange,
    "A flat ring flange: a disc with a central bore and a circle of bolt holes.",
    outputs=("views", "step", "3mf", "dxf"),
)
_register("spacer", parts.Spacer, build_spacer, "A plain round spacer: a ring of one length.")
_register(
    "bushing",
    parts.Bushing,
    build_bushing,
    "A sleeve bushing, plain or with a flange at one end.",
)
_register(
    "standoff",
    parts.Standoff,
    build_standoff,
    "A hexagonal standoff with a hole along its axis, tapped as data.",
)
_register(
    "shaft_collar",
    parts.ShaftCollar,
    build_shaft_collar,
    "A plain shaft collar: a ring on a shaft.",
)
_register(
    "stepped_shaft",
    parts.SteppedShaft,
    build_stepped_shaft,
    "A solid round shaft of several diameters, with keyways and chamfered ends.",
)
_register(
    "pulley",
    parts.Pulley,
    build_pulley,
    "A V-belt pulley: a disc with a bore and one V groove in its rim.",
)
_register(
    "clevis",
    parts.Clevis,
    build_clevis,
    "A fork: a base and two ears with a pin hole through both, screened under a pin load.",
    screened=True,
)
_register("tube", parts.Tube, build_tube, "A straight round or rectangular tube cut to length.")
_register(
    "t_slot_extrusion",
    parts.TSlotExtrusion,
    build_t_slot_extrusion,
    "A T-slot aluminium extrusion cut to length, drawn as an envelope from its designation.",
    envelope=True,
)
_register(
    "sheet_metal_bracket",
    parts.SheetMetalBracket,
    build_sheet_metal_bracket,
    "A bracket bent from one sheet (L, U or Z), with its developed flat length.",
    outputs=("views", "step", "3mf", "flat_pattern"),
)
_register(
    "enclosure",
    parts.Enclosure,
    build_enclosure,
    "An open-topped box with a wall thickness, round corners and floor holes.",
)
_register(
    "enclosure_lid",
    parts.EnclosureLid,
    build_enclosure_lid,
    "A flat lid for an enclosure, with holes and an optional lip that drops into the box.",
)
