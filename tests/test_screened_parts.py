"""Elements a pack already screened, now drawn (expand-drawable-parts, group 3).

A lifting lug, a shaft key, a spring, a bearing, a gear pair and a rolled member each had a
card and no picture. Each is drawn from what its element declares or from the bundled table
its designation names, and these hold three things: the solid is the closed form, a
dimension the drawing needs and the screen never did is asked for by name rather than
guessed, and being drawn changes nothing on the card.
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
from anvilate.screening import screen_spec  # noqa: E402
from anvilate.spec import load_spec_yaml  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "parts"
_DRAWN = (
    "beam_column_member",
    "beam_member",
    "column_member",
    "gusset_plate",
    "helical_compression_spring",
    "lifting_lug",
    "pipe_run",
    "rolling_bearing",
    "shaft_key",
    "shear_plate",
    "spur_gear_mesh",
    "tension_member",
)


def _spec(element_type: str, **changes):
    document = copy.deepcopy(
        yaml.safe_load((_EXAMPLES / f"{element_type}.spec.yaml").read_text(encoding="utf-8"))
    )
    for name, value in changes.items():
        if value is None:
            document["element_params"].pop(name, None)
        else:
            document["element_params"][name] = value
    return load_spec_yaml(yaml.safe_dump(document))


def _mm(value: float) -> dict:
    return {"magnitude": value, "unit": "mm"}


def _mm2(value: float) -> dict:
    return {"magnitude": value, "unit": "mm**2"}


def _disc(diameter: float) -> float:
    return math.pi * diameter**2 / 4


def _lens(first: float, second: float, apart: float) -> float:
    """The area two circles of these radii share when their centres are ``apart``."""
    a = (apart**2 + first**2 - second**2) / (2 * apart)
    b = apart - a
    return (
        first**2 * math.acos(a / first)
        - a * math.sqrt(first**2 - a**2)
        + second**2 * math.acos(b / second)
        - b * math.sqrt(second**2 - b**2)
    )


# IPE 200 is 200 x 100 with a 5.6 web, 8.5 flanges and 12 mm root radii: 2,848 mm^2, the
# figure EN 10365 tabulates for it.
_IPE_200 = 2 * 100 * 8.5 + (200 - 17) * 5.6 + (4 - math.pi) * 12**2

_VOLUMES = {
    "beam_column_member": _IPE_200 * 3000,
    "beam_member": _IPE_200 * 4000,
    "column_member": _IPE_200 * 3000,
    # 300 x 250 x 10 with four 22 mm holes.
    "gusset_plate": (300 * 250 - 4 * _disc(22)) * 10,
    # 100 x 240 x 10 with three 22 mm holes; 100 x 400 x 10 with two 18 mm holes.
    "shear_plate": (100 * 240 - 3 * _disc(22)) * 10,
    "tension_member": (100 * 400 - 2 * _disc(18)) * 10,
    # A 3 mm wire on a 24 mm mean coil occupies the tube from 21 to 27 mm, 200 long.
    "helical_compression_spring": (_disc(27) - _disc(21)) * 200,
    # 80 wide and 12 thick, the hole 90 up, a half disc above it, less the 25 mm pin hole.
    "lifting_lug": (80 * 90 + _disc(80) / 2 - _disc(25)) * 12,
    # NPS 2 schedule 40 is 60.3 outside with a 3.91 wall in ASME B36.10M, so 52.48 inside.
    "pipe_run": (_disc(60.3) - _disc(60.3 - 2 * 3.91)) * 3000,
    # A 6204 is 20 x 47 x 14 in ISO 15.
    "rolling_bearing": (_disc(47) - _disc(20)) * 14,
    "shaft_key": 40 * 4 * 20,
    # Module 2, 18 and 54 teeth: tip circles of 40 and 112 mm, 72 mm apart, 40 mm wide.
    "spur_gear_mesh": (_disc(40) + _disc(112) - _lens(20, 56, 72)) * 40,
}


def test_the_floor_and_the_table_agree():
    assert set(_VOLUMES) == set(_DRAWN) and set(_DRAWN) <= set(patterns.patterns())
    assert _IPE_200 == pytest.approx(2848, abs=0.5)
    assert all(patterns.patterns()[name].screened for name in _DRAWN)


@pytest.mark.parametrize("element_type", _DRAWN)
def test_the_example_builds_to_its_closed_form_volume(element_type):
    built = build_spec(_spec(element_type))
    assert built.is_valid and built.pattern == f"{element_type}/1"
    assert built.volume_mm3 == pytest.approx(_VOLUMES[element_type], rel=1e-6)
    again = build_spec(_spec(element_type))
    assert again.signature == built.signature and again.volume_mm3 == built.volume_mm3


def test_being_drawn_changes_nothing_on_the_card():
    """`hole_height` and `designation` are for the drawing. No check reads either."""
    for element_type, field in (
        ("lifting_lug", "hole_height"),
        ("rolling_bearing", "designation"),
        ("pipe_run", "designation"),
        ("shear_plate", "outline"),
        ("tension_member", "outline"),
        ("gusset_plate", "outline"),
    ):
        with_it = screen_spec(_spec(element_type))
        without = screen_spec(_spec(element_type, **{field: None}))
        assert [(e.name, e.status, e.detail) for e in with_it.entries] == [
            (e.name, e.status, e.detail) for e in without.entries
        ], element_type


@pytest.mark.parametrize(
    ("element_type", "changes", "reason"),
    [
        ("lifting_lug", {"hole_height": None}, "add element_params.hole_height"),
        ("rolling_bearing", {"designation": None}, "add element_params.designation"),
        (
            "rolling_bearing",
            {"designation": "6240"},
            "no bundled bearing is designated .6240.; closest: 62",
        ),
        ("pipe_run", {"designation": None}, "add element_params.designation"),
        ("shear_plate", {"outline": None}, "add element_params.outline"),
        ("tension_member", {"outline": None}, "add element_params.outline"),
        ("gusset_plate", {"outline": None}, "add element_params.outline"),
        # 240 x 10 is 2,400 mm2 of gross shear plane, and three 22 mm holes leave 1,740.
        (
            "shear_plate",
            {"gross_shear_area": _mm2(2500)},
            "gross_shear_area is 2500 mm² and the outline has 2400 mm² there, more than 0.5%",
        ),
        ("shear_plate", {"gross_shear_area": _mm2(2300)}, "gross_shear_area is 2300 mm²"),
        (
            "shear_plate",
            {"net_shear_area": _mm2(1800)},
            "net_shear_area is 1800 mm² and the outline has 1740 mm² there, less by more",
        ),
        # 100 x 10 is 1,000 mm2 across the bar, and two 18 mm holes on one line leave 640.
        ("tension_member", {"gross_area": _mm2(1100)}, "gross_area is 1100 mm²"),
        ("tension_member", {"net_area": _mm2(700)}, "the outline has 640 mm² there"),
        # A gusset's block cannot tear on more than its width, or twice its length.
        ("gusset_plate", {"net_tension_area": _mm2(3100)}, "the outline has 3000 mm² there"),
        ("gusset_plate", {"net_shear_area": _mm2(5100)}, "the outline has 5000 mm² there"),
        (
            "pipe_run",
            {"designation": "NPS 2 SCH 41"},
            "no bundled pipe is designated .NPS 2 SCH 41.; closest: NPS 2 SCH 40",
        ),
        ("pipe_run", {"designation": "2 in sch 40"}, "no bundled pipe is designated"),
        ("pipe_run", {"diameter": _mm(50)}, "the bore of NPS 2 SCH 40 is 52.48 mm"),
        ("helical_compression_spring", {"wire_diameter": _mm(30)}, "wire_diameter"),
        ("beam_member", {"section": "IPE 201"}, "IPE 200"),
    ],
)
def test_what_the_drawing_needs_is_asked_for_by_name(element_type, changes, reason):
    with pytest.raises(GeometryError, match=reason) as refused:
        build_spec(_spec(element_type, **changes))
    assert refused.value.remedies


def test_a_member_stating_its_properties_is_not_given_a_shape():
    """Area and second moments do not say whether the section is an I, a box or a bar."""
    document = yaml.safe_load((_EXAMPLES / "beam_member.spec.yaml").read_text(encoding="utf-8"))
    document["element_params"]["section"] = {
        "area": {"magnitude": 2848.0, "unit": "mm**2"},
        "second_moment": {"magnitude": 1.943e7, "unit": "mm**4"},
        "extreme_fibre": _mm(100.0),
    }
    spec = load_spec_yaml(yaml.safe_dump(document))
    assert screen_spec(spec).entries
    with pytest.raises(GeometryError, match="named rolled profile"):
        build_spec(spec)


def test_a_lug_carries_its_pin_hole_as_a_feature():
    lug = build_spec(_spec("lifting_lug"))
    (pin,) = lug.features
    assert (pin.tag, pin.kind, pin.diameter_mm) == ("pin", "through_hole", 25.0)
    assert pin.position_mm == (0.0, -6.0, 90.0) and pin.axis == (0.0, -1.0, 0.0)
    assert measure_geometry(lug, "feature:pin:diameter").value == 25.0
    assert lug.dimensions_mm["height"] == 130.0
    box = lug.shape.bounding_box().size
    assert (box.X, box.Y, box.Z) == pytest.approx((80.0, 12.0, 130.0), abs=1e-6)


def test_an_envelope_is_labelled_one_and_a_made_part_is_not():
    for element_type in _DRAWN:
        built = build_spec(_spec(element_type))
        expected = element_type in (
            "helical_compression_spring",
            "pipe_run",
            "rolling_bearing",
            "spur_gear_mesh",
        )
        assert built.envelope is expected and built.summary().envelope is expected, element_type


def test_a_gear_pair_states_its_circles():
    """Module 2 with 18 and 54 teeth: pitch 36 and 108, tips +2m, roots -2.5m, 72 apart."""
    pair = build_spec(_spec("spur_gear_mesh")).dimensions_mm
    assert (pair["pinion_pitch_diameter"], pair["gear_pitch_diameter"]) == (36.0, 108.0)
    assert (pair["pinion_tip_diameter"], pair["gear_tip_diameter"]) == (40.0, 112.0)
    assert (pair["pinion_root_diameter"], pair["gear_root_diameter"]) == (31.0, 103.0)
    assert pair["centre_distance"] == 72.0


def test_a_beam_lies_and_a_column_stands():
    beam = build_spec(_spec("beam_member")).shape.bounding_box().size
    column = build_spec(_spec("column_member")).shape.bounding_box().size
    assert (beam.X, beam.Y, beam.Z) == pytest.approx((100.0, 4000.0, 200.0), abs=1e-6)
    assert (column.X, column.Y, column.Z) == pytest.approx((100.0, 200.0, 3000.0), abs=1e-6)
    assert build_spec(_spec("beam_member")).dimensions_mm["section_area"] == pytest.approx(
        _IPE_200, rel=1e-12
    )


def test_a_pipe_run_is_drawn_only_as_the_pipe_its_head_loss_was_worked_from():
    """The declared bore and the designation's agree to half a percent, or nothing is drawn.

    NPS 2 schedule 40 has a 52.48 mm bore, so half a percent is 0.2624 mm either side.
    """
    run = build_spec(_spec("pipe_run", diameter=_mm(52.7)))
    assert run.dimensions_mm["inside_diameter"] == pytest.approx(52.48)
    assert run.dimensions_mm["wall_thickness"] == 3.91
    box = run.shape.bounding_box().size
    assert (box.X, box.Y, box.Z) == pytest.approx((60.3, 3000.0, 60.3), abs=1e-6)
    for apart in (52.2, 52.76):
        with pytest.raises(GeometryError, match="more than 0.5% apart"):
            build_spec(_spec("pipe_run", diameter=_mm(apart)))
    # The same bore in schedule 80 is a different pipe: 5.54 mm of wall leaves 49.22 mm.
    with pytest.raises(GeometryError, match="the bore of NPS 2 SCH 80 is 49.22 mm"):
        build_spec(_spec("pipe_run", designation="NPS 2 SCH 80"))


def test_the_end_of_a_long_pipe_is_drawn_round():
    """A view is fitted to what it shows, so its curves are cut to that and not to the part.

    Seen from its end a 3 m pipe is 60.3 mm across and fills the panel. Cut to a fraction
    of the pipe's length, each circle was eight chords and the bore a polygon. A chord's
    middle now sits within a thousandth of the view of the circle it stands for.
    """
    from anvilate import projection

    run = build_spec(_spec("pipe_run"))
    camera = projection._Camera(run.shape, "front")
    assert camera.size == pytest.approx(3000.0) and camera.seen == pytest.approx(60.3)
    visible, _hidden = projection._hidden_lines(run.shape, camera)
    curves = [line for line in visible if len(line) > 2]
    assert curves
    for line in curves:
        for first, second in zip(line, line[1:], strict=False):
            radius = math.hypot(*first)
            middle = math.hypot((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
            assert radius - middle < 0.001 * camera.seen


def test_a_net_area_may_be_smaller_than_the_drawn_one_and_a_gross_area_may_not():
    """A net area carries a hole allowance the drawing does not; a gross area carries none.

    The shear tab's holes are drawn at 22 mm and its net area is worked at 24, so 1,680
    against a drawn 1,740 is the same plate. Half a percent either way is the same too.
    """
    for changes in (
        {},
        {"net_shear_area": _mm2(900)},
        {"net_shear_area": _mm2(1740 * 1.004)},
        {"gross_shear_area": _mm2(2400 * 1.004)},
        {"gross_shear_area": _mm2(2400 * 0.996)},
    ):
        assert build_spec(_spec("shear_plate", **changes)).is_valid, changes


def test_holes_count_against_a_net_section_only_where_one_line_crosses_them():
    """Two 18 mm holes side by side take 36 mm of the bar's width; staggered, 18."""
    document = yaml.safe_load((_EXAMPLES / "tension_member.spec.yaml").read_text("utf-8"))
    outline = document["element_params"]["outline"]
    outline.pop("hole_patterns")
    outline["holes"] = [
        {"tag": "a", "x": _mm(-25), "y": _mm(150), "diameter": _mm(18)},
        {"tag": "b", "x": _mm(25), "y": _mm(100), "diameter": _mm(18)},
    ]
    document["element_params"]["net_area"] = _mm2(820)  # (100 - 18) x 10
    assert build_spec(load_spec_yaml(yaml.safe_dump(document))).is_valid
    outline["holes"][1]["y"] = _mm(150)
    with pytest.raises(GeometryError, match="the outline has 640 mm² there"):
        build_spec(load_spec_yaml(yaml.safe_dump(document)))


