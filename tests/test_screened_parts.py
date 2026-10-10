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
