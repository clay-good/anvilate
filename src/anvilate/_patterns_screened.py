"""Builders and registrations for elements a pack already screens and nothing drew.

Each draws from fields the element already declares, or from the bundled table its
designation names. Where the screen never needed a dimension the drawing does (how high a
lug's hole stands, which bearing this is), the element takes it as an optional field and
the build is refused, naming it, when it is absent: a shape is never guessed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from . import features, geometry
from ._patterns_parts import _X, _Y, _built, _low, _mm, _refuse, _ring
from .geometry import BuiltGeometry, GeometryError
from .packs.machinery import (
    HelicalCompressionSpring,
    RollingBearing,
    ShaftKey,
    SpurGearMesh,
)
from .packs.structural import BeamColumnMember, BeamMember, ColumnMember, LiftingLug
from .patterns import Pattern, register

__all__: list[str] = []


def _needs(element: str, field: str, what: str) -> GeometryError:
    return GeometryError(
        f"{element} is drawn from {what}, and this one does not state it; add "
        f"element_params.{field}",
        action="declare",
        subject=f"the {element} element_params.{field}",
        source=f"the drawing or catalog page the {element.replace('_', ' ')} was taken from",
    )


def build_lifting_lug(lug: LiftingLug, name: str, params: Mapping[str, Any]) -> BuiltGeometry:
    """A plate standing on z = 0 with a round top concentric with its pin hole."""
    from build123d import Align, Box, Cylinder, Pos, Rot

    geometry._kernel()
    tag = "lifting_lug"
    if lug.hole_height is None:
        raise _needs(tag, "hole_height", "the height of its pin hole above its base")
    width, thickness = _mm(lug.width, "width", tag), _mm(lug.thickness, "thickness", tag)
    hole = _mm(lug.hole_diameter, "hole_diameter", tag)
    height = _mm(lug.hole_height, "hole_height", tag)
    if hole >= width:
        raise _refuse(
            f"hole_diameter ({hole:g} mm) must be below width ({width:g} mm)",
            element=tag,
            field="hole_diameter",
        )
    body = Box(width, thickness, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    crown = Pos(0, 0, height) * Rot(90, 0, 0) * Cylinder(width / 2, thickness)
    host = features.Host(
        "the lug's face",
        (0.0, -thickness / 2, height),
        _X,
        (0.0, 0.0, 1.0),
        (0.0, -1.0, 0.0),
        thickness,
        radius=width / 2,
    )
    shape, cut = features.apply(body + crown, host, [features.through_hole("pin", 0.0, 0.0, hole)])
    dimensions = {
        "width": width,
        "thickness": thickness,
        "hole_diameter": hole,
        "hole_height": height,
        "height": height + width / 2,
    }
    return _built(lug, tag, shape, dimensions, cut)


def build_shaft_key(key: ShaftKey, name: str, params: Mapping[str, Any]) -> BuiltGeometry:
    """A parallel key lying on z = 0: its length along x, its width along y."""
    from build123d import Box

    geometry._kernel()
    tag = "shaft_key"
    width, height = _mm(key.key_width, "key_width", tag), _mm(key.key_height, "key_height", tag)
    length = _mm(key.key_length, "key_length", tag)
    dimensions = {"key_length": length, "key_width": width, "key_height": height}
    return _built(key, tag, Box(length, width, height, align=_low()), dimensions, name=name)


def build_spring(
    spring: HelicalCompressionSpring, name: str, params: Mapping[str, Any]
) -> BuiltGeometry:
    """An envelope: the tube a compression spring occupies at its free length."""
    geometry._kernel()
    tag = "helical_compression_spring"
    wire = _mm(spring.wire_diameter, "wire_diameter", tag)
    mean = _mm(spring.mean_coil_diameter, "mean_coil_diameter", tag)
    free = _mm(spring.free_length, "free_length", tag)
    if wire >= mean:
        raise _refuse(
            f"wire_diameter ({wire:g} mm) must be below mean_coil_diameter ({mean:g} mm)",
            element=tag,
            field="wire_diameter",
        )
    dimensions = {
        "outer_diameter": mean + wire,
        "inner_diameter": mean - wire,
        "free_length": free,
        "wire_diameter": wire,
    }
    shape = _ring(mean + wire, mean - wire, free)
    return _built(spring, tag, shape, dimensions, envelope=True, name=name)


def build_rolling_bearing(
    bearing: RollingBearing, name: str, params: Mapping[str, Any]
) -> BuiltGeometry:
    """An envelope: the ring a bearing occupies, from its ISO 15 boundary dimensions."""
    from .standards.bearings import default_bearing_table

    geometry._kernel()
    tag = "rolling_bearing"
    if bearing.designation is None:
        raise _needs(tag, "designation", "its catalog designation, such as 6204")
    table = default_bearing_table()
    if not table.has_bearing(bearing.designation):
        import difflib

        near = difflib.get_close_matches(bearing.designation, table.designations(), n=4)
        raise GeometryError(
            f"rolling_bearing: no bundled bearing is designated {bearing.designation!r}"
            + (f"; closest: {', '.join(near)}" if near else ""),
            action="select",
            subject="the rolling_bearing element_params.designation",
            source="the bundled ISO 15 deep-groove ball bearing table",
        )
    record = table.get(bearing.designation)
    bore = float(record.bore.quantity.to("mm").magnitude)
    outer = float(record.outer_diameter.quantity.to("mm").magnitude)
    width = float(record.width.quantity.to("mm").magnitude)
    dimensions = {"bore": bore, "outer_diameter": outer, "width": width}
    return _built(bearing, tag, _ring(outer, bore, width), dimensions, envelope=True, name=name)


def build_gear_mesh(mesh: SpurGearMesh, name: str, params: Mapping[str, Any]) -> BuiltGeometry:
    """An envelope: the pinion and the gear as their tip cylinders, at their centre distance.

    Standard full-depth proportions: tip diameter m(z + 2), root diameter m(z - 2.5), and a
    centre distance of m(z1 + z2)/2. The tooth form is not modelled.
    """
    from build123d import Cylinder, Pos

    geometry._kernel()
    tag = "spur_gear_mesh"
    module = _mm(mesh.module, "module", tag)
    face = _mm(mesh.face_width, "face_width", tag)
    pinion, gear = mesh.pinion_teeth, mesh.gear_teeth
    centre = module * (pinion + gear) / 2
    shape = Cylinder(module * (pinion + 2) / 2, face, align=_low()) + Pos(centre, 0, 0) * Cylinder(
        module * (gear + 2) / 2, face, align=_low()
    )
    dimensions = {
        "module": module,
        "face_width": face,
        "centre_distance": centre,
        "pinion_pitch_diameter": module * pinion,
        "pinion_tip_diameter": module * (pinion + 2),
        "pinion_root_diameter": module * (pinion - 2.5),
        "gear_pitch_diameter": module * gear,
        "gear_tip_diameter": module * (gear + 2),
        "gear_root_diameter": module * (gear - 2.5),
    }
    return _built(mesh, tag, shape, dimensions, envelope=True, name=name)


def _rolled_section(tag: str, params: Mapping[str, Any]) -> tuple[Any, dict[str, float]]:
    """The 2D outline of the member's named rolled profile, centred, and its dimensions."""
    from build123d import Circle, Pos, Rectangle

    from .standards.profiles import resolve_profile

    named = params.get("section")
    if not isinstance(named, str):
        raise GeometryError(
            f"{tag} is drawn from a named rolled profile, such as `section: IPE 200`; this "
            "one states its section properties, which do not say its shape",
            action="declare",
            subject=f"the {tag} element_params.section",
            source="the bundled rolled-profile table, by designation",
        )
    profile = resolve_profile(named)
    depth, flange, web, thick, root = (
        float(getattr(profile, field).quantity.to("mm").magnitude)
        for field in (
            "depth",
            "flange_width",
            "web_thickness",
            "flange_thickness",
            "root_radius",
        )
    )
    outline = Rectangle(web, depth - 2 * thick)
    for side in (1, -1):
        outline += Pos(0, side * (depth - thick) / 2) * Rectangle(flange, thick)
    if root > 0:
        for across in (1, -1):
            for up in (1, -1):
                corner = (across * (web / 2 + root / 2), up * (depth / 2 - thick - root / 2))
                centre = (across * (web / 2 + root), up * (depth / 2 - thick - root))
                outline += Pos(*corner) * Rectangle(root, root) - Pos(*centre) * Circle(root)
    dimensions = {
        "depth": depth,
        "flange_width": flange,
        "web_thickness": web,
        "flange_thickness": thick,
        "root_radius": root,
        "section_area": 2 * flange * thick + (depth - 2 * thick) * web + (4 - math.pi) * root**2,
    }
    return outline, dimensions