def test_a_member_may_be_a_flat_bar_named_by_its_two_dimensions():
    """`FLAT 50x10` is 50 across the load and 10 along it; `FLAT 10x50` stands on edge.

    A flat bar is its two dimensions and needs no table. The section the screen uses and
    the solid that is drawn are the same rectangle.
    """
    from anvilate.packs.structural import BeamMember, _flat_bar

    assert _flat_bar("FLAT 50x10") == (50.0, 10.0) and _flat_bar("FLAT 12.5x6") == (12.5, 6.0)
    assert _flat_bar("IPE 200") is None and _flat_bar("FLAT 0x10") is None
    flat = build_spec(_spec("beam_member", section="FLAT 50x10"))
    box = flat.shape.bounding_box().size
    assert (box.X, box.Y, box.Z) == pytest.approx((50.0, 4000.0, 10.0), abs=1e-6)
    assert flat.volume_mm3 == pytest.approx(50 * 10 * 4000, rel=1e-9)
    assert flat.dimensions_mm["section_area"] == 500.0
    on_edge = build_spec(_spec("beam_member", section="FLAT 10x50")).shape.bounding_box().size
    assert (on_edge.X, on_edge.Z) == pytest.approx((10.0, 50.0), abs=1e-6)
    column = build_spec(_spec("column_member", section="FLAT 50x10")).shape.bounding_box().size
    assert (column.X, column.Y, column.Z) == pytest.approx((50.0, 10.0, 3000.0), abs=1e-6)
    # The screen's section is that rectangle: I = b h^3 / 12 about the bending axis.
    document = yaml.safe_load((_EXAMPLES / "beam_member.spec.yaml").read_text("utf-8"))
    params = {**document["element_params"], "section": "FLAT 10x50"}
    section = BeamMember.model_validate(params).section
    assert section.area.to("mm**2").magnitude == pytest.approx(500.0)
    assert section.second_moment.to("mm**4").magnitude == pytest.approx(10 * 50**3 / 12)
    with pytest.raises(ValueError, match="FLAT 0x10"):
        BeamMember.model_validate({**params, "section": "FLAT 0x10"})


