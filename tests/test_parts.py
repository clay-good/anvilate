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

from anvilate import patterns  # noqa: E402
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
    # A 120 x 80 x 3 plate with 6 mm corners; under it a lip 4 deep, set in 3.2 (so 113.6 x
    # 73.6 with 2.8 mm corners) and 2 thick (so 109.6 x 69.6 with 0.8 mm corners inside);
    # four 3.4 holes and a 12.5 hole through the plate.
    "enclosure_lid": (120 * 80 - _corners(6)) * 3
    + ((113.6 * 73.6 - _corners(2.8)) - (109.6 * 69.6 - _corners(0.8))) * 4
    - (4 * _disc(3.4) + _disc(12.5)) * 3,
}


def test_every_part_has_an_example_a_pattern_and_a_volume():
    """The floor: a part added without its example or its hand-derived volume fails here."""
    assert len(_PARTS) == 15
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
    "enclosure_lid": {"top", "bottom", "left", "right", "front", "back", "round"},
}


@pytest.mark.parametrize("element_type", _PARTS)
def test_faces_are_named_by_direction_and_every_face_has_a_name(element_type):
    built = build_spec(_spec(element_type))
    assert set(built.faces) == _TAGS[element_type]
    assert sum(len(faces) for faces in built.faces.values()) == len(built.shape.faces())


# A clevis is screened once it states the load on its pin, and its example does; without
# one it is the fifteenth drawn-only part, and is held to the same statement here.
_UNLOADED = {
    "clevis": dict.fromkeys(
        (
            "load",
            "pin_allowable_shear",
            "allowable_bearing",
            "allowable_tension",
            "allowable_shear",
        )
    )
}


@pytest.mark.parametrize("element_type", _PARTS)
def test_a_part_with_no_screen_says_it_was_drawn_and_not_checked(element_type):
    from anvilate.export.gate import ExportRefused, authorize_export

    card = screen_spec(_spec(element_type, **_UNLOADED.get(element_type, {})))
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
        ("shaft_collar", {"keyway_width": _mm(6), "keyway_depth": _mm(12)}, "cuts through"),
        ("shaft_collar", {"keyway_width": _mm(25), "keyway_depth": _mm(2)}, "keyway_width"),
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
        ("enclosure_lid", {"corner_radius": _mm(40)}, "corner_radius"),
        ("enclosure_lid", {"lip_wall": _mm(37)}, "leave no opening"),
        ("enclosure_lid", {"hole_patterns__0__pitch_x": _mm(108)}, "scr_1_1 runs into the lip"),
        ("enclosure_lid", {"hole_patterns__0__pitch_y": _mm(72)}, "scr_1_1 runs into the lip"),
        ("enclosure_lid", {"hole_patterns__0__pitch_x": _mm(118)}, "does not fit"),
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


def test_an_enclosure_lid_states_its_lip_whole_or_not_at_all():
    """A lip is three dimensions; one or two of them describe no lip, and are refused."""
    with pytest.raises(ValueError, match="lip_inset, lip_wall and lip_height"):
        build_spec(_spec("enclosure_lid", lip_wall=None))
    flat = build_spec(_spec("enclosure_lid", lip_inset=None, lip_wall=None, lip_height=None))
    holes = (4 * _disc(3.4) + _disc(12.5)) * 3
    assert flat.volume_mm3 == pytest.approx((120 * 80 - _corners(6)) * 3 - holes, rel=1e-9)
    assert measure_geometry(flat, "feature:gland:z").value == 3.0


def test_an_enclosure_lid_takes_a_hole_in_the_margin_outside_its_lip():
    """Clear of the lip is inside its opening or outside it: a wide margin takes the screws."""
    lid = build_spec(
        _spec(
            "enclosure_lid",
            lip_inset=_mm(10),
            hole_patterns__0__pitch_x=_mm(110),
            hole_patterns__0__pitch_y=_mm(70),
        )
    )
    assert measure_geometry(lid, "feature:scr_1_1:x").value == -55.0
    assert measure_geometry(lid, "feature:scr_1_1:z").value == 7.0
    assert measure_geometry(lid, "feature:scr_1_1:depth").value == 3.0
    # 10 mm in, the lip starts at x = -50: a 3.4 hole at -51 stands on it, and is refused.
    with pytest.raises(GeometryError, match="runs into the lip"):
        build_spec(_spec("enclosure_lid", lip_inset=_mm(10), hole_patterns__0__pitch_x=_mm(102)))


def test_an_enclosure_lid_drops_into_the_enclosure_it_is_drawn_for():
    """The two examples are one box: the lid covers it, and its lip clears the walls."""
    box, lid = (
        _document("enclosure")["element_params"],
        _document("enclosure_lid")["element_params"],
    )
    for side in ("width", "length", "corner_radius"):
        assert lid[side] == box[side]
    clearance = lid["lip_inset"]["magnitude"] - box["wall"]["magnitude"]
    assert clearance == pytest.approx(0.2)
    assert lid["lip_height"]["magnitude"] < box["height"]["magnitude"] - box["wall"]["magnitude"]


