"""A project folder as context: what is in it, and measured facts from its CAD files.

add-agent-context-intake, groups 2 and 4. Every file here is written by the test that reads
it, with dimensions chosen so the expected answer is arithmetic: a 4 x 3 inch plate is
101.6 x 76.2 mm, a 10 unit cube has a volume of 1,000. The readers are held to four things:
what they report is the file's geometry, a unit is never assumed, a file is measured and
never returned, and nothing outside the folders named at launch is read.
"""

from __future__ import annotations

import json
import math
import os
import struct
import zipfile
from pathlib import Path

import pytest

from anvilate import context
from anvilate.context import ContextError, inventory, read_cad_file, resolve_in_context

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "parts"


def _disc(diameter: float) -> float:
    return math.pi * diameter**2 / 4


def _built(name: str):
    from anvilate.geometry import build_spec
    from anvilate.spec import load_spec_yaml

    return build_spec(load_spec_yaml((_EXAMPLES / f"{name}.spec.yaml").read_text("utf-8")))


def _step(folder: Path, name: str) -> Path:
    pytest.importorskip("build123d")
    from anvilate.export.gate import authorize_export
    from anvilate.geometry import write_step

    return write_step(
        _built(name), folder / f"{name}.step", authorization=authorize_export(None, override=True)
    )