def test_a_member_may_be_a_round_tube_or_a_box_named_by_its_dimensions():
    """`TUBE 60x4` is outside diameter by wall; `BOX 100x50x4` is breadth, depth and wall.

    Neither needs a table. The metal that is drawn is the area the screen divides a load by,
    for every member kind, and a wall that leaves no bore is refused by name.
    """
    from anvilate.packs.structural import BeamMember, _hollow_bar

    assert _hollow_bar("TUBE 60x4") == (60.0, 4.0)
    assert _hollow_bar("BOX 100x50x4") == (100.0, 50.0, 4.0)
    assert _hollow_bar("IPE 200") is None and _hollow_bar("FLAT 50x10") is None
    assert _hollow_bar("TUBE 60") is None and _hollow_bar("BOX 100x50") is None
    document = yaml.safe_load((_EXAMPLES / "beam_member.spec.yaml").read_text("utf-8"))
    params = document["element_params"]
    tube_area = math.pi * (60**2 - 52**2) / 4
    box_area = 100 * 50 - 92 * 42
    for named, area, lying, standing in (
        ("TUBE 60x4", tube_area, (60.0, 60.0), (60.0, 60.0)),
        ("BOX 100x50x4", box_area, (100.0, 50.0), (100.0, 50.0)),
        ("BOX 50x100x4", box_area, (50.0, 100.0), (50.0, 100.0)),
    ):
        section = BeamMember.model_validate({**params, "section": named}).section
        assert section.area.to("mm**2").magnitude == pytest.approx(area, rel=1e-12)
        beam = build_spec(_spec("beam_member", section=named))
        box = beam.shape.bounding_box().size
        assert (box.X, box.Z, box.Y) == pytest.approx((*lying, 4000.0), abs=1e-6)
        assert beam.volume_mm3 == pytest.approx(area * 4000, rel=1e-6)
        assert beam.dimensions_mm["section_area"] == pytest.approx(area, rel=1e-12)
        for upright in ("column_member", "beam_column_member"):
            column = build_spec(_spec(upright, section=named))
            box = column.shape.bounding_box().size
            assert (box.X, box.Y, box.Z) == pytest.approx((*standing, 3000.0), abs=1e-6)
            assert column.volume_mm3 == pytest.approx(area * 3000, rel=1e-6)
    # The screen's section is that shape, about the bending axis: the depth is the second
    # number of a box, so the same tube on edge is stiffer.
    tube = BeamMember.model_validate({**params, "section": "TUBE 60x4"}).section
    assert tube.second_moment.to("mm**4").magnitude == pytest.approx(
        math.pi * (60**4 - 52**4) / 64, rel=1e-12
    )
    flat = BeamMember.model_validate({**params, "section": "BOX 100x50x4"}).section
    edge = BeamMember.model_validate({**params, "section": "BOX 50x100x4"}).section
    assert flat.second_moment.to("mm**4").magnitude == pytest.approx(
        (100 * 50**3 - 92 * 42**3) / 12, rel=1e-12
    )
    assert edge.second_moment.to("mm**4").magnitude == pytest.approx(
        (50 * 100**3 - 42 * 92**3) / 12, rel=1e-12
    )
    assert flat.second_moment_transverse == edge.second_moment
    for solid, reason in (
        ("TUBE 60x30", "TUBE 60x30 has a 30 mm wall.*half its outside diameter, 60 mm"),
        ("TUBE 60x0", "TUBE 60x0 has a 0 mm wall"),
        ("BOX 100x50x25", "a 25 mm wall.*half its smaller outside dimension, 50 mm"),
        ("BOX 50x100x25", "a 25 mm wall.*half its smaller outside dimension, 50 mm"),
    ):
        with pytest.raises(ValueError, match=reason):
            BeamMember.model_validate({**params, "section": solid})
        with pytest.raises(ValueError, match=reason):
            build_spec(_spec("beam_member", section=solid))
    # A near miss is not a profile nobody rolls: it is shown the spelling it wanted.
    for near in ("TUBE 60 x 4", "tube 60x4", "BOX 100x50", "HSS 100x50x4"):
        with pytest.raises(ValueError, match="`FLAT 50x10`, `TUBE 60x4`, `BOX 100x50x4`") as said:
            BeamMember.model_validate({**params, "section": near})
        assert near in str(said.value)