def _mpa(value: float) -> dict:
    return {"magnitude": value, "unit": "MPa"}


def _checks(card) -> dict:
    return {entry.name.removeprefix("rod-end-clevis "): entry for entry in card.entries}


def test_a_loaded_clevis_is_screened_on_its_pin_and_its_ears():
    """20 kN on a 12 mm pin through two 10 mm ears, 30 wide, the hole 10 below their top.

    The pin shears on two planes of pi 12^2/4; the ears bear on 2 x 12 x 10, pull apart on
    2 x (30 - 12) x 10 and tear out on four planes of 10 x 10.
    """
    from anvilate.export.gate import authorize_export

    card = screen_spec(_spec("clevis"))
    checks = _checks(card)
    expected = {
        "pin shear": (20000 / (2 * _disc(12)), 240),
        "ear bearing": (20000 / 240, 250),
        "ear net tension": (20000 / 360, 250),
        "ear shear-out": (20000 / 400, 145),
    }
    for name, (stress, allowable) in expected.items():
        entry = checks[name]
        assert entry.status is CheckStatus.PASS, name
        assert entry.safety_factor == pytest.approx(allowable / stress, rel=1e-12), name
        assert entry.required_safety_factor == 2.0
        assert entry.derivation.result.value.to("MPa").magnitude == pytest.approx(stress)
    assert not any("drawn" in entry.detail for entry in card.entries)
    assert card.passed and authorize_export(card).validated


@pytest.mark.parametrize(
    ("check", "allowable", "at_the_margin"),
    [
        # Each allowable sits a hair under twice its stress, so only that check fails.
        ("pin shear", "pin_allowable_shear", 2 * 20000 / (2 * math.pi * 12**2 / 4)),
        ("ear bearing", "allowable_bearing", 2 * 20000 / 240),
        ("ear net tension", "allowable_tension", 2 * 20000 / 360),
        ("ear shear-out", "allowable_shear", 2 * 20000 / 400),
    ],
)
def test_each_clevis_check_fails_alone_under_twice_its_stress(check, allowable, at_the_margin):
    failing = _checks(screen_spec(_spec("clevis", **{allowable: _mpa(at_the_margin * 0.999)})))
    assert failing[check].status is CheckStatus.FAIL
    assert [n for n, e in failing.items() if e.status is CheckStatus.FAIL] == [check]
    passing = _checks(screen_spec(_spec("clevis", **{allowable: _mpa(at_the_margin * 1.001)})))
    assert passing[check].status is CheckStatus.PASS
    # An allowable nobody declared is not assumed: that check alone is not evaluated.
    missing = _checks(screen_spec(_spec("clevis", **{allowable: None})))
    assert missing[check].status is CheckStatus.NOT_EVALUATED
    assert [need.declaration for need in missing[check].needs] == [f"element_params.{allowable}"]
    assert sum(e.status is CheckStatus.NOT_EVALUATED for e in missing.values()) == 1


def test_a_clevis_is_judged_against_the_documents_safety_factor():
    document = _document("clevis")
    document["constraints"] = {"min_safety_factor": {"value": 2.8, "origin": "user_stated"}}
    checks = _checks(screen_spec(load_spec_yaml(yaml.safe_dump(document))))
    assert checks["pin shear"].status is CheckStatus.FAIL  # 2.71
    assert checks["ear shear-out"].status is CheckStatus.PASS  # 2.90
    assert checks["pin shear"].required_safety_factor == 2.8


def test_a_clevis_load_is_a_force_and_an_ear_with_no_section_is_not_passed():
    for changes, reason in (
        ({"load": _mm(20)}, "load must be a force"),
        ({"allowable_shear": {"magnitude": 1.0, "unit": "kN"}}, "allowable_shear must be a stress"),
        ({"load": {"magnitude": 0.0, "unit": "kN"}}, "load must be greater than zero"),
    ):
        card = screen_spec(_spec("clevis", **changes))
        (refused,) = [entry for entry in card.entries if reason in entry.detail]
        assert refused.status is CheckStatus.NOT_EVALUATED and not card.passed
    # The hole's edge at the top of the ear: nothing is left to tear through.
    torn = _checks(screen_spec(_spec("clevis", pin_height=_mm(44))))
    assert torn["ear shear-out"].status is CheckStatus.NOT_EVALUATED
    assert "reaches the top of the ear" in torn["ear shear-out"].detail
    # A pin as wide as the ear, and ears of no thickness.
    assert _checks(screen_spec(_spec("clevis", pin_diameter=_mm(30))))[
        "ear net tension"
    ].status is (CheckStatus.NOT_EVALUATED)
    closed = _checks(screen_spec(_spec("clevis", gap=_mm(40))))
    for name in ("ear bearing", "ear net tension", "ear shear-out"):
        assert closed[name].status is CheckStatus.NOT_EVALUATED, name