def _cube_stl(path: Path, side: float = 10.0, *, drop: int = 0) -> Path:
    """A closed cube as a binary STL, twelve triangles, or fewer to leave it open."""
    v = [(x, y, z) for x in (0.0, side) for y in (0.0, side) for z in (0.0, side)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    triangles = [t for a, b, c, d in quads for t in ((v[a], v[b], v[c]), (v[a], v[c], v[d]))]
    triangles = triangles[: len(triangles) - drop]
    data = b"\0" * 80 + struct.pack("<I", len(triangles))
    for a, b, c in triangles:
        data += struct.pack("<12fH", 0, 0, 0, *a, *b, *c, 0)
    path.write_bytes(data)
    return path


def _plate_dxf(path: Path, *, units: int = 1) -> Path:
    """A 4 x 3 plate with four 0.25 holes 0.5 in from each edge, and a slot drawn as lines."""
    ezdxf = pytest.importorskip("ezdxf")
    document = ezdxf.new()
    document.header["$INSUNITS"] = units
    space = document.modelspace()
    document.layers.add("OUTLINE")
    space.add_lwpolyline(
        [(0, 0), (4, 0), (4, 3), (0, 3)], close=True, dxfattribs={"layer": "OUTLINE"}
    )
    for x, y in ((0.5, 0.5), (3.5, 0.5), (3.5, 2.5), (0.5, 2.5)):
        space.add_circle((x, y), 0.125)
    # A second outline drawn the way a draughtsman draws one: three lines and an arc.
    space.add_line((6, 0), (8, 0))
    space.add_line((8, 0), (8, 1))
    space.add_arc((7, 1), 1, 0, 180)
    space.add_line((6, 1), (6, 0))
    space.add_linear_dim(base=(2, -1), p1=(0, 0), p2=(4, 0)).render()
    space.add_linear_dim(base=(2, 4), p1=(0, 3), p2=(4, 3), text="4.25").render()
    space.add_line((20, 20), (21, 21))
    document.saveas(path)
    return path


# --- the inventory ---------------------------------------------------------------------


def test_a_folder_is_listed_with_whose_each_file_is(tmp_path):
    for name in ("plate.step", "outline.DXF", "scan.stl", "print.3mf", "sketch.png", "sheet.pdf"):
        (tmp_path / name).write_bytes(b"x" * 7)
    (tmp_path / "old.dwg").write_bytes(b"AC1027")
    (tmp_path / "part.SLDPRT").write_bytes(b"")
    (tmp_path / "notes.xyz").write_text("ignored")
    (tmp_path / ".hidden.step").write_bytes(b"")
    listing = inventory(tmp_path)
    by_name = {file.path: file for file in listing.files}
    assert {name: file.reader for name, file in by_name.items()} == {
        "plate.step": "anvilate",
        "outline.DXF": "anvilate",
        "scan.stl": "anvilate",
        "print.3mf": "anvilate",
        "sketch.png": "agent",
        "sheet.pdf": "agent",
        "old.dwg": "unsupported",
        "part.SLDPRT": "unsupported",
    }
    assert by_name["plate.step"].bytes == 7 and by_name["plate.step"].note is None
    assert by_name["old.dwg"].note == "export DXF from the CAD tool that wrote it"
    assert "export STEP" in by_name["part.SLDPRT"].note
    assert (listing.other_files, listing.not_listed) == (1, 0)
    text = str(listing)
    assert "8 engineering files" in text and "1 files of other kinds are not listed" in text
    assert "note" not in by_name["plate.step"].model_dump()


def test_the_listing_is_bounded_and_counts_what_it_left_out(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "_INVENTORY_FILES", 5)
    for index in range(9):
        (tmp_path / f"part{index}.step").write_bytes(b"")
    deep = tmp_path / "a" / "b" / "c" / "d" / "e"
    deep.mkdir(parents=True)
    (deep / "buried.step").write_bytes(b"")
    (tmp_path / "a" / "near.dxf").write_bytes(b"")
    listing = inventory(tmp_path)
    assert len(listing.files) == 5
    # Four past the limit at the top, and the one below the depth it descends to; the
    # near one would be the sixth and is counted too.
    assert listing.not_listed == 4 + 1 + 1
    assert "more past the listing limit" in str(listing)
    with pytest.raises(ContextError, match="is not a folder"):
        inventory(tmp_path / "missing")


def test_listing_opens_nothing(tmp_path, monkeypatch):
    (tmp_path / "plate.step").write_bytes(b"not a step file at all")

    def opened(*_args, **_kwargs):
        raise AssertionError("the inventory read a file")

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(Path, "read_bytes", opened)
    assert inventory(tmp_path).files[0].format == "STEP solid model"


# --- STEP ------------------------------------------------------------------------------


def test_a_step_part_is_read_as_its_holes_and_its_bolt_circle(tmp_path):
    path = _step(tmp_path, "plate_flange")
    facts = read_cad_file(path)
    assert (facts.kind, facts.unit_written, facts.unit_reported) == ("step", "mm", "mm")
    assert facts.size_mm == (120.0, 120.0, 12.0) and facts.products == ("pump-plate-flange",)
    assert facts.volume_mm3 == pytest.approx((_disc(120) - _disc(50) - 6 * _disc(9)) * 12, rel=1e-6)
    (solid,) = facts.solids
    assert solid.unclassified_faces == 0 and solid.faces == 10
    holes = [c for c in solid.cylinders if c.kind == "hole"]
    assert sorted(c.diameter_mm for c in holes) == [9.0] * 6 + [50.0]
    assert all(c.depth_mm == 12.0 and c.axis == (0.0, 0.0, 1.0) for c in holes)
    assert [(c.kind, c.diameter_mm) for c in solid.cylinders if c.kind != "hole"] == [
        ("boss", 120.0)
    ]
    (pattern,) = solid.hole_patterns
    assert (pattern.count, pattern.diameter_mm, pattern.bolt_circle_diameter_mm) == (6, 9.0, 90.0)
    assert pattern.pitch_mm == pytest.approx(45.0, abs=1e-6)  # the chord between neighbours
    assert [plane.normal for plane in solid.planes] == [(0.0, 0.0, -1.0), (0.0, 0.0, 1.0)]
    assert solid.planes[0].area_mm2 == pytest.approx(
        _disc(120) - _disc(50) - 6 * _disc(9), rel=1e-6
    )


def test_the_file_is_cited_and_never_returned(tmp_path):
    import hashlib

    path = _step(tmp_path, "spacer")
    facts = read_cad_file(path)
    assert facts.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert facts.bytes == path.stat().st_size and facts.file == "spacer.step"
    written = facts.model_dump_json()
    assert "CARTESIAN_POINT" not in written and "ADVANCED_FACE" not in written
    assert len(written) < 4000
    assert type(facts).model_validate_json(written) == facts


def test_a_partial_round_is_not_called_a_hole_or_a_boss(tmp_path):
    """A plate's rounded corners are quarter cylinders and a slot's ends are half cylinders.
    Reported as bosses and holes they were four 16 mm bosses and two 6 mm holes nobody drew."""
    (solid,) = read_cad_file(_step(tmp_path, "mounting_plate")).solids
    kinds = {}
    for cylinder in solid.cylinders:
        kinds.setdefault((cylinder.kind, cylinder.diameter_mm), []).append(cylinder)
    assert len(kinds[("round", 16.0)]) == 4  # the 8 mm corner radii
    assert len(kinds[("fillet", 6.0)]) == 2  # the two ends of the 6 mm slot
    assert len(kinds[("hole", 6.6)]) == 5 and len(kinds[("hole", 11.0)]) == 1
    assert not any(kind == "boss" for kind, _diameter in kinds)
    patterns = {(p.count, p.diameter_mm) for p in solid.hole_patterns}
    assert patterns == {(5, 6.6)}


def test_a_hole_built_from_two_half_cylinders_is_one_hole(tmp_path):
    pytest.importorskip("build123d")
    from build123d import Align, Box, Cylinder, Solid, export_step
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse

    # Two blocks, each with the hole cut through its inner face, fused by the kernel's own
    # operation with no face merging afterwards: the hole is left as two half-cylinders.
    low = (Align.CENTER, Align.CENTER, Align.MIN)
    halves = [
        Box(20, 40, 10, align=(side, Align.CENTER, Align.MIN)).cut(Cylinder(5, 10, align=low))
        for side in (Align.MIN, Align.MAX)
    ]
    block = Solid(BRepAlgoAPI_Fuse(halves[0].wrapped, halves[1].wrapped).Shape())
    path = tmp_path / "split.step"
    export_step(block, str(path))
    (solid,) = read_cad_file(path).solids
    cylindrical = sum(1 for face in block.faces() if face.geom_type.name == "CYLINDER")
    assert cylindrical == 2, "the fixture no longer splits the hole, so this checks nothing"
    (hole,) = solid.cylinders
    assert (hole.kind, hole.diameter_mm, hole.depth_mm) == ("hole", 10.0, 10.0)
    assert hole.position_mm == (0.0, 0.0, 5.0)


def test_an_inch_file_is_not_silently_millimetres(tmp_path):
    pytest.importorskip("build123d")
    from build123d import Box
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import (
        STEPControl_Controller,
        STEPControl_StepModelType,
        STEPControl_Writer,
    )

    STEPControl_Controller.Init_s()
    before = Interface_Static.CVal_s("write.step.unit")
    Interface_Static.SetCVal_s("write.step.unit", "INCH")
    try:
        writer = STEPControl_Writer()
        writer.Transfer(Box(50.8, 25.4, 12.7).wrapped, STEPControl_StepModelType.STEPControl_AsIs)
        writer.Write(str(tmp_path / "inch.step"))
    finally:
        Interface_Static.SetCVal_s("write.step.unit", before)
    assert "INCH" in (tmp_path / "inch.step").read_text().upper()
    facts = read_cad_file(tmp_path / "inch.step")
    assert (facts.unit_written, facts.unit_reported) == ("in", "mm")
    assert facts.size_mm == pytest.approx((50.8, 25.4, 12.7), abs=1e-6)
    assert facts.volume_mm3 == pytest.approx(50.8 * 25.4 * 12.7, rel=1e-9)
    assert any("written in inches" in note and "converted to mm" in note for note in facts.notes)
    with pytest.raises(ContextError, match="declares its unit as in, and the call states mm"):
        read_cad_file(tmp_path / "inch.step", unit="mm")


def test_a_file_with_no_solid_is_refused_with_what_it_holds(tmp_path):
    pytest.importorskip("build123d")
    from build123d import Rectangle, export_step

    export_step(Rectangle(10, 10), str(tmp_path / "surface.step"))
    with pytest.raises(ContextError, match="holds no solid: it has 1 faces"):
        read_cad_file(tmp_path / "surface.step")
    (tmp_path / "junk.step").write_text("this is not ISO 10303-21")
    with pytest.raises(ContextError):
        read_cad_file(tmp_path / "junk.step")


def test_two_bodies_are_two_solids(tmp_path):
    pytest.importorskip("build123d")
    from build123d import Box, Compound, Pos, export_step

    export_step(
        Compound([Box(10, 10, 10), Pos(50, 0, 0) * Box(20, 20, 20)]), str(tmp_path / "two.step")
    )
    facts = read_cad_file(tmp_path / "two.step")
    assert sorted(solid.volume_mm3 for solid in facts.solids) == [1000.0, 8000.0]
    assert facts.volume_mm3 == 9000.0 and any("2 solids" in note for note in facts.notes)


# --- DXF -------------------------------------------------------------------------------


def test_a_drawing_in_inches_is_read_in_millimetres_with_its_holes(tmp_path):
    facts = read_cad_file(_plate_dxf(tmp_path / "plate.dxf"))
    assert (facts.kind, facts.unit_written, facts.unit_reported) == ("dxf", "in", "mm")
    plate, tab = facts.profiles
    assert (plate.kind, plate.layer, plate.width_mm, plate.height_mm) == (
        "rectangle",
        "OUTLINE",
        101.6,
        76.2,
    )
    assert plate.area_mm2 == pytest.approx(101.6 * 76.2, rel=1e-9)
    # Four 0.25 in holes, 1.5 in and 1.0 in from the plate's centre.
    assert [(hole.kind, hole.diameter_mm, hole.x_mm, hole.y_mm) for hole in plate.holes] == [
        ("circle", 6.35, -38.1, -25.4),
        ("circle", 6.35, -38.1, 25.4),
        ("circle", 6.35, 38.1, -25.4),
        ("circle", 6.35, 38.1, 25.4),
    ]
    assert "OUTLINE" in facts.layers
    assert any("drawn in inches" in note for note in facts.notes)
    assert facts.open_entities == 1  # the stray line that closes nothing


def test_an_outline_drawn_as_separate_lines_and_an_arc_is_one_profile(tmp_path):
    _plate, tab = read_cad_file(_plate_dxf(tmp_path / "plate.dxf")).profiles
    # A 2 x 1 inch rectangle with a 1 inch radius half disc on top.
    assert (tab.kind, tab.width_mm, tab.height_mm) == ("profile", 50.8, 50.8)
    assert tab.area_mm2 == pytest.approx((2 * 1 + math.pi / 2) * 25.4**2, rel=1e-4)


def test_a_dimension_whose_text_disagrees_with_its_geometry_is_flagged(tmp_path):
    facts = read_cad_file(_plate_dxf(tmp_path / "plate.dxf"))
    honest, typed = sorted(facts.dimensions, key=lambda d: d.override or "")
    assert (honest.measured_mm, honest.override, honest.disagrees) == (101.6, None, False)
    assert (typed.measured_mm, typed.override, typed.disagrees) == (101.6, "4.25", True)
    assert any("does not match what it measures" in note for note in facts.notes)
    assert "DISAGREES" in str(facts)


def test_an_override_that_says_what_the_geometry_says_is_not_flagged(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    document = ezdxf.new()
    document.header["$INSUNITS"] = 1
    space = document.modelspace()
    space.add_linear_dim(base=(2, -1), p1=(0, 0), p2=(4, 0), text="4.000 TYP").render()
    space.add_linear_dim(base=(2, -2), p1=(0, 0), p2=(4, 0), text="101.6 mm").render()
    space.add_linear_dim(base=(2, -3), p1=(0, 0), p2=(4, 0), text="SEE NOTE").render()
    document.saveas(tmp_path / "dims.dxf")
    dimensions = read_cad_file(tmp_path / "dims.dxf").dimensions
    assert [d.override for d in dimensions] == ["4.000 TYP", "101.6 mm", "SEE NOTE"]
    assert not any(d.disagrees for d in dimensions)


def test_a_drawing_with_no_unit_is_not_assumed_to_be_millimetres(tmp_path):
    path = _plate_dxf(tmp_path / "bare.dxf", units=0)
    with pytest.raises(ContextError, match="declares no drawing unit") as refused:
        read_cad_file(path)
    assert refused.value.remedies[0].subject == "unit"
    as_inches, as_mm = read_cad_file(path, unit="in"), read_cad_file(path, unit="mm")
    assert as_inches.profiles[0].width_mm == 101.6 and as_mm.profiles[0].width_mm == 4.0
    assert as_inches.unit_written is None
    assert any("declares no unit; read as inches" in note for note in as_inches.notes)
    with pytest.raises(ContextError, match="declares its unit as in"):
        read_cad_file(_plate_dxf(tmp_path / "inch.dxf"), unit="mm")
    with pytest.raises(ContextError, match="is not one of"):
        read_cad_file(path, unit="furlong")


def test_a_block_is_read_at_the_scale_it_was_inserted_at(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    document = ezdxf.new()
    document.header["$INSUNITS"] = 4
    block = document.blocks.new("PAD")
    block.add_lwpolyline([(0, 0), (10, 0), (10, 5), (0, 5)], close=True)
    block.add_circle((5, 2.5), 1)
    document.modelspace().add_blockref("PAD", (100, 100), dxfattribs={"xscale": 3, "yscale": 3})
    document.saveas(tmp_path / "block.dxf")
    (pad,) = read_cad_file(tmp_path / "block.dxf").profiles
    assert (pad.width_mm, pad.height_mm) == (30.0, 15.0)
    (hole,) = pad.holes
    assert (hole.diameter_mm, hole.x_mm, hole.y_mm) == (6.0, 0.0, 0.0)


def test_a_file_that_is_not_a_drawing_is_refused(tmp_path):
    pytest.importorskip("ezdxf")
    (tmp_path / "broken.dxf").write_text("0\nSECTION\nnot a drawing")
    with pytest.raises(ContextError, match="is not a DXF file this reader can open"):
        read_cad_file(tmp_path / "broken.dxf")


# --- meshes ----------------------------------------------------------------------------


def test_a_mesh_gives_a_size_and_a_volume_and_claims_nothing_else(tmp_path):
    facts = read_cad_file(_cube_stl(tmp_path / "cube.stl"))
    assert (facts.kind, facts.triangles, facts.closed) == ("mesh", 12, True)
    assert (facts.unit_written, facts.unit_reported) == (None, "file units")
    assert facts.size_mm == (10.0, 10.0, 10.0) and facts.volume_mm3 == 1000.0
    assert not facts.solids and not facts.profiles
    assert any("no faces, holes or design intent" in note for note in facts.notes)
    assert any("states no unit" in note for note in facts.notes)
    in_inches = read_cad_file(tmp_path / "cube.stl", unit="in")
    assert in_inches.unit_reported == "mm" and in_inches.size_mm == (254.0, 254.0, 254.0)
    assert in_inches.volume_mm3 == pytest.approx(1000 * 25.4**3, rel=1e-12)


def test_an_open_mesh_encloses_no_volume(tmp_path):
    facts = read_cad_file(_cube_stl(tmp_path / "open.stl", drop=2))
    assert facts.closed is False and facts.volume_mm3 is None and facts.triangles == 10
    assert any("not closed" in note for note in facts.notes)
    assert "not closed" in str(facts)


def test_an_ascii_stl_reads_the_same_as_a_binary_one(tmp_path):
    lines = ["solid tetra"]
    points = [(0, 0, 0), (6, 0, 0), (0, 6, 0), (0, 0, 6)]
    for a, b, c in ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)):
        lines += ["facet normal 0 0 0", "outer loop"]
        lines += [f"vertex {x} {y} {z}" for x, y, z in (points[a], points[b], points[c])]
        lines += ["endloop", "endfacet"]
    (tmp_path / "tetra.stl").write_text("\n".join([*lines, "endsolid tetra"]))
    facts = read_cad_file(tmp_path / "tetra.stl")
    assert (facts.triangles, facts.closed, facts.volume_mm3) == (4, True, 36.0)
    (tmp_path / "bad.stl").write_text("solid x\nvertex 1 2 three\nendsolid")
    with pytest.raises(ContextError, match="not three numbers"):
        read_cad_file(tmp_path / "bad.stl")
    (tmp_path / "empty.stl").write_text("solid nothing\nendsolid nothing\n")
    with pytest.raises(ContextError, match="holds no triangles"):
        read_cad_file(tmp_path / "empty.stl")


def test_a_3mf_states_its_unit_and_is_read_in_millimetres(tmp_path):
    pytest.importorskip("build123d")
    from anvilate.export.gate import authorize_export
    from anvilate.geometry import render_3mf

    built = _built("spacer")
    (tmp_path / "spacer.3mf").write_bytes(
        render_3mf(built, authorization=authorize_export(None, override=True))
    )
    facts = read_cad_file(tmp_path / "spacer.3mf")
    assert (facts.kind, facts.unit_written, facts.unit_reported, facts.closed) == (
        "mesh",
        "mm",
        "mm",
        True,
    )
    assert facts.size_mm == pytest.approx((12.0, 12.0, 10.0), abs=0.01)
    # A faceted ring is a little smaller than the round one it approximates.
    assert facts.volume_mm3 == pytest.approx(built.volume_mm3, rel=5e-3)
    with pytest.raises(ContextError, match="declares its unit as mm"):
        read_cad_file(tmp_path / "spacer.3mf", unit="in")


def _model(body: str, unit: str = "inch") -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<model unit="{unit}" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources><object id="1" type="model"><mesh>{body}</mesh></object></resources></model>'
    ).encode()