def test_a_member_may_be_a_pipe_named_by_its_nominal_size_and_schedule():
    """`NPS 4 SCH 40` is a pipe from the bundled ASME B36.10M table, not a dimension pair.

    A pipe's outside diameter does not follow from its nominal size, so the designation is a
    table lookup — the same table and the same spelling a pipe run is drawn from. The section
    is then computed from the two dimensions the standard publishes, which is why the whole
    table can be held to the formula exactly rather than to a tabulated area.
    """
    from anvilate.packs.structural import BeamMember, _pipe_section
    from anvilate.standards import default_pipe_schedule_table

    assert _pipe_section("IPE 200") is None and _pipe_section("TUBE 60x4") is None
    assert _pipe_section("NPS 4 SCH 40") is not None

    # Every bundled pipe, against the formula and not against a second tabulation of it.
    table = default_pipe_schedule_table()
    assert len(table.designations()) == 108
    for designation in table.designations():
        size, schedule = designation.removeprefix("NPS ").split(" SCH ")
        record = table.get(size, schedule)
        outer = record.outside_diameter.quantity.to("mm").magnitude
        wall = record.wall_thickness.quantity.to("mm").magnitude
        section = _pipe_section(designation)
        assert section is not None
        bore = outer - 2 * wall
        assert section.area.to("mm**2").magnitude == pytest.approx(
            math.pi * (outer**2 - bore**2) / 4, rel=1e-12
        ), designation
        assert section.second_moment.to("mm**4").magnitude == pytest.approx(
            math.pi * (outer**4 - bore**4) / 64, rel=1e-12
        ), designation
        assert section.wall_thickness.to("mm").magnitude == pytest.approx(wall, rel=1e-12)

    # NPS 4 pipe is 114.3 mm across, not 4 inches: the point of the lookup.
    document = yaml.safe_load((_EXAMPLES / "beam_member.spec.yaml").read_text("utf-8"))
    params = document["element_params"]
    section = BeamMember.model_validate({**params, "section": "NPS 4 SCH 40"}).section
    assert section.outside is not None
    assert section.outside[0].to("mm").magnitude == pytest.approx(114.3)
    assert section.wall_thickness.to("mm").magnitude == pytest.approx(6.02)
    area = math.pi * (114.3**2 - (114.3 - 2 * 6.02) ** 2) / 4

    # Drawn as the round tube it is, for every member kind.
    for kind, length in (("beam_member", 4000.0), ("column_member", 3000.0)):
        built = build_spec(_spec(kind, section="NPS 4 SCH 40"))
        box = built.shape.bounding_box().size
        assert sorted(round(value, 6) for value in (box.X, box.Y, box.Z)) == pytest.approx(
            sorted((114.3, 114.3, length)), abs=1e-6
        )
        assert built.volume_mm3 == pytest.approx(area * length, rel=1e-6)
        assert built.dimensions_mm["section_area"] == pytest.approx(area, rel=1e-12)

    # A size or schedule the table does not hold is refused by name, with its neighbours,
    # rather than carried on to the profile tables, which hold no pipe at all.
    with pytest.raises(ValueError, match="no bundled pipe is designated NPS 4 SCH 999") as said:
        BeamMember.model_validate({**params, "section": "NPS 4 SCH 999"})
    assert "NPS 4 SCH 40" in str(said.value)
    with pytest.raises(ValueError, match="no bundled pipe is designated NPS 99 SCH 40"):
        BeamMember.model_validate({**params, "section": "NPS 99 SCH 40"})
    # A spelling that is not the designation's is shown the one that is.
    for near in ("NPS 4 SCH40", "NPS4 SCH 40", "PIPE NPS 4 SCH 40", "NPS 4"):
        with pytest.raises(ValueError, match="`NPS 4 SCH 40`"):
            BeamMember.model_validate({**params, "section": near})


