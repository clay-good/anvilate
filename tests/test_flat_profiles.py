"""A flat part exports its cut profile as DXF, and the file reads back as that part.

expand-drawable-parts 4.10. Each profile is written, then measured by the reader in
`anvilate.context`, which shares no code with the writer: the outline's size and area, each
hole's diameter and place, and a slot as the slot it is. A sheet-metal bracket exports its
developed blank with the bend lines marked, and a part with no flat profile is refused.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")
ezdxf = pytest.importorskip("ezdxf")

from anvilate.context import read_cad_file  # noqa: E402
from anvilate.export.dxf import render_geometry_dxf  # noqa: E402
from anvilate.export.gate import authorize_export  # noqa: E402
from anvilate.geometry import UnsupportedGeometry, build_spec  # noqa: E402
from anvilate.patterns import patterns  # noqa: E402
from anvilate.spec import load_spec_yaml  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "parts"


def _built(name: str, **changes):
    document = yaml.safe_load((_EXAMPLES / f"{name}.spec.yaml").read_text(encoding="utf-8"))
    for key, value in changes.items():
        if value is None:
            document["element_params"].pop(key, None)
        else:
            document["element_params"][key] = value
    return build_spec(load_spec_yaml(yaml.safe_dump(document)))


def _written(built, tmp_path: Path) -> Path:
    data = render_geometry_dxf(geometry=built, authorization=authorize_export(None, override=True))
    path = tmp_path / "part.dxf"
    path.write_bytes(data)
    return path


def _disc(diameter: float) -> float:
    return math.pi * diameter**2 / 4


def test_the_patterns_that_say_they_export_dxf_are_the_ones_with_a_profile():
    """The catalog's `outputs` is a claim, so it is held to what the builders produce."""
    claimed = {
        name
        for name, pattern in patterns().items()
        if {"dxf", "flat_pattern"} & set(pattern.outputs)
    }
    assert claimed == {
        "base_plate",
        "cover_plate",
        "gusset_plate",
        "lifting_lug",
        "mounting_plate",
        "plate_flange",
        "shear_plate",
        "sheet_metal_bracket",
        "tension_member",
    }
    for name in sorted(claimed - {"base_plate", "cover_plate"}):
        assert _built(name).profile is not None, name
    assert _built("spacer").profile is None and _built("angle_bracket").profile is None


def test_a_mounting_plate_reads_back_with_its_holes_its_slot_and_its_round_corners(tmp_path):
    facts = read_cad_file(_written(_built("mounting_plate"), tmp_path))
    assert facts.unit_written == "mm" and {"OUTLINE", "HOLES"} <= set(facts.layers)
    (plate,) = facts.profiles
    assert (plate.kind, plate.layer, plate.width_mm, plate.height_mm) == (
        "profile",
        "OUTLINE",
        120.0,
        80.0,
    )
    # 120 x 80 less what four 8 mm corner radii take off.
    assert plate.area_mm2 == pytest.approx(120 * 80 - (4 - math.pi) * 8**2, rel=1e-5)
    circles = sorted((h.x_mm, h.y_mm, h.diameter_mm) for h in plate.holes if h.kind == "circle")
    # The four pattern holes, and the counterbored one cut at its through diameter.
    assert circles == [
        (-50.0, -30.0, 6.6),
        (-50.0, 30.0, 6.6),
        (0.0, 0.0, 6.6),
        (50.0, -30.0, 6.6),
        (50.0, 30.0, 6.6),
    ]
    (slot,) = [h for h in plate.holes if h.kind == "profile"]
    assert (slot.x_mm, slot.y_mm, slot.width_mm, slot.height_mm) == (0.0, 25.0, 30.0, 6.0)
    assert facts.open_entities == 0


def test_a_slot_turned_a_quarter_is_drawn_turned(tmp_path):
    plate = _built(
        "mounting_plate",
        slots=[
            {
                "tag": "up",
                "x": {"magnitude": 0.0, "unit": "mm"},
                "y": {"magnitude": 20.0, "unit": "mm"},
                "length": {"magnitude": 20.0, "unit": "mm"},
                "width": {"magnitude": 6.0, "unit": "mm"},
                "angle_deg": 90.0,
            }
        ],
    )
    (found,) = read_cad_file(_written(plate, tmp_path)).profiles
    (slot,) = [h for h in found.holes if h.kind == "profile"]
    assert (slot.width_mm, slot.height_mm) == pytest.approx((6.0, 20.0), abs=1e-6)


def test_a_plain_plate_is_a_rectangle(tmp_path):
    plate = _built("mounting_plate", corner_radius=None, holes=[], hole_patterns=[], slots=[])
    (found,) = read_cad_file(_written(plate, tmp_path)).profiles
    assert (found.kind, found.area_mm2, found.holes) == ("rectangle", 9600.0, ())


