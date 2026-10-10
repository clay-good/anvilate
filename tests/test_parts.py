"""The everyday parts: each example builds to its closed-form volume, and says it is unchecked.

expand-drawable-parts, group 4. One worked example per part lives in ``examples/parts``,
and every test here starts from one of them, so the examples are the fixtures: the volume of
each is derived by hand below from the numbers in its file, a dimension that cannot be made
is refused by name, and a part with no screen is reported as drawn and not checked.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")

from anvilate import patterns, projection  # noqa: E402
from anvilate.geometry import GeometryError, build_spec, measure_geometry  # noqa: E402
from anvilate.packs import parts  # noqa: E402
from anvilate.scorecard import CheckStatus  # noqa: E402
from anvilate.screening import element_registry, screen_spec  # noqa: E402
from anvilate.spec import load_spec_yaml  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "parts"
_PARTS = tuple(sorted(name.removeprefix("screen_") for name in parts.__all__ if "screen_" in name))


def _document(element_type: str) -> dict:
    return yaml.safe_load((_EXAMPLES / f"{element_type}.spec.yaml").read_text(encoding="utf-8"))


def _spec(element_type: str, **changes):
    """The example for ``element_type``, with ``changes`` made to its element parameters."""
    document = copy.deepcopy(_document(element_type))
    for path, value in changes.items():
        target, *rest = path.split("__")
        node = document["element_params"]
        for step in [target, *rest][:-1]:
            node = node[int(step)] if step.isdigit() else node[step]
        last = [target, *rest][-1]
        if value is None:
            node.pop(last, None)
        else:
            node[int(last) if last.isdigit() else last] = value
    return load_spec_yaml(yaml.safe_dump(document))


def _mm(value: float) -> dict:
    return {"magnitude": value, "unit": "mm"}


def _disc(diameter: float) -> float:
    return math.pi * diameter**2 / 4


def _corners(radius: float) -> float:
    """What rounding four square corners removes from a rectangle's area."""
    return (4 - math.pi) * radius**2


def _keyway(radius: float, width: float, depth: float, length: float) -> float:
    """A flat-bottomed keyway: the cap of the circle beyond ``radius - depth``, ``width`` wide."""
    half = width / 2
    cap = half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)
    return (cap - width * (radius - depth)) * length


def _chamfer(diameter: float, size: float) -> float:
    """What a ``size`` x 45 degree chamfer takes off the end of a cylinder."""
    big, small = diameter / 2, diameter / 2 - size
    return math.pi * big**2 * size - math.pi * size / 3 * (big**2 + big * small + small**2)


def _groove(outer_radius: float, depth: float, top: float, angle_deg: float) -> float:
    """A V groove turned into a rim: its width grows linearly from the root to the rim."""
    root = outer_radius - depth
    bottom = top - 2 * depth * math.tan(math.radians(angle_deg) / 2)
    slope = (top - bottom) / depth
    # The integral of 2 pi r (bottom + slope (r - root)) dr from the root to the rim.
    return (
        2
        * math.pi
        * (
            bottom * (outer_radius**2 - root**2) / 2
            + slope * ((outer_radius**3 - root**3) / 3 - root * (outer_radius**2 - root**2) / 2)
        )
    )