_TETRA = (
    "<vertices>"
    '<vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/>'
    '<vertex x="0" y="1" z="0"/><vertex x="0" y="0" z="1"/>'
    "</vertices><triangles>"
    '<triangle v1="0" v2="2" v3="1"/><triangle v1="0" v2="1" v3="3"/>'
    '<triangle v1="0" v2="3" v3="2"/><triangle v1="1" v2="2" v3="3"/>'
    "</triangles>"
)


def _package(path: Path, data: bytes | None) -> Path:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        if data is not None:
            package.writestr("3D/3dmodel.model", data)
    return path


def test_a_3mf_in_inches_is_converted(tmp_path):
    facts = read_cad_file(_package(tmp_path / "tetra.3mf", _model(_TETRA)))
    assert facts.unit_written == "in" and facts.size_mm == (25.4, 25.4, 25.4)
    assert facts.volume_mm3 == pytest.approx(25.4**3 / 6, rel=1e-9)


@pytest.mark.parametrize(
    "data",
    [
        None,
        b"not xml at all",
        b'<?xml version="1.0"?><!DOCTYPE model [<!ENTITY a "aaaa">]><model>&a;</model>',
        _model(_TETRA.replace('v3="3"/></tri', 'v3="9"/></tri')),
        # A negative index reads from the end of a Python list instead of failing.
        _model(_TETRA.replace('v1="0" v2="2"', 'v1="-1" v2="2"')),
        _model(_TETRA.replace('x="1"', 'x="nan"')),
        _model(_TETRA, unit="parsec"),
    ],
)
def test_a_3mf_that_is_not_a_mesh_package_is_refused(tmp_path, data):
    with pytest.raises(ContextError):
        read_cad_file(_package(tmp_path / "bad.3mf", data))
    (tmp_path / "plain.3mf").write_bytes(b"not a zip")
    with pytest.raises(ContextError, match="not a readable 3MF"):
        read_cad_file(tmp_path / "plain.3mf")