def test_a_pipe_members_wall_is_screened_and_a_slender_one_is_not_passed():
    """The round-tube wall entries a hollow member earns apply to pipe, which is one.

    Pipe is the thinnest-walled section the library names, so this is where the wall
    entries matter most: `NPS 24 SCH 10` is a slender element at D/t = 96 for A36 steel,
    and the column screen says so rather than passing on an area that is not all working.
    """
    from anvilate.packs.structural import (
        BeamMember,
        ColumnMember,
        screen_beam_member,
        screen_column_member,
    )
    from anvilate.scorecard import CheckStatus

    beam = yaml.safe_load((_EXAMPLES / "beam_member.spec.yaml").read_text("utf-8"))
    card = screen_beam_member(
        BeamMember.model_validate({**beam["element_params"], "section": "NPS 4 SCH 40"}),
        required_safety_factor=1.5,
    )
    buckling = next(entry for entry in card.entries if entry.name.endswith("wall local buckling"))
    assert buckling.status is CheckStatus.PASS
    assert buckling.reference == "AISC 360-16 Ch. F"
    assert buckling.name == "floor-beam wall local buckling"

    column = yaml.safe_load((_EXAMPLES / "column_member.spec.yaml").read_text("utf-8"))
    for designation, status, expected in (
        ("NPS 24 SCH STD", CheckStatus.PASS, "the wall is not a slender element"),
        ("NPS 24 SCH 10", CheckStatus.NOT_EVALUATED, "the wall is a slender element"),
    ):
        card = screen_column_member(
            ColumnMember.model_validate({**column["element_params"], "section": designation}),
            required_safety_factor=1.5,
        )
        entry = next(one for one in card.entries if one.name.endswith("wall slenderness"))
        assert entry.status is status, designation
        assert expected in entry.detail, designation
        assert "0.11·E/F_y = 88.0" in entry.detail


def _fetch_a_test_aisc_table(tmp_path, monkeypatch, rows: tuple[dict, ...]) -> None:
    """Cache a one-sheet workbook holding ``rows``, so a named AISC shape resolves.

    The suite keeps every test out of the user's own cache, and the workbook is not
    redistributable, so a test that needs a named AISC shape writes the few rows it needs.
    """
    import hashlib
    import io
    from zipfile import ZIP_DEFLATED, ZipFile

    from anvilate.fetch import DatasetRecipe
    from anvilate.standards import fetch_aisc_profile_table, profiles

    head = {"A": "Type", "C": "AISC_Manual_Label", "G": "d", "I": "Ht", "K": "OD", "L": "bf",
            "N": "B", "O": "b", "Q": "tw", "T": "tf", "V": "t", "X": "tdes",
            "Y": "kdes"}  # fmt: skip
    strings = sorted({v for row in (head, *rows) for v in row.values() if isinstance(v, str)})
    sheet = "".join(
        f'<row r="{n}">'
        + "".join(
            f'<c r="{c}{n}" t="s"><v>{strings.index(v)}</v></c>'
            if isinstance(v, str)
            else f'<c r="{c}{n}"><v>{v}</v></c>'
            for c, v in row.items()
        )
        + "</row>"
        for n, row in enumerate((head, *rows), start=1)
    )
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        shared = "".join(f"<si><t>{value}</t></si>" for value in strings)
        archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{namespace}">{shared}</sst>')
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            f'<worksheet xmlns="{namespace}"><sheetData>{sheet}</sheetData></worksheet>',
        )
    payload = output.getvalue()
    monkeypatch.setattr(
        profiles,
        "AISC_SHAPES_V16",
        DatasetRecipe(
            name="aisc-shapes-database-v16.0.xlsx",
            url="https://example.invalid/aisc-shapes-database-v16.0.xlsx",
            sha256=hashlib.sha256(payload).hexdigest(),
            license="LicenseRef-AISC-Terms",
            source="AISC Shapes Database v16.0, test fixture",
            redistributable=False,
        ),
    )
    monkeypatch.setenv("ANVILATE_DATA_HOME", str(tmp_path))
    fetch_aisc_profile_table(retrieved="2026-10-11", consent=True, opener=lambda _url: payload)