_VOLUMES = {
    # 120 x 80 x 6 with 8 mm corners, four 6.6 holes, a 6.6 hole counterbored 11 x 3, and a
    # 30 x 6 slot.
    "mounting_plate": (120 * 80 - _corners(8)) * 6
    - 5 * _disc(6.6) * 6
    - (_disc(11) - _disc(6.6)) * 3
    - (_disc(6) + 24 * 6) * 6,
    # Two 5 mm legs 50 wide (60 along the base, 75 more up), a 25 mm rib 5 thick, two 6.6
    # holes and a 20 x 6.6 slot.
    "angle_bracket": 60 * 50 * 5
    + 75 * 50 * 5
    + 25 * 25 / 2 * 5
    - 2 * _disc(6.6) * 5
    - (_disc(6.6) + 13.4 * 6.6) * 5,
    "plate_flange": (_disc(120) - _disc(50) - 6 * _disc(9)) * 12,
    "spacer": (_disc(12) - _disc(6.4)) * 10,
    "bushing": (_disc(16) - _disc(12)) * 20 + (_disc(22) - _disc(16)) * 2,
    # A regular hexagon 8 across flats has area (sqrt(3) / 2) * 8^2.
    "standoff": (math.sqrt(3) / 2 * 8**2 - _disc(3.3)) * 25,
    "shaft_collar": (_disc(40) - _disc(20)) * 15,
    "stepped_shaft": _disc(20) * 40
    + _disc(30) * 60
    + _disc(25) * 30
    - _chamfer(20, 1)
    - _chamfer(25, 1)
    - _keyway(10, 6, 3.5, 25),
    "pulley": (_disc(100) - _disc(20)) * 20 - _groove(50, 11, 13, 38),
    # A 40 x 30 x 50 block, a 20 mm gap 38 deep, and a 12 mm pin through two 10 mm ears.
    "clevis": 40 * 30 * 50 - 20 * 30 * 38 - _disc(12) * 20,
    "tube": (40 * 20 - 36 * 16) * 300,
    # The 40 mm module less four 10 x 10 slot mouths.
    "t_slot_extrusion": (40 * 40 - 4 * 10 * 10) * 500,
    # Straights of 30-4, 50-8 and 25-4 in 2 mm sheet, and two quarter bends from R2 to R4.
    "sheet_metal_bracket": ((26 + 42 + 21) * 2 + 2 * math.pi / 4 * (4**2 - 2**2)) * 40,
    # 120 x 80 x 40 outside with 6 mm corners, hollowed 114 x 74 with 3 mm corners above a
    # 3 mm floor, and four 4.5 holes in the floor.
    "enclosure": (120 * 80 - _corners(6)) * 40 - (114 * 74 - _corners(3)) * 37 - 4 * _disc(4.5) * 3,
}


def test_every_part_has_an_example_a_pattern_and_a_volume():
    """The floor: a part added without its example or its hand-derived volume fails here."""
    assert len(_PARTS) == 14
    assert {path.name.removesuffix(".spec.yaml") for path in _EXAMPLES.glob("*.spec.yaml")} >= set(
        _PARTS
    )
    assert set(_VOLUMES) == set(_PARTS)
    assert set(_PARTS) <= set(patterns.patterns()) and set(_PARTS) <= set(element_registry())


@pytest.mark.parametrize("element_type", _PARTS)
def test_the_example_builds_to_its_closed_form_volume(element_type):
    built = build_spec(_spec(element_type))
    assert built.is_valid and built.pattern == f"{element_type}/1"
    assert built.volume_mm3 == pytest.approx(_VOLUMES[element_type], rel=1e-6)


@pytest.mark.parametrize("element_type", _PARTS)
def test_a_part_rebuilds_the_same_and_its_summary_round_trips(element_type):
    first, second = build_spec(_spec(element_type)), build_spec(_spec(element_type))
    assert first.signature == second.signature
    assert first.volume_mm3 == second.volume_mm3
    summary = first.summary()
    assert type(summary).model_validate_json(summary.model_dump_json(by_alias=True)) == summary
    assert summary.face_tags == tuple(sorted(first.faces))
    assert [feature.tag for feature in summary.features] == [f.tag for f in first.features]


_TAGS = {
    "mounting_plate": {"top", "bottom", "left", "right", "front", "back", "round"},
    "angle_bracket": {"top", "bottom", "left", "right", "front", "back", "round", "inclined"},
    "plate_flange": {"top", "bottom", "round"},
    "spacer": {"top", "bottom", "round"},
    "bushing": {"top", "bottom", "round"},
    "standoff": {"top", "bottom", "front", "back", "inclined", "round"},
    "shaft_collar": {"top", "bottom", "round"},
    "stepped_shaft": {"top", "bottom", "front", "back", "right", "round", "curved"},
    "pulley": {"top", "bottom", "round", "curved"},
    "clevis": {"top", "bottom", "left", "right", "front", "back", "round"},
    "tube": {"top", "bottom", "left", "right", "front", "back"},
    "t_slot_extrusion": {"top", "bottom", "left", "right", "front", "back"},
    "sheet_metal_bracket": {"top", "bottom", "left", "right", "front", "back", "round"},
    "enclosure": {"top", "bottom", "left", "right", "front", "back", "round"},
}


@pytest.mark.parametrize("element_type", _PARTS)
def test_faces_are_named_by_direction_and_every_face_has_a_name(element_type):
    built = build_spec(_spec(element_type))
    assert set(built.faces) == _TAGS[element_type]
    assert sum(len(faces) for faces in built.faces.values()) == len(built.shape.faces())