def test_a_package_that_unpacks_past_the_limit_is_not_inflated(tmp_path, monkeypatch):
    """A package is small on disk and can hold anything: 6 kB of padding deflates to a few
    bytes. The member's declared size is checked before it is read."""
    path = tmp_path / "bomb.3mf"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("3D/3dmodel.model", _model(_TETRA) + b" " * 6000)
    assert path.stat().st_size < 1000
    monkeypatch.setattr(context, "MAX_BYTES", {**context.MAX_BYTES, "mesh": 1000})
    inflated = []
    monkeypatch.setattr(zipfile.ZipFile, "read", lambda *a, **k: inflated.append(a) or b"")
    with pytest.raises(ContextError, match="unpacks to 0 MB, past what one read accepts"):
        read_cad_file(path)
    assert not inflated


# --- what is not read ------------------------------------------------------------------


@pytest.mark.parametrize("suffix", sorted(context._UNSUPPORTED))
def test_a_format_that_needs_converting_is_refused_with_the_step_that_fixes_it(tmp_path, suffix):
    path = tmp_path / f"model{suffix.upper()}"
    path.write_bytes(b"\x00binary")
    fmt, fix = context._UNSUPPORTED[suffix]
    with pytest.raises(ContextError) as refused:
        read_cad_file(path)
    message = str(refused.value)
    assert fmt in message and fix in message and "does not convert" in message
    assert ("export DXF" in fix) == (suffix == ".dwg")