def _member(tag: str, upright: bool):
    def build(member: Any, name: str, params: Mapping[str, Any]) -> BuiltGeometry:
        from build123d import Plane, extrude

        geometry._kernel()
        outline, dimensions = _rolled_section(tag, params)
        length = _mm(member.length, "length", tag)
        # A beam lies along y with its web vertical; a column stands along z.
        plane = Plane.XY if upright else Plane.XZ
        shape = extrude(plane * outline, amount=length / 2, both=True)
        return _built(member, tag, shape, {**dimensions, "length": length}, name=name)

    return build


def _register(element_type: str, model: type, builder: Any, summary: str, **options: Any) -> None:
    register(
        Pattern(
            name=f"{element_type}/1",
            element_type=element_type,
            model=model,
            build=builder,
            summary=summary,
            example=f"parts/{element_type}.spec.yaml",
            **options,
        )
    )


_register(
    "lifting_lug",
    LiftingLug,
    build_lifting_lug,
    "A lifting lug (pad eye): a plate with a round top concentric with its pin hole.",
)
_register(
    "shaft_key", ShaftKey, build_shaft_key, "A parallel shaft key: a bar of its width and height."
)
_register(
    "helical_compression_spring",
    HelicalCompressionSpring,
    build_spring,
    "A helical compression spring, drawn as the tube it occupies at its free length.",
    envelope=True,
)
_register(
    "rolling_bearing",
    RollingBearing,
    build_rolling_bearing,
    "A deep-groove ball bearing, drawn as a ring from its ISO 15 boundary dimensions.",
    envelope=True,
)
_register(
    "spur_gear_mesh",
    SpurGearMesh,
    build_gear_mesh,
    "A spur gear pair, drawn as its two tip cylinders at their centre distance.",
    envelope=True,
)
_register(
    "beam_member",
    BeamMember,
    _member("beam_member", upright=False),
    "A beam cut to length from a named rolled I or H profile.",
    example_params={"section": "IPE 200"},
)
_register(
    "column_member",
    ColumnMember,
    _member("column_member", upright=True),
    "A column cut to length from a named rolled I or H profile.",
    example_params={"section": "IPE 200"},
)
_register(
    "beam_column_member",
    BeamColumnMember,
    _member("beam_column_member", upright=True),
    "A beam-column cut to length from a named rolled I or H profile.",
    example_params={"section": "IPE 200"},
)
del _Y
