"""Tests for the DXF plate export (round-tripped through ezdxf)."""

from __future__ import annotations

import pytest

from anvilate.export.dxf import Hole, export_plate_dxf
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