def test_a_picture_is_the_agents_to_read_and_an_unknown_file_is_nobodys(tmp_path):
    (tmp_path / "sketch.png").write_bytes(b"\x89PNG")
    with pytest.raises(ContextError, match="is the agent's to read.*agent-read"):
        read_cad_file(tmp_path / "sketch.png")
    (tmp_path / "data.bin").write_bytes(b"")
    with pytest.raises(ContextError, match="reads STEP, DXF, STL and 3MF"):
        read_cad_file(tmp_path / "data.bin")
    with pytest.raises(ContextError, match="is not a file"):
        read_cad_file(tmp_path / "missing.step")


def test_a_file_past_the_size_one_call_reads_is_refused_with_its_size(tmp_path, monkeypatch):
    path = _cube_stl(tmp_path / "cube.stl")
    monkeypatch.setattr(context, "MAX_BYTES", {**context.MAX_BYTES, "mesh": 100})
    with pytest.raises(ContextError, match="past the 0 MB a mesh read accepts"):
        read_cad_file(path)
    monkeypatch.setattr(context, "_MAX_TRIANGLES", 5)
    monkeypatch.setattr(context, "MAX_BYTES", {**context.MAX_BYTES, "mesh": 10**6})
    with pytest.raises(ContextError, match="holds 12 triangles, past the 5"):
        read_cad_file(path)