# Real channel and angle rows, as the workbook's US customary columns give them.
_CHANNEL_ROWS = (
    {"A": "W", "C": "W12X26", "G": 12.2, "L": 6.49, "Q": 0.23, "T": 0.38, "Y": 0.68},
    {"A": "C", "C": "C10X30", "G": 10.0, "L": 3.03, "Q": 0.673, "T": 0.436},
    {"A": "MC", "C": "MC18X51.9", "G": 18.0, "L": 4.1, "Q": 0.6, "T": 0.625},
    {"A": "L", "C": "L8X4X1", "G": 4.0, "O": 8.0, "V": 1.0},
    {"A": "L", "C": "L4X4X1/2", "G": 4.0, "O": 4.0, "V": 0.5},
)


def test_a_beam_may_be_a_rolled_channel_and_its_twist_is_named_rather_than_passed(
    tmp_path, monkeypatch
):
    """`C10X30` is screened in bending and drawn, and the card says the twist is not checked.

    A channel's shear centre is off its web, so a transverse load through the web twists it
    as well as bending it. The bending, deflection and shear entries beside the twist entry
    are pure bending, and the twist entry is NOT_EVALUATED saying so until the member
    declares how the twist is dealt with.
    """
    from anvilate.packs.structural import BeamMember, screen_beam_member
    from anvilate.scorecard import CheckStatus

    _fetch_a_test_aisc_table(tmp_path, monkeypatch, _CHANNEL_ROWS)
    document = yaml.safe_load((_EXAMPLES / "beam_member.spec.yaml").read_text("utf-8"))
    params = {**document["element_params"], "section": "C10X30"}
    member = BeamMember.model_validate(params)
    section = member.section
    assert section.area.to("in**2").magnitude == pytest.approx(8.81, rel=3e-3)
    assert section.shear_centre_offset.to("in").magnitude == pytest.approx(0.368, rel=3e-3)

    card = screen_beam_member(member, required_safety_factor=1.5)
    statuses = {entry.name.removeprefix("floor-beam "): entry.status for entry in card.entries}
    assert statuses["bending"] is CheckStatus.PASS
    assert statuses["twist"] is CheckStatus.NOT_EVALUATED
    twist = next(one for one in card.entries if one.name.endswith("twist"))
    assert "9.33 mm outside the back of its web" in twist.detail
    assert "do not carry the torsion" in twist.detail
    assert twist.reference == "AISC 360-16 Ch. H"
    # It names the declaration that answers it, so the needs report can rank it.
    assert [need.declaration for need in twist.needs] == ["element_params.twist_restraint"]
    # A section with no shear centre offset gets no such entry at all.
    plain = BeamMember.model_validate({**params, "section": "IPE 200"})
    assert all(
        not entry.name.endswith("twist")
        for entry in screen_beam_member(plain, required_safety_factor=1.5).entries
    )

    # Drawn as the three rectangles the screen took its properties from.
    built = build_spec(_spec("beam_member", section="C10X30"))
    box = built.shape.bounding_box().size
    assert (box.X, box.Z, box.Y) == pytest.approx((76.962, 254.0, 4000.0), abs=1e-3)
    area = section.area.to("mm**2").magnitude
    assert built.dimensions_mm["section_area"] == pytest.approx(area, rel=1e-12)
    assert built.volume_mm3 == pytest.approx(area * 4000, rel=1e-9)


def test_a_declared_twist_restraint_passes_the_entry_and_says_what_it_rests_on(
    tmp_path, monkeypatch
):
    """Two things make a channel's bending entries the whole story, and both are declared.

    Where the load acts and whether anything holds the section are facts about the
    installation that no section property carries, so the entry passes on the declaration
    and the detail says so rather than implying a calculation. Declaring it on a section
    with no shear centre off its axis is refused instead of accepted and ignored.
    """
    from anvilate.packs.structural import BeamMember, TwistRestraint, screen_beam_member
    from anvilate.scorecard import CheckStatus

    _fetch_a_test_aisc_table(tmp_path, monkeypatch, _CHANNEL_ROWS)
    params = yaml.safe_load((_EXAMPLES / "beam_member.spec.yaml").read_text("utf-8"))[
        "element_params"
    ]
    for declared, says in (
        (TwistRestraint.THROUGH_SHEAR_CENTRE, "no torsion is applied"),
        (TwistRestraint.RESTRAINED, "declared restrained against rotating"),
    ):
        member = BeamMember.model_validate(
            {**params, "section": "C10X30", "twist_restraint": declared.value}
        )
        card = screen_beam_member(member, required_safety_factor=1.5)
        twist = next(one for one in card.entries if one.name.endswith("twist"))
        assert twist.status is CheckStatus.PASS, declared
        assert says in twist.detail, declared
        # A pass on a word, and the card says which.
        assert "not on a calculation" in twist.detail
        assert twist.needs == ()
    # The restrained case does not pretend to have sized the restraint.
    held = BeamMember.model_validate(
        {**params, "section": "C10X30", "twist_restraint": "restrained"}
    )
    entry = next(
        one
        for one in screen_beam_member(held, required_safety_factor=1.5).entries
        if one.name.endswith("twist")
    )
    assert "not sized here" in entry.detail

    # A section whose shear centre is on the load axis has no twist for this to answer.
    for section in ("IPE 200", "TUBE 60x4", "FLAT 50x10"):
        with pytest.raises(ValueError, match="no twist to restrain"):
            BeamMember.model_validate(
                {**params, "section": section, "twist_restraint": "restrained"}
            )
    # And without the declaration the channel is still not evaluated.
    bare = BeamMember.model_validate({**params, "section": "C10X30"})
    plain = next(
        one
        for one in screen_beam_member(bare, required_safety_factor=1.5).entries
        if one.name.endswith("twist")
    )
    assert plain.status is CheckStatus.NOT_EVALUATED