@pytest.mark.parametrize("element_type", _PARTS)
def test_every_view_draws_with_no_code_of_the_parts_own(element_type):
    built = build_spec(_spec(element_type))
    for view in projection.VIEWS:
        svg, height = projection.render_view(
            built.shape, built.faces, name=built.name, view=view, width_px=480
        )
        assert height > 0 and b"<path" in svg, (element_type, view)


@pytest.mark.parametrize("element_type", _PARTS)
def test_a_part_with_no_screen_says_it_was_drawn_and_not_checked(element_type):
    from anvilate.export.gate import ExportRefused, authorize_export

    card = screen_spec(_spec(element_type))
    drawn = [entry for entry in card.entries if "drawn" in entry.detail]
    assert drawn and all(entry.status is CheckStatus.NOT_EVALUATED for entry in drawn)
    assert not card.passed
    with pytest.raises(ExportRefused):
        authorize_export(card)
    assert authorize_export(card, override=True).validated is False


@pytest.mark.parametrize(
    ("element_type", "changes", "reason"),
    [
        ("mounting_plate", {"corner_radius": _mm(40)}, "corner_radius"),
        ("mounting_plate", {"hole_patterns__0__pitch_x": _mm(116)}, "does not fit"),
        ("mounting_plate", {"slots__0__y": _mm(0)}, "overlap"),
        ("mounting_plate", {"holes__0__counterbore_depth": _mm(6)}, "stop inside"),
        ("angle_bracket", {"thickness": _mm(60)}, "thickness"),
        ("angle_bracket", {"base_holes__0__y": _mm(0), "base_holes__0__x": _mm(-15)}, "rib"),
        ("angle_bracket", {"rib_leg": _mm(70)}, "rib_leg"),
        ("angle_bracket", {"upright_slots__0__x": _mm(20)}, "does not fit"),
        ("plate_flange", {"bore_diameter": _mm(85)}, "overlap"),
        ("plate_flange", {"bolt_circle_diameter": _mm(115)}, "does not fit"),
        ("plate_flange", {"bore_diameter": _mm(120)}, "bore_diameter"),
        ("spacer", {"inner_diameter": _mm(12)}, "inner_diameter"),
        ("bushing", {"flange_diameter": _mm(16)}, "flange_diameter"),
        ("bushing", {"flange_thickness": _mm(20)}, "flange_thickness"),
        ("standoff", {"hole_diameter": _mm(8)}, "hole_diameter"),
        ("shaft_collar", {"bore": _mm(40)}, "bore"),
        ("stepped_shaft", {"keyways__0__length": _mm(40)}, "runs 45 mm along"),
        ("stepped_shaft", {"keyways__0__depth": _mm(10)}, "does not fit"),
        ("stepped_shaft", {"end_chamfer": _mm(10)}, "end_chamfer"),
        ("pulley", {"groove_depth": _mm(30)}, "closes before"),
        ("pulley", {"bore": _mm(80)}, "bottom of the groove"),
        ("pulley", {"groove_width": _mm(20)}, "groove_width"),
        ("clevis", {"gap": _mm(40)}, "gap"),
        ("clevis", {"pin_height": _mm(46)}, "does not fit"),
        ("clevis", {"base_thickness": _mm(50)}, "base_thickness"),
        ("tube", {"wall": _mm(10)}, "wall"),
        ("t_slot_extrusion", {"designation": "EXT-4041"}, "EXT-4040"),
        ("sheet_metal_bracket", {"flange_b": _mm(7)}, "shorter than its bends"),
        ("enclosure", {"wall": _mm(40)}, "wall"),
        ("enclosure", {"floor": _mm(40)}, "floor"),
        ("enclosure", {"floor_patterns__0__pitch_x": _mm(112)}, "does not fit"),
    ],
)
def test_a_dimension_that_cannot_be_made_is_refused_by_name(element_type, changes, reason):
    with pytest.raises(GeometryError, match=reason) as refused:
        build_spec(_spec(element_type, **changes))
    assert refused.value.remedies


def test_the_same_hole_is_measured_the_same_way_in_two_parts():
    """One feature vocabulary: a plate's hole and a flange's answer the same queries."""
    plate, flange = build_spec(_spec("mounting_plate")), build_spec(_spec("plate_flange"))
    assert measure_geometry(plate, "feature:m6_1_1:diameter").value == 6.6
    assert measure_geometry(plate, "feature:m6_1_1:x").value == -50.0
    assert measure_geometry(plate, "feature:cb:counterbore_diameter").value == 11.0
    assert measure_geometry(plate, "feature_count").value == 6
    assert measure_geometry(flange, "feature:bolt_1:diameter").value == 9.0
    assert measure_geometry(flange, "feature:bolt_1:x").value == 45.0
    assert measure_geometry(flange, "feature:bore:diameter").value == 50.0
    assert {feature.kind for feature in plate.features} == {"through_hole", "counterbore", "slot"}