# --- confinement -----------------------------------------------------------------------


def test_with_no_context_folder_nothing_is_read(tmp_path):
    _cube_stl(tmp_path / "cube.stl")
    assert context.context_roots() == ()
    with pytest.raises(ContextError, match="started without a context folder") as refused:
        resolve_in_context(tmp_path / "cube.stl")
    assert refused.value.remedies[0].subject == "--context"


def test_a_path_outside_the_context_is_refused_naming_the_folders(tmp_path):
    inside, outside = tmp_path / "project", tmp_path / "elsewhere"
    inside.mkdir()
    outside.mkdir()
    _cube_stl(inside / "cube.stl")
    _cube_stl(outside / "secret.stl")
    context.set_context_roots([inside])
    assert resolve_in_context("cube.stl") == (inside / "cube.stl").resolve()
    assert resolve_in_context(inside / "cube.stl") == (inside / "cube.stl").resolve()
    assert resolve_in_context(".") == inside.resolve()
    for escape in (outside / "secret.stl", "../elsewhere/secret.stl", "/etc/hosts", "missing.stl"):
        with pytest.raises(ContextError, match="reads only inside") as refused:
            resolve_in_context(escape)
        assert str(inside.resolve()) in str(refused.value)


def test_a_link_that_points_outside_the_context_is_outside(tmp_path):
    inside, outside = tmp_path / "project", tmp_path / "elsewhere"
    inside.mkdir()
    outside.mkdir()
    _cube_stl(outside / "secret.stl")
    os.symlink(outside / "secret.stl", inside / "innocent.stl")
    os.symlink(outside, inside / "shortcut")
    context.set_context_roots([inside])
    for path in ("innocent.stl", "shortcut/secret.stl", "shortcut"):
        with pytest.raises(ContextError, match="reads only inside"):
            resolve_in_context(path)


def test_several_folders_are_each_readable_and_the_environment_names_them(tmp_path, monkeypatch):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    _cube_stl(second / "cube.stl")
    monkeypatch.setenv("ANVILATE_CONTEXT", os.pathsep.join([str(first), str(second)]))
    assert context.context_roots() == (first.resolve(), second.resolve())
    assert resolve_in_context("cube.stl") == (second / "cube.stl").resolve()
    context.set_context_roots([first])
    with pytest.raises(ContextError):
        resolve_in_context("cube.stl")


# --- the surfaces ----------------------------------------------------------------------


def _call(name: str, arguments: dict) -> dict:
    from anvilate.mcp import handle_request

    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


def test_the_server_reads_nothing_until_it_is_started_with_a_folder(tmp_path):
    _cube_stl(tmp_path / "cube.stl")
    for name, arguments in (
        ("list_context", {"folder": "."}),
        ("read_cad_file", {"source": str(tmp_path / "cube.stl")}),
    ):
        error = _call(name, arguments)["error"]
        assert error["code"] == -32000 and "anvilate-mcp --context DIR" in error["message"]


def test_an_agent_lists_the_folder_and_measures_a_file_in_it(tmp_path):
    from anvilate.mcp import RESULT_BUDGET_CHARS

    _cube_stl(tmp_path / "scan.stl")
    (tmp_path / "old.dwg").write_bytes(b"AC1027")
    (tmp_path / "sketch.png").write_bytes(b"\x89PNG")
    context.set_context_roots([tmp_path])
    listing = _call("list_context", {"folder": "."})["result"]["structuredContent"]["inventory"]
    assert {file["path"]: file["reader"] for file in listing["files"]} == {
        "old.dwg": "unsupported",
        "scan.stl": "anvilate",
        "sketch.png": "agent",
    }
    result = _call("read_cad_file", {"source": "scan.stl", "unit": "mm"})["result"]
    facts = result["structuredContent"]["facts"]
    assert facts["triangles"] == 12 and facts["volume_mm3"] == 1000.0
    assert len(json.dumps(result)) < RESULT_BUDGET_CHARS