def test_a_shaft_collar_takes_a_keyseat_along_its_bore():
    """An 8 x 3.3 keyseat in a 20 mm bore, 15 mm long: the slot less what the bore already took."""
    keyed = build_spec(_spec("shaft_collar", keyway_width=_mm(8), keyway_depth=_mm(3.3)))
    plain = build_spec(_spec("shaft_collar"))
    strip = 4 * math.sqrt(10**2 - 4**2) + 10**2 * math.asin(4 / 10)  # of the bore, |y| < 4, x > 0
    assert plain.volume_mm3 - keyed.volume_mm3 == pytest.approx((8 * 13.3 - strip) * 15, rel=1e-9)
    assert (keyed.dimensions_mm["keyway_width"], keyed.dimensions_mm["keyway_depth"]) == (8.0, 3.3)
    with pytest.raises(ValueError, match="keyway_width and keyway_depth"):
        build_spec(_spec("shaft_collar", keyway_width=_mm(8)))


def test_a_shaft_says_where_each_keyway_is():
    shaft = build_spec(_spec("stepped_shaft")).dimensions_mm
    # Step 1 is 20 mm across and starts at the drive end; the keyway is 5 mm along it.
    assert (shaft["keyway_1_start"], shaft["keyway_1_diameter"]) == (5.0, 20.0)


def _loaded_bracket(**changes):
    stated = {
        "load": {"magnitude": 1.0, "unit": "kN"},
        "load_height": _mm(60),
        "allowable_bending": _mpa(150),
        "allowable_bearing": _mpa(250),
        **changes,
    }
    card = screen_spec(_spec("angle_bracket", **stated))
    return {e.name.removeprefix("shelf-angle-bracket "): e for e in card.entries}, card


def test_a_loaded_angle_bracket_is_screened_on_its_upright_and_its_base_holes():
    """1 kN on the upright 60 mm up a 50 x 5 bracket, fixed by two 6.6 mm holes.

    The upright bends about the top of the base leg, 55 mm below the load: 6 x 1000 x 55 /
    (50 x 5^2) = 264 MPa. The two holes bear 1000 / (2 x 6.6 x 5) = 15.15 MPa.
    """
    checks, card = _loaded_bracket()
    assert checks["leg bending"].safety_factor == pytest.approx(150 / 264)
    assert checks["bolt bearing"].safety_factor == pytest.approx(250 / (1000 / 66))
    assert checks["leg bending"].status is CheckStatus.FAIL
    assert checks["bolt bearing"].status is CheckStatus.PASS
    assert checks["leg bending"].derivation.result.value.to("MPa").magnitude == pytest.approx(264)
    assert not any("drawn" in e.detail for e in card.entries) and not card.passed
    # A load a third as high bends the upright a third as much, about the same root.
    low, _card = _loaded_bracket(load_height=_mm(5 + 55 / 3))
    assert low["leg bending"].safety_factor == pytest.approx(3 * 150 / 264)
    # A thicker allowable passes, and an allowable nobody declared is not assumed.
    assert _loaded_bracket(allowable_bending=_mpa(530))[0]["leg bending"].status is CheckStatus.PASS
    bare, _card = _loaded_bracket(allowable_bearing=None)
    assert bare["bolt bearing"].status is CheckStatus.NOT_EVALUATED
    assert [n.declaration for n in bare["bolt bearing"].needs] == [
        "element_params.allowable_bearing"
    ]


def test_a_bracket_load_has_a_height_on_the_upright_and_holes_to_bear_on():
    for changes, reason in (
        ({"load_height": None}, "states its load and the load_height it acts at"),
        ({"load_height": _mm(81)}, "above the top of the upright"),
        ({"load": _mm(5)}, "load must be a force"),
        ({"allowable_bending": {"magnitude": 1.0, "unit": "kN"}}, "must be a stress"),
    ):
        card = screen_spec(_spec("angle_bracket", **{**_BRACKET_LOAD, **changes}))
        (refused,) = [entry for entry in card.entries if reason in entry.detail]
        assert refused.status is CheckStatus.NOT_EVALUATED, reason
    # At the height of the base leg there is no arm, and with no round hole nothing bears.
    flat, _card = _loaded_bracket(load_height=_mm(5))
    assert flat["leg bending"].status is CheckStatus.NOT_EVALUATED
    assert "not above the base leg" in flat["leg bending"].detail
    bare, _card = _loaded_bracket(base_holes=[])
    assert bare["bolt bearing"].status is CheckStatus.NOT_EVALUATED
    assert "no round hole" in bare["bolt bearing"].detail


_BRACKET_LOAD = {
    "load": {"magnitude": 1.0, "unit": "kN"},
    "load_height": _mm(60),
    "allowable_bending": _mpa(150),
    "allowable_bearing": _mpa(250),
}
