"""Products placed through mates: positions, patterns, sub-products, interference, mass.

Placeholders are boxes centred on their own origin, so every placed position here is a
hand calculation: a 200 × 100 × 10 base spans z −5 to 5, and a 40 mm block seated on it
with its left and front faces flush spans x −100 to −60, y −50 to −10, z 5 to 45.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")

from anvilate.product import ProductError, parse_product, place_product  # noqa: E402
from anvilate.scorecard import CheckStatus  # noqa: E402


def _box(x: float, y: float, z: float, kg: float) -> dict:
    return {"envelope": [{"magnitude": v, "unit": "mm"} for v in (x, y, z)],
            "mass": {"magnitude": kg, "unit": "kg"}, "reason": "not yet detailed"}  # fmt: skip


def _definition(id_: str, **kind) -> dict:
    return {"id": id_, "identity": {"description": id_, "source": "make"}, **kind}


def _seat(part: str, on: str, prefix: str = "") -> list[dict]:
    return [
        {"id": f"{prefix}sit", "kind": "face_to_face", "place": {"part": part, "face": "bottom"},
         "on": {"part": on, "face": "top"}},
        {"id": f"{prefix}left", "kind": "edge_flush", "place": {"part": part, "face": "left"},
         "on": {"part": on, "face": "left"}},
        {"id": f"{prefix}front", "kind": "edge_flush", "place": {"part": part, "face": "front"},
         "on": {"part": on, "face": "front"}},
    ]  # fmt: skip


def _cart(spacing: float = 50.0) -> dict:
    return {
        "name": "cart",
        "definitions": [_definition("base", placeholder=_box(200, 100, 10, 2.0)),
                        _definition("block", placeholder=_box(40, 40, 40, 0.5))],
        "instances": [
            {"name": "base", "item": "base"},
            {"name": "block", "item": "block",
             "pattern": {"kind": "linear", "count": 3,
                         "spacing": {"magnitude": spacing, "unit": "mm"}, "direction": "x"}},
        ],
        "ground": "base",
        "mates": _seat("block", "base"),
    }  # fmt: skip


def _box_of(placed, path):
    body = next(b for b in placed.bodies if b.path == path)
    return body.box_min_mm, body.box_max_mm


def test_a_seated_block_and_its_pattern_land_where_the_mates_put_them():
    placed = place_product(parse_product(_cart()))
    low, high = _box_of(placed, "cart/block[1]")
    # front is −y, so the flush front face puts the block at y −50 to −10
    assert low == pytest.approx((-100, -50, 5)) and high == pytest.approx((-60, -10, 45))
    low3, _ = _box_of(placed, "cart/block[3]")
    assert low3[0] == pytest.approx(-100 + 2 * 50)  # the pattern follows its first member
    assert placed.interference.status is CheckStatus.PASS


def test_a_pattern_spaced_tighter_than_its_member_overlaps():
    placed = place_product(parse_product(_cart(spacing=30.0)))
    assert placed.interference.status is CheckStatus.FAIL
    assert "cart/block[1] and cart/block[2]" in placed.interference.detail


def test_mass_rolls_up_and_names_the_placeholders_it_rests_on():
    placed = place_product(parse_product(_cart()))
    assert placed.mass_kg == pytest.approx(2.0 + 3 * 0.5)
    assert len(placed.mass_rests_on) == 4 and "rests on placeholders" in str(placed)


def test_a_sub_product_moves_as_one_body():
    drive = parse_product({
        "name": "drive",
        "definitions": [_definition("plate", placeholder=_box(80, 60, 8, 0.6)),
                        _definition("motor", placeholder=_box(40, 40, 50, 0.9))],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "motor", "item": "motor"}],
        "ground": "plate",
        "mates": _seat("motor", "plate"),
    })  # fmt: skip
    stage = parse_product({
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(200, 100, 10, 2.0)),
                        _definition("drive", product="drive")],
        "instances": [{"name": "base", "item": "base"}, {"name": "drive", "item": "drive"}],
        "ground": "base",
        "mates": _seat("drive", "base"),
    })  # fmt: skip
    placed = place_product(stage, library={"drive": drive})
    low, _ = _box_of(placed, "stage/drive/plate")
    assert low[2] == pytest.approx(5)  # the drive's plate sits on the base's top
    motor_low, _ = _box_of(placed, "stage/drive/motor")
    assert motor_low[2] == pytest.approx(5 + 8)  # and its motor still sits on its plate
    assert placed.mass_kg == pytest.approx(2.0 + 0.6 + 0.9)


def test_a_catalog_part_brings_its_own_mass():
    plate_spec = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "examples" / "parts" / "mounting_plate.spec.yaml")
        .read_text()
    )  # fmt: skip
    document = _cart()
    document["definitions"][1] = _definition("block", spec=plate_spec)
    document["instances"][1].pop("pattern")
    placed = place_product(parse_product(document))
    plate = next(b for b in placed.bodies if b.path == "cart/block")
    # 120 × 80 × 6 steel with rounded corners and holes: well under 120 × 80 × 6 × 7.85e-6
    assert plate.placeholder is False and 0.3 < plate.mass_kg < 0.4521
    assert placed.mass_rests_on == ("cart/base",)
    # its node carries the part's own card, the one `anvilate check` gives its spec
    from anvilate.screening import screen_spec
    from anvilate.spec import parse_spec

    node = placed.card.find("cart/block")
    assert node.kind == "part" and node.entries == screen_spec(parse_spec(plate_spec)).entries


def test_every_instance_but_the_ground_needs_a_mate():
    document = _cart()
    document["mates"] = []
    with pytest.raises(ProductError, match="never states a coordinate"):
        place_product(parse_product(document))


def test_the_ground_is_not_placed_by_a_mate():
    document = _cart()
    document["mates"] = _seat("base", "block")
    with pytest.raises(ProductError, match="places the ground"):
        place_product(parse_product(document))


def _mm3(x: float, y: float, z: float) -> list[dict]:
    return [{"magnitude": v, "unit": "mm"} for v in (x, y, z)]


def _hole(tag: str, x: float, y: float, z: float, face: str) -> dict:
    x_, y_, z_ = _mm3(x, y, z)
    return {"tag": tag, "x": x_, "y": y_, "z": z_, "face": face,
            "diameter": {"magnitude": 5, "unit": "mm"}}  # fmt: skip


def _motor_on_plate(center_of_mass: list[dict] | None = None) -> dict:
    """A 40 × 40 × 50 motor bolted by its base holes onto two holes in an 80 × 60 × 8 plate.

    The motor's holes sit at x −10 and 20 on its bottom face (z −25), the plate's at x 0 and
    30, y 10 on its top (z 4), so the mate shifts the motor by (10, 10, 29): its box spans
    x 0 to 30 → −10 to 30, y −10 to 30, z 4 to 54.
    """
    motor = _box(40, 40, 50, 0.9)
    motor["holes"] = [_hole("m1", -10, 0, -25, "bottom"), _hole("m2", 20, 0, -25, "bottom")]
    if center_of_mass is not None:
        motor["center_of_mass"] = center_of_mass
    plate = _box(80, 60, 8, 0.6)
    plate["holes"] = [_hole("p1", 0, 10, 4, "top"), _hole("p2", 30, 10, 4, "top")]
    return {
        "name": "drive",
        "definitions": [_definition("plate", placeholder=plate),
                        _definition("motor", placeholder=motor)],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "motor", "item": "motor"}],
        "ground": "plate",
        "mates": [{"id": "bolted", "kind": "hole_pattern",
                   "place": {"part": "motor", "face": "bottom", "holes": ["m1", "m2"]},
                   "on": {"part": "plate", "face": "top", "holes": ["p1", "p2"]}}],
    }  # fmt: skip


def test_a_placeholder_bolt_pattern_takes_a_hole_pattern_mate():
    placed = place_product(parse_product(_motor_on_plate()))
    low, high = _box_of(placed, "drive/motor")
    assert low == pytest.approx((-10, -10, 4)) and high == pytest.approx((30, 30, 54))


def test_the_centre_of_mass_is_the_mass_weighted_centre_of_the_leaves():
    placed = place_product(parse_product(_motor_on_plate()))
    # plate 0.6 kg at the origin, motor 0.9 kg at (10, 10, 29): (9, 9, 26.1) / 1.5
    assert placed.center_of_mass_mm == pytest.approx((6.0, 6.0, 17.4))
    assert placed.center_assumed == ("drive/plate", "drive/motor")
    assert "centre of mass (6, 6, 17.4) mm, assuming envelope centres" in str(placed)


def test_a_declared_centre_of_mass_moves_with_its_placeholder():
    placed = place_product(parse_product(_motor_on_plate(_mm3(0, 0, -5))))
    motor = next(b for b in placed.bodies if b.path == "drive/motor")
    assert motor.center_of_mass_mm == pytest.approx((10.0, 10.0, 24.0))
    assert placed.center_of_mass_mm == pytest.approx((6.0, 6.0, 0.9 * 24 / 1.5))
    assert placed.center_assumed == ("drive/plate",)


def test_interference_resting_on_placeholders_says_it_is_provisional():
    placed = place_product(parse_product(_motor_on_plate()))
    assert placed.interference.status is CheckStatus.PASS
    assert "provisional: 2 placeholders (drive/plate, drive/motor)" in placed.interference.detail


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda p: p.update(center_of_mass=_mm3(0, 0, 30)), "centre of mass"),
        (lambda p: p["holes"].__setitem__(0, _hole("m1", 0, 0, -40, "bottom")), "hole 'm1'"),
    ],
)
def test_a_placeholder_refuses_what_lies_outside_its_envelope(change, message):
    document = _motor_on_plate()
    change(document["definitions"][1]["placeholder"])
    with pytest.raises(Exception, match=message):
        parse_product(document)


def test_the_placed_product_names_a_layout_parameter_no_item_reads():
    document = _motor_on_plate()
    document["layout"] = {"parameters": [
        {"name": "bolt", "value": {"magnitude": 5, "unit": "mm"}, "source": "M5 clearance"},
        {"name": "stroke", "value": {"magnitude": 300, "unit": "mm"}, "source": "requirement"},
    ]}  # fmt: skip
    for holder in (document["definitions"][0], document["definitions"][1]):
        for hole in holder["placeholder"]["holes"]:
            hole["diameter"] = {"layout": "bolt"}
    placed = place_product(parse_product(document))
    assert placed.unused_parameters == ("stroke",)
    assert "layout parameters no item reads: ['stroke']" in str(placed)
    # the layout is in no mass roll-up and no body
    assert placed.mass_kg == pytest.approx(1.5) and len(placed.bodies) == 2