def test_a_refusal_over_mcp_names_the_argument_it_is_about(tmp_path):
    _plate_dxf(tmp_path / "bare.dxf", units=0)
    (tmp_path / "old.dwg").write_bytes(b"AC1027")
    context.set_context_roots([tmp_path])
    no_unit = _call("read_cad_file", {"source": "bare.dxf"})["error"]
    assert no_unit["code"] == -32602 and no_unit["message"].startswith("unit: bare.dxf declares")
    dwg = _call("read_cad_file", {"source": "old.dwg"})["error"]
    assert dwg["message"].startswith("source: old.dwg") and "export DXF" in dwg["message"]
    outside = _call("read_cad_file", {"source": "/etc/hosts"})["error"]
    assert outside["code"] == -32602 and "reads only inside" in outside["message"]
    assert _call("list_context", {"folder": "/"})["error"]["code"] == -32602


def test_the_server_takes_its_context_folders_at_launch(tmp_path, monkeypatch, capsys):
    from anvilate import mcp

    monkeypatch.setattr(mcp, "serve_stdio", lambda: None)
    project = tmp_path / "project"
    project.mkdir()
    mcp.main(["--context", str(project), "--out", str(tmp_path / "out")])
    assert context.context_roots() == (project.resolve(),)
    with pytest.raises(SystemExit) as stopped:
        mcp.main(["--context", str(tmp_path / "missing")])
    assert stopped.value.code == 2 and "not a folder" in capsys.readouterr().err


def test_the_context_tools_are_not_pipeline_operations_and_write_nothing(tmp_path):
    from anvilate.mcp import CONTEXT_OPERATIONS, REQUIRED_OPERATIONS, tool_catalog

    tools = {tool.name: tool for tool in tool_catalog() if tool.name in CONTEXT_OPERATIONS}
    assert set(tools) == {"list_context", "read_cad_file"} and not set(tools) & REQUIRED_OPERATIONS
    assert tools["list_context"].subject == "folder" and tools["read_cad_file"].subject == "source"
    assert not any(tool.emits_artifacts or tool.gates for tool in tools.values())
    _cube_stl(tmp_path / "cube.stl")
    context.set_context_roots([tmp_path])
    before = sorted(path.name for path in tmp_path.iterdir())
    _call("list_context", {"folder": "."})
    _call("read_cad_file", {"source": "cube.stl"})
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_the_command_line_measures_a_file_and_lists_a_folder(tmp_path):
    from cli_output import run_cli

    _cube_stl(tmp_path / "cube.stl")
    (tmp_path / "old.dwg").write_bytes(b"AC1027")
    code, out, _err = run_cli("read", str(tmp_path / "cube.stl"), "--unit", "mm")
    assert code == 0 and "cube.stl: mesh, written in no stated unit, 10 x 10 x 10 mm" in out
    assert "12 triangles, closed" in out and "volume 1000 mm^3" in out
    code, out, _err = run_cli("read", str(tmp_path))
    assert code == 0 and "2 engineering files" in out and "export DXF" in out
    code, _out, err = run_cli("read", str(tmp_path / "old.dwg"))
    assert code == 3 and "does not read and does not convert" in err


# --- starting a part from what was read ------------------------------------------------


def _seeded(seed, **stated) -> dict:
    """A whole spec from a seed, with the fields the file could not give stated by hand."""
    params = {**seed.element_params, **stated}
    assert set(seed.missing) <= set(stated), "the test must state everything the seed lacks"
    return {
        "name": stated["name"],
        "description": "A part started from a measured file.",
        "units": {"value": "SI", "origin": "user_stated"},
        "material": {"ref": "ASTM-A36"},
        "manufacturing": {"process": "cnc_milling"},
        "element_type": seed.element_type,
        "element_params": params,
        "sources": [dict(source) for source in seed.sources],
        "acceptance": {"tiers": ["T1_analytical"]},
    }


def test_a_drawing_of_a_plate_seeds_a_mounting_plate_that_builds_to_the_drawing(tmp_path):
    pytest.importorskip("build123d")
    from anvilate.context import seed_part
    from anvilate.geometry import build_spec
    from anvilate.screening import CITED_SOURCES_CHECK, screen_spec
    from anvilate.spec import parse_spec

    path = _plate_dxf(tmp_path / "plate.dxf")
    # Only the plate is on this drawing: the tab and the stray line would make it two profiles.
    ezdxf = pytest.importorskip("ezdxf")
    document = ezdxf.readfile(path)
    for entity in list(document.modelspace()):
        if entity.dxftype() in ("LINE", "ARC", "DIMENSION"):
            document.modelspace().delete_entity(entity)
    document.saveas(path)
    facts = read_cad_file(path)
    seed = seed_part(facts)
    assert seed.element_type == "mounting_plate" and seed.missing == ("name", "thickness")
    assert seed.element_params["width"] == {"magnitude": 101.6, "unit": "mm"}
    assert [hole["tag"] for hole in seed.element_params["holes"]] == ["h1", "h2", "h3", "h4"]
    assert {source["sha256"] for source in seed.sources} == {facts.sha256}
    assert {source["origin"] for source in seed.sources} == {"measured_from_file"}
    assert "still needs name, thickness" in str(seed)
    spec = parse_spec(
        _seeded(seed, name="from-drawing", thickness={"magnitude": 6.0, "unit": "mm"})
    )
    built = build_spec(spec)
    assert built.dimensions_mm["width"] == 101.6 and len(built.features) == 4
    assert built.volume_mm3 == pytest.approx((101.6 * 76.2 - 4 * _disc(6.35)) * 6, rel=1e-6)
    held = next(
        entry
        for entry in screen_spec(spec, source_roots=(tmp_path,)).entries
        if entry.name == CITED_SOURCES_CHECK
    )
    assert "6 cited files match" in held.detail  # width, length and four hole diameters