def test_a_tapped_hole_is_a_hole_that_carries_its_thread():
    standoff = build_spec(_spec("standoff"))
    (hole,) = standoff.summary().features
    assert (hole.tag, hole.thread, hole.diameter_mm) == ("hole", "M4x0.7", 3.3)
    assert not any(face.geom_type.name == "BSPLINE" for face in standoff.shape.faces())


def test_bracket_holes_are_cut_through_the_leg_they_are_declared_on():
    bracket = build_spec(_spec("angle_bracket"))
    by_tag = {feature.tag: feature for feature in bracket.features}
    assert by_tag["b1"].axis == (0.0, 0.0, 1.0) and by_tag["s1"].axis == (1.0, 0.0, 0.0)
    # The base is 60 long and 5 thick, so its clear face is centred at x = 32.5.
    assert by_tag["b1"].position_mm == (42.5, -15.0, 5.0)
    # The upright's clear face is centred 42.5 up; the slot is 15 above that.
    assert by_tag["s1"].position_mm == (5.0, 0.0, 57.5)


def test_an_envelope_says_it_is_one():
    extrusion = build_spec(_spec("t_slot_extrusion"))
    assert extrusion.envelope and extrusion.summary().envelope is True
    assert "envelope" in extrusion.summary().model_dump(by_alias=True)
    assert "envelope" not in build_spec(_spec("spacer")).summary().model_dump(by_alias=True)
    assert patterns.patterns()["t_slot_extrusion"].envelope


def test_a_flat_length_is_stated_with_the_k_factor_it_came_from():
    """Two bends of R2 in 2 mm sheet at K = 0.44: BA = (pi/2)(2 + 0.88) each."""
    bracket = build_spec(_spec("sheet_metal_bracket"))
    allowance = math.pi / 2 * (2 + 0.44 * 2)
    assert bracket.dimensions_mm["bend_allowance"] == pytest.approx(allowance, rel=1e-12)
    assert bracket.dimensions_mm["flat_length"] == pytest.approx(89 + 2 * allowance, rel=1e-12)
    (drawn,) = [e for e in screen_spec(_spec("sheet_metal_bracket")).entries if "drawn" in e.detail]
    assert "K = 0.44 from shop bend table rev C" in drawn.detail
    assert f"flat pattern {89 + 2 * allowance:.2f} mm long" in drawn.detail
    assert f"2 bends of {allowance:.2f} mm allowance" in drawn.detail


def test_a_k_factor_is_never_invented():
    spec = _spec("sheet_metal_bracket", k_factor=None, k_factor_source=None)
    bracket = build_spec(spec)
    assert bracket.is_valid and "flat_length" not in bracket.dimensions_mm
    flat = next(entry for entry in screen_spec(spec).entries if "flat pattern" in entry.name)
    assert flat.status is CheckStatus.NOT_EVALUATED and "k_factor" in flat.detail
    assert [need.declaration for need in flat.needs] == ["element_params.k_factor"]
    with pytest.raises(GeometryError, match="k_factor_source"):
        build_spec(_spec("sheet_metal_bracket", k_factor_source=None))


def _bend_radius(**changes):
    spec = _spec("sheet_metal_bracket", **changes)
    return next(entry for entry in screen_spec(spec).entries if "bend radius" in entry.name)


def test_a_bend_tighter_than_the_sheet_takes_fails():
    """2 mm sheet at 20 % reduction of area: R_min = 2 x (50/20 - 1) = 3 mm, over the R2 drawn."""
    source = {"reduction_of_area_source": "mill certificate 4471"}
    tight = _bend_radius(reduction_of_area_percent=20.0, **source)
    assert tight.status is CheckStatus.FAIL
    assert "minimum 3 mm" in tight.detail and "mill certificate 4471" in tight.detail
    # 25 % puts the minimum exactly on the drawn 2 mm, which is not under it.
    for percent, minimum in ((25.0, "2 mm"), (40.0, "0.5 mm")):
        stated = _bend_radius(reduction_of_area_percent=percent, **source)
        assert stated.status is CheckStatus.NOT_EVALUATED
        assert f"minimum {minimum}" in stated.detail and "not a pass" in stated.detail