def test_a_channel_column_is_refused_because_its_weak_axis_was_not_derived(tmp_path, monkeypatch):
    """The weak axis a channel buckles about is withheld, so it is refused, not screened.

    `least_radius_of_gyration` falls back to the bending axis when a section carries no
    transverse second moment. On a C10X30 that is 3.43 in where the weak axis is nearer
    0.92, so a channel column screened through the fallback would be told it carries about
    four times what it does. Both compression members refuse it at validation.
    """
    from anvilate.packs.structural import BeamColumnMember, ColumnMember

    _fetch_a_test_aisc_table(tmp_path, monkeypatch, _CHANNEL_ROWS)
    for element, model in (
        ("column_member", ColumnMember),
        ("beam_column_member", BeamColumnMember),
    ):
        document = yaml.safe_load((_EXAMPLES / f"{element}.spec.yaml").read_text("utf-8"))
        for designation in ("C10X30", "MC18X51.9"):
            with pytest.raises(ValueError, match="buckles about the weak axis") as refused:
                model.model_validate({**document["element_params"], "section": designation})
            assert "beam_member" in str(refused.value)
            assert "flange taper" in str(refused.value)
            with pytest.raises(ValueError, match="buckles about the weak axis"):
                build_spec(_spec(element, section=designation))
        # The same member with a section that carries its weak axis is screened as before.
        assert model.model_validate({**document["element_params"], "section": "IPE 200"})


def test_a_column_may_be_a_rolled_angle_and_it_buckles_about_its_principal_axis(
    tmp_path, monkeypatch
):
    """`L8X4X1` is a column, screened on the axis a strut actually bows about.

    A single angle's weakest axis is neither of its legs: it lies across them. The section
    states that axis, so the buckling screen takes it — 0.844 in for an L8X4X1, where the
    weaker leg alone would give 1.02 and over-state the capacity.
    """
    from anvilate.packs.structural import ColumnMember, screen_column_member
    from anvilate.scorecard import CheckStatus

    _fetch_a_test_aisc_table(tmp_path, monkeypatch, _CHANNEL_ROWS)
    document = yaml.safe_load((_EXAMPLES / "column_member.spec.yaml").read_text("utf-8"))
    member = ColumnMember.model_validate({**document["element_params"], "section": "L8X4X1"})
    section = member.section
    assert section.least_radius_of_gyration.to("in").magnitude == pytest.approx(0.844, rel=4e-3)
    assert section.radius_of_gyration_transverse.to("in").magnitude == pytest.approx(1.02, rel=1e-2)
    assert section.principal_axis_tangent == pytest.approx(0.247, rel=3e-3)
    card = screen_column_member(member, required_safety_factor=1.5)
    buckling = next(one for one in card.entries if "buckling" in one.name)
    # At 3 m on a 21 mm radius of gyration this angle is slender, so the elastic branch of
    # §E3 governs — which is the branch the principal axis put it in.
    assert buckling.status is CheckStatus.PASS
    assert buckling.name.endswith("buckling (AISC E3 elastic)")

    # An equal-leg angle's principal axis is the diagonal, so tan(α) is 1 and its two legs
    # carry the same second moment.
    equal = ColumnMember.model_validate({**document["element_params"], "section": "L4X4X1/2"})
    assert equal.section.principal_axis_tangent == pytest.approx(1.0)
    assert equal.section.second_moment.to("mm**4").magnitude == pytest.approx(
        equal.section.second_moment_transverse.to("mm**4").magnitude, rel=1e-12
    )
    # And its minor principal axis is well below either leg's: the diagonal is the weak way.
    assert (
        equal.section.minor_principal_second_moment.to("mm**4").magnitude
        < 0.5 * equal.section.second_moment.to("mm**4").magnitude
    )

    # Drawn as the two legs the screen took its properties from.
    built = build_spec(_spec("column_member", section="L8X4X1"))
    box = built.shape.bounding_box().size
    assert (box.X, box.Y, box.Z) == pytest.approx((101.6, 203.2, 3000.0), abs=1e-3)
    area = section.area.to("mm**2").magnitude
    assert built.dimensions_mm["section_area"] == pytest.approx(area, rel=1e-12)
    assert built.volume_mm3 == pytest.approx(area * 3000, rel=1e-9)


def test_an_angle_beam_is_refused_because_a_leg_is_not_a_principal_axis(tmp_path, monkeypatch):
    """Bending an angle in the plane of a leg is not uniaxial bending, so it is refused.

    The screens compute M/S about the declared axis. A single angle curves about both of
    its principal axes at once and deflects out of the load plane, so that M/S reads under
    the real stress — the unconservative direction — and AISC 360-16 §F10, which covers it,
    is not implemented. Both flexural members refuse it; the column does not.
    """
    from anvilate.packs.structural import BeamColumnMember, BeamMember, ColumnMember

    _fetch_a_test_aisc_table(tmp_path, monkeypatch, _CHANNEL_ROWS)
    for element, model in (
        ("beam_member", BeamMember),
        ("beam_column_member", BeamColumnMember),
    ):
        document = yaml.safe_load((_EXAMPLES / f"{element}.spec.yaml").read_text("utf-8"))
        for designation in ("L8X4X1", "L4X4X1/2"):
            with pytest.raises(ValueError, match="principal axes are tilted off its legs") as bad:
                model.model_validate({**document["element_params"], "section": designation})
            assert "AISC 360-16 Chapter F" in str(bad.value)
            assert "column_member" in str(bad.value)
            with pytest.raises(ValueError, match="principal axes are tilted off its legs"):
                build_spec(_spec(element, section=designation))
        # An I-section bends about its own axes and is screened as before.
        assert model.model_validate({**document["element_params"], "section": "IPE 200"})
    upright = yaml.safe_load((_EXAMPLES / "column_member.spec.yaml").read_text("utf-8"))
    assert ColumnMember.model_validate({**upright["element_params"], "section": "L8X4X1"})