def test_a_flange_reads_back_as_a_disc_with_its_bore_and_its_bolt_circle(tmp_path):
    (flange,) = read_cad_file(_written(_built("plate_flange"), tmp_path)).profiles
    assert (flange.kind, flange.width_mm, flange.height_mm) == ("circle", 120.0, 120.0)
    assert flange.area_mm2 == pytest.approx(_disc(120), rel=1e-9)
    holes = sorted(h.diameter_mm for h in flange.holes)
    assert holes == [9.0] * 6 + [50.0]
    bolts = [h for h in flange.holes if h.diameter_mm == 9.0]
    assert {round(math.hypot(h.x_mm, h.y_mm), 6) for h in bolts} == {45.0}


def test_a_lug_reads_back_with_its_round_top_and_its_pin_hole(tmp_path):
    (lug,) = read_cad_file(_written(_built("lifting_lug"), tmp_path)).profiles
    assert (lug.width_mm, lug.height_mm) == (80.0, 130.0)
    # An 80 x 90 rectangle and a half disc of 40 mm radius above it.
    assert lug.area_mm2 == pytest.approx(80 * 90 + _disc(80) / 2, rel=1e-5)
    (pin,) = lug.holes
    # The profile is 130 tall, so its middle is at 65 and the hole, at 90, is 25 above it.
    assert (pin.diameter_mm, pin.x_mm, pin.y_mm) == (25.0, 0.0, 25.0)


def test_a_bent_bracket_exports_its_blank_with_the_bend_lines_marked(tmp_path):
    bracket = _built("sheet_metal_bracket")
    allowance = math.pi / 2 * (2 + 0.44 * 2)
    developed = 89 + 2 * allowance
    path = _written(bracket, tmp_path)
    facts = read_cad_file(path)
    (blank,) = facts.profiles
    assert (blank.kind, blank.height_mm) == ("rectangle", 40.0)
    assert blank.width_mm == pytest.approx(developed, abs=1e-6)
    assert blank.area_mm2 == pytest.approx(developed * 40, rel=1e-9)
    # The bend lines are on their own layer, each across the blank at the middle of a bend.
    drawing = ezdxf.readfile(path)
    lines = [e for e in drawing.modelspace() if e.dxftype() == "LINE"]
    assert {line.dxf.layer for line in lines} == {"BEND"} and len(lines) == 2
    assert sorted(round(line.dxf.start.x, 6) for line in lines) == pytest.approx(
        [26 + allowance / 2, 26 + allowance + 42 + allowance / 2], abs=1e-6
    )
    for line in lines:
        assert (line.dxf.start.y, line.dxf.end.y) == (-20.0, 20.0)
        assert line.dxf.start.x == line.dxf.end.x
    # Nothing that is cut is on the bend layer, and nothing on a cut layer is a bend.
    cut = [e for e in drawing.modelspace() if e.dxf.layer in ("OUTLINE", "HOLES")]
    assert [e.dxftype() for e in cut] == ["LWPOLYLINE"]


def test_a_bracket_with_no_k_factor_has_no_blank_to_export(tmp_path):
    bracket = _built("sheet_metal_bracket", k_factor=None, k_factor_source=None)
    assert bracket.profile is None
    with pytest.raises(UnsupportedGeometry, match="has none"):
        _written(bracket, tmp_path)


@pytest.mark.parametrize("name", ["spacer", "angle_bracket", "stepped_shaft", "enclosure"])
def test_a_part_with_no_flat_profile_is_refused_and_told_what_exports(name, tmp_path):
    with pytest.raises(UnsupportedGeometry, match="Plates, flanges, lugs") as refused:
        _written(_built(name), tmp_path)
    assert "writes this part as STEP" in str(refused.value)


def test_the_file_carries_the_unvalidated_mark_and_is_the_same_bytes_twice(tmp_path):
    built = _built("mounting_plate")
    authorization = authorize_export(None, override=True)
    first = render_geometry_dxf(geometry=built, authorization=authorization)
    assert first == render_geometry_dxf(
        geometry=_built("mounting_plate"), authorization=authorization
    )
    assert b"UNVALIDATED" in first


def test_an_agent_takes_away_a_drawn_plate_as_a_dxf(tmp_path, monkeypatch):
    from anvilate.mcp import handle_request

    out = tmp_path / "out"
    monkeypatch.setenv("ANVILATE_OUT", str(out))
    spec = yaml.safe_load((_EXAMPLES / "mounting_plate.spec.yaml").read_text(encoding="utf-8"))

    def call(name: str, arguments: dict) -> dict:
        return handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )

    handle = call("build_part", {"spec": spec})["result"]["structuredContent"]["subject"]
    body = call("export_artifact", {"subject": handle, "format": "dxf"})["result"][
        "structuredContent"
    ]
    assert body["validated"] is False and Path(body["file"]["path"]).suffix == ".dxf"
    (plate,) = read_cad_file(body["file"]["path"]).profiles
    assert (plate.width_mm, plate.height_mm, len(plate.holes)) == (120.0, 80.0, 6)
    spacer = yaml.safe_load((_EXAMPLES / "spacer.spec.yaml").read_text(encoding="utf-8"))
    handle = call("build_part", {"spec": spacer})["result"]["structuredContent"]["subject"]
    refused = call("export_artifact", {"subject": handle, "format": "dxf"})["error"]
    assert refused["code"] == -32000 and "has none" in refused["message"]
