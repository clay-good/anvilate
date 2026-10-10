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
    "helical_compression_spring",
    "lifting_lug",
    "rolling_bearing",
    "shaft_key",
    "spur_gear_mesh",
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
    # A 3 mm wire on a 24 mm mean coil occupies the tube from 21 to 27 mm, 200 long.
    "helical_compression_spring": (_disc(27) - _disc(21)) * 200,
    # 80 wide and 12 thick, the hole 90 up, a half disc above it, less the 25 mm pin hole.
    "lifting_lug": (80 * 90 + _disc(80) / 2 - _disc(25)) * 12,
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


@pytest.mark.parametrize("element_type", _DRAWN)
def test_the_step_file_is_one_part_and_reads_back(element_type, tmp_path):
    from anvilate.export.gate import authorize_export
    from anvilate.geometry import read_step_validation_properties, write_step

    built = build_spec(_spec(element_type))
    path = write_step(
        built, tmp_path / "part.step", authorization=authorize_export(None, override=True)
    )
    assert path.read_text(encoding="utf-8").count("PRODUCT(") == 1
    assert read_step_validation_properties(path).volume_mm3 == pytest.approx(
        built.volume_mm3, rel=1e-9
    )


def test_being_drawn_changes_nothing_on_the_card():
    """`hole_height` and `designation` are for the drawing. No check reads either."""
    for element_type, field in (("lifting_lug", "hole_height"), ("rolling_bearing", "designation")):
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
