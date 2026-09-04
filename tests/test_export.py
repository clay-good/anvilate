"""Tests for the DXF plate export (round-tripped through ezdxf)."""

from __future__ import annotations

import pytest

from anvilate.export.dxf import Hole, Slot, export_plate_dxf
from anvilate.export.gate import authorize_export
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


# These tests are about geometry, not about the export gate — `tests/test_export_gate.py`
# owns that. An explicit override is the authorization a caller with no acceptance card
# can obtain, so it is the one that keeps this file's subject unchanged.
_AUTH = authorize_export(None, override=True)


def test_export_lug_outline_round_trips(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    # An 80 x 120 mm lug plate with a 25 mm pin hole 90 mm up, centred.
    out = export_plate_dxf(
        authorization=_AUTH,
        width=_q("80 mm"),
        height=_q("120 mm"),
        holes=[Hole(x=_q("40 mm"), y=_q("90 mm"), diameter=_q("25 mm"))],
        path=tmp_path / "lug.dxf",
    )
    assert out.exists()

    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    polylines = list(msp.query("LWPOLYLINE"))
    circles = list(msp.query("CIRCLE"))
    assert len(polylines) == 1
    assert len(circles) == 1
    # Profile and pierces land on separate named layers for the CNC controller.
    assert polylines[0].dxf.layer == "OUTLINE"
    assert circles[0].dxf.layer == "HOLES"
    # The plate outline is a closed 4-point rectangle spanning the plate.
    points = [(round(p[0]), round(p[1])) for p in polylines[0].get_points("xy")]
    assert points == [(0, 0), (80, 0), (80, 120), (0, 120)]
    # The hole circle sits where declared with the right radius.
    circle = circles[0]
    assert (round(circle.dxf.center.x), round(circle.dxf.center.y)) == (40, 90)
    assert circle.dxf.radius == pytest.approx(12.5)


def test_export_writes_an_optional_part_label(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    out = export_plate_dxf(
        authorization=_AUTH,
        width=_q("80 mm"),
        height=_q("120 mm"),
        holes=[],
        path=tmp_path / "labelled.dxf",
        label="PADEYE  ASTM-A36",
    )
    doc = ezdxf.readfile(out)
    texts = list(doc.modelspace().query("TEXT"))
    assert len(texts) == 1
    assert texts[0].dxf.text == "PADEYE  ASTM-A36"
    assert texts[0].dxf.layer == "TEXT"


def test_export_omits_text_when_no_label(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    out = export_plate_dxf(
        authorization=_AUTH,
        width=_q("80 mm"),
        height=_q("120 mm"),
        holes=[],
        path=tmp_path / "plain.dxf",
    )
    doc = ezdxf.readfile(out)
    assert list(doc.modelspace().query("TEXT")) == []


def test_export_draws_a_slotted_hole_as_an_obround(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    # A 40 mm-long, 16 mm-wide horizontal slot centred at (40, 60).
    out = export_plate_dxf(
        authorization=_AUTH,
        width=_q("80 mm"),
        height=_q("120 mm"),
        holes=[],
        slots=[Slot(x=_q("40 mm"), y=_q("60 mm"), length=_q("40 mm"), width=_q("16 mm"))],
        path=tmp_path / "slot.dxf",
    )
    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    # The slot is a closed 4-vertex polyline on the HOLES layer with two arc caps.
    obrounds = [p for p in msp.query("LWPOLYLINE") if p.dxf.layer == "HOLES"]
    assert len(obrounds) == 1
    verts = obrounds[0].get_points("xyb")
    assert obrounds[0].closed
    assert [round(b, 1) for _, _, b in verts] == [0.0, 1.0, 0.0, 1.0]  # two semicircle caps
    xs = [round(x) for x, _, _ in verts]
    assert min(xs) == 28 and max(xs) == 52  # straight run; caps add the 8 mm radius


def test_export_rejects_slot_outside_the_plate(tmp_path):
    pytest.importorskip("ezdxf")
    with pytest.raises(ValueError, match="falls outside"):
        export_plate_dxf(
            authorization=_AUTH,
            width=_q("80 mm"),
            height=_q("120 mm"),
            holes=[],
            slots=[Slot(x=_q("70 mm"), y=_q("60 mm"), length=_q("40 mm"), width=_q("16 mm"))],
            path=tmp_path / "bad_slot.dxf",
        )


def test_export_rejects_slot_length_not_over_width(tmp_path):
    pytest.importorskip("ezdxf")
    with pytest.raises(ValueError, match="length > width"):
        export_plate_dxf(
            authorization=_AUTH,
            width=_q("80 mm"),
            height=_q("120 mm"),
            holes=[],
            slots=[Slot(x=_q("40 mm"), y=_q("60 mm"), length=_q("16 mm"), width=_q("16 mm"))],
            path=tmp_path / "bad_slot.dxf",
        )


def test_export_rejects_hole_outside_the_plate(tmp_path):
    pytest.importorskip("ezdxf")
    with pytest.raises(ValueError, match="falls outside"):
        export_plate_dxf(
            authorization=_AUTH,
            width=_q("80 mm"),
            height=_q("120 mm"),
            holes=[Hole(x=_q("75 mm"), y=_q("90 mm"), diameter=_q("25 mm"))],
            path=tmp_path / "bad.dxf",
        )


def test_export_rejects_non_positive_plate(tmp_path):
    pytest.importorskip("ezdxf")
    with pytest.raises(ValueError, match="must be positive"):
        export_plate_dxf(
            authorization=_AUTH,
            width=_q("0 mm"),
            height=_q("120 mm"),
            holes=[],
            path=tmp_path / "empty.dxf",
        )


def test_bolt_circle_holes_places_evenly_on_the_circle():
    from math import cos, radians, sin

    from anvilate.export.dxf import bolt_circle_holes

    holes = bolt_circle_holes(
        center_x=_q("50 mm"),
        center_y=_q("50 mm"),
        bolt_circle_diameter=_q("100 mm"),
        hole_diameter=_q("10 mm"),
        count=4,
    )
    assert len(holes) == 4
    # Four holes on a 100 mm circle centred at (50, 50): at 0, 90, 180, 270 degrees.
    expected = [(100, 50), (50, 100), (0, 50), (50, 0)]
    for hole, (ex, ey) in zip(holes, expected, strict=True):
        assert hole.x.to("mm").magnitude == pytest.approx(ex, abs=1e-9)
        assert hole.y.to("mm").magnitude == pytest.approx(ey, abs=1e-9)
        assert hole.diameter.to("mm").magnitude == 10.0
    # Every hole sits exactly the pitch radius from the centre, at the start angle offset.
    offset = bolt_circle_holes(
        center_x=_q("0 mm"),
        center_y=_q("0 mm"),
        bolt_circle_diameter=_q("80 mm"),
        hole_diameter=_q("8 mm"),
        count=6,
        start_angle=30.0,
    )
    for i, hole in enumerate(offset):
        angle = radians(30.0 + 60.0 * i)
        assert hole.x.to("mm").magnitude == pytest.approx(40 * cos(angle), abs=1e-9)
        assert hole.y.to("mm").magnitude == pytest.approx(40 * sin(angle), abs=1e-9)
    with pytest.raises(ValueError, match="count must be at least 1"):
        bolt_circle_holes(
            center_x=_q("0 mm"),
            center_y=_q("0 mm"),
            bolt_circle_diameter=_q("80 mm"),
            hole_diameter=_q("8 mm"),
            count=0,
        )


def test_bolt_circle_holes_feed_the_plate_export(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")

    from anvilate.export.dxf import bolt_circle_holes, export_plate_dxf

    holes = bolt_circle_holes(
        center_x=_q("100 mm"),
        center_y=_q("100 mm"),
        bolt_circle_diameter=_q("140 mm"),
        hole_diameter=_q("14 mm"),
        count=8,
    )
    out = export_plate_dxf(
        authorization=_AUTH,
        width=_q("200 mm"),
        height=_q("200 mm"),
        holes=holes,
        path=tmp_path / "flange.dxf",
    )
    doc = ezdxf.readfile(out)
    circles = list(doc.modelspace().query("CIRCLE"))
    assert len(circles) == 8


def test_linear_hole_pattern_marches_along_the_pitch_line():
    from math import cos, radians, sin

    from anvilate.export.dxf import linear_hole_pattern

    row = linear_hole_pattern(
        start_x=_q("10 mm"),
        start_y=_q("10 mm"),
        hole_diameter=_q("6 mm"),
        count=4,
        pitch=_q("20 mm"),
    )
    assert [h.x.to("mm").magnitude for h in row] == pytest.approx([10, 30, 50, 70])
    assert all(h.y.to("mm").magnitude == pytest.approx(10) for h in row)
    # An angled row steps along the pitch direction.
    diag = linear_hole_pattern(
        start_x=_q("0 mm"),
        start_y=_q("0 mm"),
        hole_diameter=_q("6 mm"),
        count=3,
        pitch=_q("10 mm"),
        angle=45.0,
    )
    for i, h in enumerate(diag):
        assert h.x.to("mm").magnitude == pytest.approx(10 * i * cos(radians(45)), abs=1e-9)
        assert h.y.to("mm").magnitude == pytest.approx(10 * i * sin(radians(45)), abs=1e-9)
    with pytest.raises(ValueError, match="pitch must be positive"):
        linear_hole_pattern(
            start_x=_q("0 mm"),
            start_y=_q("0 mm"),
            hole_diameter=_q("6 mm"),
            count=3,
            pitch=_q("0 mm"),
        )


def test_grid_hole_pattern_fills_a_rectangular_array():
    from anvilate.export.dxf import grid_hole_pattern

    grid = grid_hole_pattern(
        origin_x=_q("0 mm"),
        origin_y=_q("0 mm"),
        hole_diameter=_q("6 mm"),
        columns=3,
        rows=2,
        x_pitch=_q("25 mm"),
        y_pitch=_q("30 mm"),
    )
    assert len(grid) == 6
    coords = [(h.x.to("mm").magnitude, h.y.to("mm").magnitude) for h in grid]
    assert coords == [(0, 0), (25, 0), (50, 0), (0, 30), (25, 30), (50, 30)]
    with pytest.raises(ValueError, match="columns and rows must be at least 1"):
        grid_hole_pattern(
            origin_x=_q("0 mm"),
            origin_y=_q("0 mm"),
            hole_diameter=_q("6 mm"),
            columns=0,
            rows=2,
            x_pitch=_q("25 mm"),
            y_pitch=_q("30 mm"),
        )


def test_plate_cut_length_sums_outline_holes_and_slots():
    from math import pi

    from anvilate.export.dxf import Hole, Slot, plate_cut_length

    # Bare rectangle: just the outline perimeter.
    assert plate_cut_length(width=_q("100 mm"), height=_q("80 mm")).to(
        "mm"
    ).magnitude == pytest.approx(2 * (100 + 80))
    # Outline + a round hole (pi*d) + an obround slot (2*(L-w) + pi*w).
    total = plate_cut_length(
        width=_q("100 mm"),
        height=_q("80 mm"),
        holes=[Hole(x=_q("50 mm"), y=_q("40 mm"), diameter=_q("20 mm"))],
        slots=[Slot(x=_q("30 mm"), y=_q("20 mm"), length=_q("40 mm"), width=_q("10 mm"))],
    )
    expected = 2 * (100 + 80) + pi * 20 + (2 * (40 - 10) + pi * 10)
    assert total.to("mm").magnitude == pytest.approx(expected, rel=1e-12)
    with pytest.raises(ValueError, match="plate width and height must be positive"):
        plate_cut_length(width=_q("0 mm"), height=_q("80 mm"))


def test_plate_mass_is_net_of_holes_and_slots():
    from math import pi

    from anvilate.export.dxf import Hole, Slot, plate_mass

    # Bare 100x80x5 steel plate: 8000 mm^2 * 5 mm * 7850 kg/m^3 = 0.314 kg.
    bare = plate_mass(
        width=_q("100 mm"), height=_q("80 mm"), thickness=_q("5 mm"), density=_q("7850 kg/m**3")
    )
    assert bare.to("kg").magnitude == pytest.approx(8000 * 5 * 1e-9 * 7850, rel=1e-12)
    # Holes and slots subtract their areas.
    net = plate_mass(
        width=_q("100 mm"),
        height=_q("80 mm"),
        thickness=_q("5 mm"),
        density=_q("7850 kg/m**3"),
        holes=[Hole(x=_q("50 mm"), y=_q("40 mm"), diameter=_q("20 mm"))],
        slots=[Slot(x=_q("30 mm"), y=_q("20 mm"), length=_q("40 mm"), width=_q("10 mm"))],
    )
    net_area = 8000 - pi * 20**2 / 4 - ((40 - 10) * 10 + pi * 10**2 / 4)
    assert net.to("kg").magnitude == pytest.approx(net_area * 5 * 1e-9 * 7850, rel=1e-12)
    assert net.to("kg").magnitude < bare.to("kg").magnitude
    with pytest.raises(ValueError, match="density must be a mass/volume"):
        plate_mass(
            width=_q("100 mm"), height=_q("80 mm"), thickness=_q("5 mm"), density=_q("7850 kg")
        )


def test_export_gear_blank_dxf_draws_the_reference_circles(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")

    from anvilate.analysis import (
        gear_outside_diameter,
        gear_pitch_diameter,
        gear_root_diameter,
    )
    from anvilate.export.dxf import export_gear_blank_dxf

    # A module-2, 20-tooth gear blank with a 12 mm bore.
    out = export_gear_blank_dxf(
        authorization=_AUTH,
        outside_diameter=gear_outside_diameter(module=_q("2 mm"), teeth=20),
        pitch_diameter=gear_pitch_diameter(module=_q("2 mm"), teeth=20),
        root_diameter=gear_root_diameter(module=_q("2 mm"), teeth=20),
        bore_diameter=_q("12 mm"),
        path=tmp_path / "gear.dxf",
        label="m2 z20",
    )
    assert out.exists()
    doc = ezdxf.readfile(out)
    circles = list(doc.modelspace().query("CIRCLE"))
    # Outside, bore, pitch, and root -> four concentric circles.
    assert len(circles) == 4
    radii = sorted(c.dxf.radius for c in circles)
    assert radii == pytest.approx([6.0, 17.5, 20.0, 22.0])  # bore, root, pitch, outside


def test_export_gear_blank_dxf_rejects_bad_diameter_order(tmp_path):
    pytest.importorskip("ezdxf")

    from anvilate.export.dxf import export_gear_blank_dxf

    with pytest.raises(ValueError, match="outside > pitch > root > bore"):
        export_gear_blank_dxf(
            authorization=_AUTH,
            outside_diameter=_q("40 mm"),
            pitch_diameter=_q("44 mm"),  # pitch above outside -> invalid
            root_diameter=_q("35 mm"),
            bore_diameter=_q("12 mm"),
            path=tmp_path / "bad.dxf",
        )


def test_export_rounds_the_plate_corners_with_quarter_arcs(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    from math import pi, tan

    out = export_plate_dxf(
        authorization=_AUTH,
        width=_q("80 mm"),
        height=_q("120 mm"),
        holes=[],
        corner_radius=_q("10 mm"),
        path=tmp_path / "rounded.dxf",
    )
    doc = ezdxf.readfile(out)
    outline = doc.modelspace().query("LWPOLYLINE")[0]
    assert outline.closed
    points = outline.get_points("xyb")
    # Eight vertices: a straight edge then a quarter-arc at each corner, CCW.
    coords = [(round(p[0]), round(p[1])) for p in points]
    assert coords == [
        (10, 0),
        (70, 0),
        (80, 10),
        (80, 110),
        (70, 120),
        (10, 120),
        (0, 110),
        (0, 10),
    ]
    # Alternate segments carry the 90-degree arc bulge tan(pi/8); edges are straight.
    bulges = [p[2] for p in points]
    for i, bulge in enumerate(bulges):
        expected = tan(pi / 8) if i % 2 == 1 else 0.0
        assert bulge == pytest.approx(expected, abs=1e-12)


def test_export_rejects_an_oversized_corner_radius(tmp_path):
    pytest.importorskip("ezdxf")
    with pytest.raises(ValueError, match="corner_radius .* under half the shorter"):
        export_plate_dxf(
            authorization=_AUTH,
            width=_q("80 mm"),
            height=_q("120 mm"),
            holes=[],
            corner_radius=_q("40 mm"),
            path=tmp_path / "bad.dxf",
        )


def test_plate_cut_length_and_mass_account_for_rounded_corners():
    from math import pi

    from anvilate.export.dxf import plate_cut_length, plate_mass

    # Each rounded corner swaps 2r of straight edge for a quarter arc pi*r/2:
    # the outline shortens by (8 - 2*pi)*r in total.
    rounded = plate_cut_length(width=_q("100 mm"), height=_q("80 mm"), corner_radius=_q("10 mm"))
    assert rounded.to("mm").magnitude == pytest.approx(
        2 * (100 + 80) - (8 - 2 * pi) * 10, rel=1e-12
    )
    # A zero radius is exactly the sharp-cornered perimeter.
    sharp = plate_cut_length(width=_q("100 mm"), height=_q("80 mm"), corner_radius=_q("0 mm"))
    assert sharp.to("mm").magnitude == pytest.approx(2 * (100 + 80), rel=1e-12)
    # The mass loses the four corner cut-offs, (4 - pi)*r^2 of area.
    mass = plate_mass(
        width=_q("100 mm"),
        height=_q("80 mm"),
        thickness=_q("5 mm"),
        density=_q("7850 kg/m**3"),
        corner_radius=_q("10 mm"),
    )
    expected_area = 100 * 80 - (4 - pi) * 10**2
    assert mass.to("kg").magnitude == pytest.approx(expected_area * 5 * 1e-9 * 7850, rel=1e-12)


def test_a_plate_its_cut_outs_consume_is_refused_rather_than_weighed():
    """The mass is density times *net* area, so a plate whose holes remove all of it has a
    mass of zero or less — a number in kilograms that no plate has.

    The refusal was never executed by anything. Pinned by its boundary: a cut-out pattern
    just inside the limit still weighs something, and one just past it is refused.
    """
    from math import pi

    from anvilate.export.dxf import plate_mass

    plate = {
        "width": _q("100 mm"),
        "height": _q("100 mm"),
        "thickness": _q("5 mm"),
        "density": _q("7850 kg/m**3"),
    }
    # One hole whose area is just under, then just over, the 10 000 mm² plate.
    under = 2.0 * (10000.0 * 0.999 / pi) ** 0.5
    over = 2.0 * (10000.0 * 1.001 / pi) ** 0.5
    assert (
        plate_mass(**plate, holes=[Hole(diameter=_q(f"{under} mm"), x=_q("0 mm"), y=_q("0 mm"))])
        .to("kg")
        .magnitude
        > 0
    )
    with pytest.raises(ValueError, match="net area is not positive"):
        plate_mass(**plate, holes=[Hole(diameter=_q(f"{over} mm"), x=_q("0 mm"), y=_q("0 mm"))])
    # And through the slots, which subtract a different shape and so are a separate path.
    with pytest.raises(ValueError, match="net area is not positive"):
        plate_mass(
            **plate,
            slots=[
                Slot(
                    length=_q("200 mm"),
                    width=_q("99 mm"),
                    x=_q("0 mm"),
                    y=_q("0 mm"),
                    angle=0.0,
                )
            ],
        )


def test_the_gdt_writer_handles_every_stroke_the_union_declares():
    """`export/dxf.py` raises `TypeError: unknown stroke primitive` after its isinstance
    chain, excused as unreachable because "the stroke union is closed".

    The excuse is true and the fact it rests on is not held by anything: `Stroke` is a union
    in `export/fcf.py`, and a fourth member added there would make the refusal reachable and
    every frame carrying one silently undrawn. So the union's members are read from the
    annotation and each one must be named in the writer's chain.
    """
    import inspect
    import typing

    from anvilate.export import dxf, fcf

    members = typing.get_args(fcf.Stroke)
    assert len(members) >= 3, f"the Stroke union has {len(members)} members"
    source = inspect.getsource(dxf)
    for member in members:
        assert f"isinstance(stroke, {member.__name__})" in source, (
            f"{member.__name__} is a Stroke and the DXF writer's chain does not name it, so "
            "a frame carrying one raises 'unknown stroke primitive' at export"
        )


def test_a_hole_with_no_size_is_refused_before_it_reaches_a_drawing():
    """A negative diameter wrote `radius = -5.0` into the DXF a shop cuts from.

    `export_plate_dxf` checks each feature against the plate — and that check cannot stand in
    for this one. It is `cx - radius >= 0 and cx + radius <= w`, which a *negative* radius
    satisfies **more easily** than a real one: a Ø-10 mm hole at (50, 50) tests 55 and 45, both
    comfortably inside, so the guard that exists let it through and ezdxf wrote a CIRCLE with a
    negative radius — an entity no reader is required to accept. A zero diameter passed the
    same way and wrote a radius-0 circle.

    Three of the four ways to get a `Hole` already refused it: each pattern helper checks the
    diameter it is handed. The unguarded one was the way the docstrings tell a caller to build
    a plate — construct a `Hole`, pass it to the writer — so the rule belongs on the model,
    where all four paths meet.
    """
    for bad in ("-10 mm", "0 mm", "-1 um"):
        with pytest.raises(ValueError, match="hole diameter must be positive"):
            Hole(x=_q("50 mm"), y=_q("50 mm"), diameter=_q(bad))
    Hole(x=_q("50 mm"), y=_q("50 mm"), diameter=_q("10 mm"))  # and a real one is fine

    # A slot's length and width were checked by the writer and not by the model, so a slot
    # handed to anything else was unguarded in the same way.
    for field, kwargs in (
        ("width", {"length": _q("30 mm"), "width": _q("0 mm")}),
        ("width", {"length": _q("30 mm"), "width": _q("-8 mm")}),
        ("length", {"length": _q("0 mm"), "width": _q("8 mm")}),
    ):
        with pytest.raises(ValueError, match=f"slot {field} must be positive"):
            Slot(x=_q("50 mm"), y=_q("50 mm"), **kwargs)

    # The relational rule stays in the writer, because it is about the pair rather than a field.
    with pytest.raises(ValueError, match="needs length > width > 0"):
        export_plate_dxf(
            width=_q("100 mm"),
            height=_q("100 mm"),
            holes=[],
            slots=[Slot(x=_q("50 mm"), y=_q("50 mm"), length=_q("8 mm"), width=_q("8 mm"))],
            path="unused.dxf",
            authorization=authorize_export(None, override=True),
        )


def test_a_feature_dimension_that_is_not_a_length_is_refused_by_the_model_too():
    """`_mm` in the writer says this, and said it only there. A `Hole` carrying a mass reached
    every other consumer of the model unremarked."""
    for bad in ("3 kg", "5 N", "2 deg"):
        with pytest.raises(ValueError, match="hole diameter must be a .length. quantity"):
            Hole(x=_q("50 mm"), y=_q("50 mm"), diameter=_q(bad))


def test_model_copy_cannot_put_a_sizeless_hole_back():
    """`model_copy` does not re-run field validators, so the rule above would hold only until
    somebody copied a good hole into a bad one. Both models are `RevalidatedModel` for that
    reason — the same decision this repository has already made for its spec models."""
    good = Hole(x=_q("50 mm"), y=_q("50 mm"), diameter=_q("10 mm"))
    with pytest.raises(ValueError, match="hole diameter must be positive"):
        good.model_copy(update={"diameter": _q("-10 mm")})

    slot = Slot(x=_q("50 mm"), y=_q("50 mm"), length=_q("30 mm"), width=_q("8 mm"))
    with pytest.raises(ValueError, match="slot width must be positive"):
        slot.model_copy(update={"width": _q("0 mm")})