def test_a_reduction_of_area_is_never_invented():
    missing = _bend_radius()
    assert missing.status is CheckStatus.NOT_EVALUATED
    assert [need.declaration for need in missing.needs] == [
        "element_params.reduction_of_area_percent"
    ]
    with pytest.raises(GeometryError, match="reduction_of_area_source"):
        build_spec(_spec("sheet_metal_bracket", reduction_of_area_percent=20.0))
    with pytest.raises(GeometryError, match="at most 100"):
        build_spec(
            _spec(
                "sheet_metal_bracket",
                reduction_of_area_percent=120.0,
                reduction_of_area_source="mill certificate 4471",
            )
        )


@pytest.mark.parametrize(
    ("shape", "flanges", "box"),
    [
        ("L", {"flange_c": None}, (30.0, 40.0, 50.0)),
        ("U", {}, (50.0, 40.0, 30.0)),
        ("Z", {}, (53.0, 40.0, 50.0)),
    ],
)
def test_each_bracket_shape_has_its_outside_dimensions(shape, flanges, box):
    built = build_spec(_spec("sheet_metal_bracket", shape=shape, **flanges))
    size = built.shape.bounding_box().size
    assert (size.X, size.Y, size.Z) == pytest.approx(box, abs=1e-6)


def test_a_round_tube_and_a_plain_bushing_are_the_other_branches():
    tube = build_spec(_spec("tube", shape="round", outer_diameter=_mm(30), width=None, height=None))
    assert tube.volume_mm3 == pytest.approx((_disc(30) - _disc(26)) * 300, rel=1e-6)
    plain = build_spec(_spec("bushing", flange_diameter=None, flange_thickness=None))
    assert plain.volume_mm3 == pytest.approx((_disc(16) - _disc(12)) * 20, rel=1e-6)


@pytest.mark.parametrize(
    ("model", "fields", "reason"),
    [
        (parts.Hole, {"kind": "counterbore"}, "counterbore_diameter"),
        (parts.Hole, {"kind": "countersink"}, "head_diameter"),
        (parts.HolePattern, {"kind": "bolt_circle"}, "circle_diameter"),
        (parts.HolePattern, {"kind": "rectangular", "count_x": 2, "count_y": 1}, "pitch_x"),
        (parts.Tube, {"shape": "round"}, "outer_diameter"),
    ],
)
def test_a_declaration_missing_what_its_kind_needs_is_refused(model, fields, reason):
    base = {"tag": "h", "name": "n", "x": _mm(0), "y": _mm(0), "diameter": _mm(5)}
    base |= {"wall": _mm(2), "length": _mm(10)}
    document = {key: value for key, value in base.items() if key in model.model_fields} | fields
    with pytest.raises(ValueError, match=reason):
        model(**document)


def test_a_length_field_refuses_what_is_not_a_length():
    with pytest.raises(ValueError, match="must be a length"):
        parts.Spacer(
            name="s",
            outer_diameter={"magnitude": 12, "unit": "kN"},
            inner_diameter=_mm(6),
            length=_mm(10),
        )


@pytest.mark.parametrize("element_type", _PARTS)
def test_the_step_file_reads_back_as_one_part_with_the_solids_volume(element_type, tmp_path):
    """The sheet-metal bracket was moved into place after it was extruded, so its solid
    carried a placement, its STEP was an assembly of one, and reading that back ended the
    process with a segmentation fault. Every part is written and read back here."""
    from anvilate.export.gate import authorize_export
    from anvilate.geometry import read_step_validation_properties, write_step

    built = build_spec(_spec(element_type))
    path = write_step(
        built, tmp_path / "part.step", authorization=authorize_export(None, override=True)
    )
    text = path.read_text(encoding="utf-8")
    assert text.count("PRODUCT(") == 1 and "UNVALIDATED" in text
    assert read_step_validation_properties(path).volume_mm3 == pytest.approx(
        built.volume_mm3, rel=1e-9
    )


def test_a_solid_that_carries_a_placement_is_refused_before_it_is_read_back(tmp_path):
    import dataclasses

    from build123d import Pos

    from anvilate.export.gate import authorize_export
    from anvilate.geometry import write_step

    built = build_spec(_spec("spacer"))
    placed = dataclasses.replace(built, shape=Pos(5, 0, 0) * built.shape)
    with pytest.raises(GeometryError, match="more than one product"):
        write_step(
            placed, tmp_path / "placed.step", authorization=authorize_export(None, override=True)
        )
    assert not (tmp_path / "placed.step").exists()
