"""Tests for the DXF plate export (round-tripped through ezdxf)."""

from __future__ import annotations

import pytest

from anvilate.export.dxf import Hole, Slot, export_plate_dxf
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def test_export_lug_outline_round_trips(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    # An 80 x 120 mm lug plate with a 25 mm pin hole 90 mm up, centred.
    out = export_plate_dxf(
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
            width=_q("80 mm"),
            height=_q("120 mm"),
            holes=[Hole(x=_q("75 mm"), y=_q("90 mm"), diameter=_q("25 mm"))],
            path=tmp_path / "bad.dxf",
        )


def test_export_rejects_non_positive_plate(tmp_path):
    pytest.importorskip("ezdxf")
    with pytest.raises(ValueError, match="must be positive"):
        export_plate_dxf(
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
        width=_q("200 mm"), height=_q("200 mm"), holes=holes, path=tmp_path / "flange.dxf"
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