def test_a_drawing_of_a_flange_seeds_a_plate_flange(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    from anvilate.context import seed_part

    document = ezdxf.new()
    document.header["$INSUNITS"] = 4
    space = document.modelspace()
    space.add_circle((0, 0), 60)
    space.add_circle((0, 0), 25)
    for k in range(6):
        angle = math.radians(60 * k)
        space.add_circle((45 * math.cos(angle), 45 * math.sin(angle)), 4.5)
    document.saveas(tmp_path / "flange.dxf")
    seed = seed_part(read_cad_file(tmp_path / "flange.dxf"))
    assert seed.element_type == "plate_flange" and seed.missing == ("name", "thickness")
    assert dict(seed.element_params) == {
        "outer_diameter": {"magnitude": 120.0, "unit": "mm"},
        "bore_diameter": {"magnitude": 50.0, "unit": "mm"},
        "bolt_circle_diameter": {"magnitude": 90.0, "unit": "mm"},
        "bolt_count": 6,
        "bolt_hole_diameter": {"magnitude": 9.0, "unit": "mm"},
    }


@pytest.mark.parametrize(
    ("example", "element_type", "missing"),
    [
        ("spacer", "spacer", ("name",)),
        ("plate_flange", "plate_flange", ("name",)),
    ],
)
def test_a_solid_seeds_the_part_it_is_and_the_part_builds_to_the_same_volume(
    example, element_type, missing, tmp_path
):
    pytest.importorskip("build123d")
    from anvilate.context import seed_part
    from anvilate.geometry import build_spec
    from anvilate.spec import parse_spec

    original = _built(example)
    facts = read_cad_file(_step(tmp_path, example))
    seed = seed_part(facts)
    assert (seed.element_type, seed.missing) == (element_type, missing)
    rebuilt = build_spec(parse_spec(_seeded(seed, name="again")))
    assert rebuilt.volume_mm3 == pytest.approx(original.volume_mm3, rel=1e-6)


def test_a_plain_plate_with_holes_through_it_seeds_a_mounting_plate(tmp_path):
    pytest.importorskip("build123d")
    from build123d import Box, Cylinder, Pos, export_step

    from anvilate.context import seed_part
    from anvilate.geometry import build_spec
    from anvilate.spec import parse_spec

    plate = Box(100, 60, 8)
    for x, y in ((-35, -20), (35, -20), (35, 20), (-35, 20)):
        plate -= Pos(x, y, 0) * Cylinder(4, 8)
    export_step(plate, str(tmp_path / "plate.step"))
    seed = seed_part(read_cad_file(tmp_path / "plate.step"))
    assert seed.element_type == "mounting_plate" and seed.missing == ("name",)
    assert seed.element_params["thickness"] == {"magnitude": 8.0, "unit": "mm"}
    built = build_spec(parse_spec(_seeded(seed, name="again")))
    assert built.volume_mm3 == pytest.approx(float(plate.volume), rel=1e-6)
    assert sorted((f.position_mm[0], f.position_mm[1]) for f in built.features) == [
        (-35.0, -20.0),
        (-35.0, 20.0),
        (35.0, -20.0),
        (35.0, 20.0),
    ]


def test_a_shape_no_pattern_matches_seeds_nothing(tmp_path):
    """A shape is not forced into a pattern: rounded corners, a slot, a bracket, a mesh."""
    pytest.importorskip("build123d")
    from anvilate.context import seed_part

    for example in ("mounting_plate", "angle_bracket", "stepped_shaft", "enclosure"):
        assert seed_part(read_cad_file(_step(tmp_path, example))) is None, example
    assert seed_part(read_cad_file(_cube_stl(tmp_path / "cube.stl"))) is None
    # The whole drawing, with its tab beside the plate: two profiles, and no one part.
    assert seed_part(read_cad_file(_plate_dxf(tmp_path / "two.dxf"))) is None


def test_the_server_offers_the_seed_beside_the_facts_and_nothing_when_there_is_none(tmp_path):
    pytest.importorskip("ezdxf")
    import shutil

    repo = Path(__file__).resolve().parents[1]
    shutil.copy(repo / "examples" / "context" / "plate.dxf", tmp_path / "plate.dxf")
    _cube_stl(tmp_path / "cube.stl")
    context.set_context_roots([tmp_path])
    body = _call("read_cad_file", {"source": "plate.dxf"})["result"]["structuredContent"]
    assert body["seed"]["element_type"] == "mounting_plate"
    assert body["seed"]["missing"] == ["name", "thickness"]
    assert body["seed"]["sources"][0]["file"] == "plate.dxf"
    assert len(body["seed"]["element_params"]["holes"]) == 4
    mesh = _call("read_cad_file", {"source": "cube.stl", "unit": "mm"})["result"][
        "structuredContent"
    ]
    assert "seed" not in mesh