def test_a_section_declared_by_its_properties_is_drawn_when_it_records_its_wall():
    """Three properties do not say a shape. A tube's or a box's own dimensions do."""
    from anvilate.analysis.section import CrossSection
    from anvilate.units import Quantity

    inch = CrossSection.hollow_circular(
        outer_diameter=Quantity.parse("2 in"), inner_diameter=Quantity.parse("1.5 in")
    )
    tube = build_spec(_spec("column_member", section=inch.model_dump(mode="json")))
    box = tube.shape.bounding_box().size
    assert (box.X, box.Y, box.Z) == pytest.approx((50.8, 50.8, 3000.0), abs=1e-6)
    area = math.pi * (50.8**2 - 38.1**2) / 4
    assert tube.volume_mm3 == pytest.approx(area * 3000, rel=1e-6)
    assert tube.dimensions_mm["wall_thickness"] == pytest.approx(6.35)
    named = build_spec(_spec("beam_member", section="BOX 100x50x4"))
    declared = CrossSection.hollow_rectangular(
        width=Quantity.parse("100 mm"),
        height=Quantity.parse("50 mm"),
        wall_thickness=Quantity.parse("4 mm"),
    )
    drawn = build_spec(_spec("beam_member", section=declared.model_dump(mode="json")))
    assert drawn.volume_mm3 == pytest.approx(named.volume_mm3, rel=1e-9)
    assert drawn.dimensions_mm == named.dimensions_mm
    bare = {key: declared.model_dump(mode="json")[key] for key in ("area", "second_moment")}
    bare["extreme_fibre"] = declared.model_dump(mode="json")["extreme_fibre"]
    with pytest.raises(GeometryError, match="which do not say its shape"):
        build_spec(_spec("beam_member", section=bare))


def test_a_rolled_hss_member_is_screened_and_drawn_with_its_corners(tmp_path, monkeypatch):
    """`HSS6X4X1/4` from a fetched workbook: the solid has the area the screen divides by,
    its flats are the outside less three walls, and the trail says where it came from."""
    import hashlib
    import io
    from zipfile import ZIP_DEFLATED, ZipFile

    from anvilate.evidence import provenance_for
    from anvilate.fetch import DatasetRecipe
    from anvilate.packs.structural import BeamMember, _box_flats
    from anvilate.standards import fetch_aisc_profile_table, profiles

    head = {"A": "Type", "C": "AISC_Manual_Label", "G": "d", "I": "Ht", "K": "OD", "L": "bf",
            "N": "B", "O": "b", "Q": "tw", "T": "tf", "V": "t", "X": "tdes",
            "Y": "kdes"}  # fmt: skip
    rows = (
        {"A": "W", "C": "W12X26", "G": 12.2, "L": 6.49, "Q": 0.23, "T": 0.38, "Y": 0.68},
        {"A": "HSS", "C": "HSS6X4X1/4", "I": 6, "K": "–", "N": 4, "X": 0.233},
    )
    strings = sorted({v for row in (head, *rows) for v in row.values() if isinstance(v, str)})
    sheet = "".join(
        f'<row r="{n}">'
        + "".join(
            f'<c r="{c}{n}" t="s"><v>{strings.index(v)}</v></c>'
            if isinstance(v, str)
            else f'<c r="{c}{n}"><v>{v}</v></c>'
            for c, v in row.items()
        )
        + "</row>"
        for n, row in enumerate((head, *rows), start=1)
    )
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        shared = "".join(f"<si><t>{value}</t></si>" for value in strings)
        archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{namespace}">{shared}</sst>')
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            f'<worksheet xmlns="{namespace}"><sheetData>{sheet}</sheetData></worksheet>',
        )
    payload = output.getvalue()
    recipe = DatasetRecipe(
        name="aisc-shapes-database-v16.0.xlsx",
        url="https://example.invalid/aisc-shapes-database-v16.0.xlsx",
        sha256=hashlib.sha256(payload).hexdigest(),
        license="LicenseRef-AISC-Terms",
        source="AISC Shapes Database v16.0, test fixture",
        redistributable=False,
    )
    monkeypatch.setattr(profiles, "AISC_SHAPES_V16", recipe)
    monkeypatch.setenv("ANVILATE_DATA_HOME", str(tmp_path))
    fetch_aisc_profile_table(retrieved="2026-10-11", consent=True, opener=lambda _url: payload)

    spec = _spec("beam_member", section="hss6x4x1/4")
    built = build_spec(spec)
    box = built.shape.bounding_box().size
    assert (box.X, box.Z, box.Y) == pytest.approx((101.6, 152.4, 4000.0), abs=1e-6)
    section = BeamMember.model_validate(spec.element_params).section
    area = section.area.to("mm**2").magnitude
    assert area == pytest.approx(4.30 * 25.4**2, rel=2e-3)
    assert built.volume_mm3 == pytest.approx(area * 4000, rel=1e-6)
    assert built.dimensions_mm["corner_radius"] == pytest.approx(2 * 0.233 * 25.4)
    assert built.dimensions_mm["section_area"] == pytest.approx(area, rel=1e-12)
    wall = 0.233 * 25.4
    assert _box_flats(section) == pytest.approx((101.6 - 3 * wall, 152.4 - 3 * wall))
    (source,) = [record for record in provenance_for(spec) if record.kind == "section"]
    assert source.ref == "hss6x4x1/4" and source.name == "HSS6X4X1/4"
    assert source.sources == ("AISC Shapes Database v16.0, test fixture",)
