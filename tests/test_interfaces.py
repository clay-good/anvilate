"""Interface contracts on products: the spec's scenarios, worked on placeholders.

A 120 × 80 × 10 bracket offers a four-hole 50 mm square bolt pattern on its top face; a
57 × 57 × 76 motor offers the same pattern on its bottom face. Connecting them by name
seats the motor on the bracket with its holes on the bracket's: z 5 to 81.
"""

from __future__ import annotations

import pytest

pytest.importorskip("build123d")

from anvilate.interfaces import Interface  # noqa: E402
from anvilate.product import ProductError, parse_product, place_product  # noqa: E402
from anvilate.scorecard import CheckStatus  # noqa: E402


def _mm(v: float) -> dict:
    return {"magnitude": v, "unit": "mm"}


def _square(prefix: str, half: float, z: float, face: str) -> list[dict]:
    return [{"tag": f"{prefix}{i}", "x": _mm(x), "y": _mm(y), "z": _mm(z), "face": face,
             "diameter": _mm(5.5)}
            for i, (x, y) in enumerate([(-half, -half), (half, -half), (half, half),
                                        (-half, half)], start=1)]  # fmt: skip


def _holder(size, kg, holes=(), interfaces=()):
    return {"envelope": [_mm(v) for v in size], "mass": {"magnitude": kg, "unit": "kg"},
            "reason": "not yet detailed", "holes": list(holes),
            "interfaces": list(interfaces)}  # fmt: skip


def _pattern(name: str, prefix: str, face: str) -> dict:
    return {"name": name, "kind": "bolt_pattern", "face": face,
            "holes": [f"{prefix}{i}" for i in range(1, 5)]}  # fmt: skip


def _document(motor_half: float = 25.0, extra: dict | None = None) -> dict:
    definitions = [
        {"id": "bracket", "identity": {"description": "bracket", "source": "make"},
         "placeholder": _holder((120, 80, 10), 0.5, _square("b", 25, 5, "top"),
                                [_pattern("motor_mount", "b", "top")])},
        {"id": "motor", "identity": {"description": "motor", "source": "buy"},
         "placeholder": _holder((57, 57, 76), 1.0, _square("m", motor_half, -38, "bottom"),
                                [_pattern("flange", "m", "bottom")])},
    ]  # fmt: skip
    document = {
        "name": "drive",
        "definitions": definitions,
        "instances": [{"name": "bracket", "item": "bracket"}, {"name": "motor", "item": "motor"}],
        "ground": "bracket",
        "connections": [{"on": "bracket.motor_mount", "place": "motor.flange"}],
    }
    document.update(extra or {})
    return document


def _entries(placed) -> dict:
    return {e.name: e for e in placed.card.entries}


def test_a_motor_goes_onto_its_bracket_by_interface_names():
    document = _document()
    assert "mates" not in document  # no feature tag of either item is named by the product
    placed = place_product(parse_product(document))
    motor = next(b for b in placed.bodies if b.path == "drive/motor")
    assert motor.box_min_mm == pytest.approx((-28.5, -28.5, 5))
    assert motor.box_max_mm == pytest.approx((28.5, 28.5, 81))
    pattern = _entries(placed)["bracket.motor_mount ~ motor.flange hole pattern"]
    assert pattern.status is CheckStatus.PASS


def test_a_flange_drawn_to_an_old_datasheet_fails_its_pattern():
    placed = place_product(parse_product(_document(motor_half=47.14 / 2)))
    pattern = _entries(placed)["bracket.motor_mount ~ motor.flange hole pattern"]
    assert pattern.status is CheckStatus.FAIL and "do not line up" in pattern.detail


def test_a_shaft_offered_to_a_bolt_pattern_is_refused_before_geometry():
    document = _document()
    shaft = {"name": "shaft", "kind": "shaft", "axis": "z", "parameters": {"diameter": _mm(8)}}
    document["definitions"][1]["placeholder"]["interfaces"].append(shaft)
    document["connections"] = [{"on": "bracket.motor_mount", "place": "motor.shaft"}]
    with pytest.raises(ProductError, match="bracket.motor_mount is a bolt_pattern and "
                       "motor.shaft a shaft, which do not meet; a bolt_pattern meets "
                       "bolt_pattern or tapped_pattern"):  # fmt: skip
        parse_product(document)


def test_a_shaft_without_a_diameter_is_refused_naming_it_and_its_unit():
    # a refusal inside the model's validator reaches the caller as a ValidationError
    with pytest.raises(ValueError, match="states no diameter; a shaft needs diameter as a "
                       r"\[length\], such as mm"):  # fmt: skip
        Interface(name="out", kind="shaft", axis="z")


def test_an_unknown_kind_is_refused_with_the_nearest():
    with pytest.raises(ValueError, match="nearest: bolt_pattern"):
        Interface(name="x", kind="bolt_patern", face="top", holes=("a",))


def test_a_mounting_face_nobody_used_is_reported_and_an_open_reason_clears_it():
    document = _document()
    fan_mount = {"name": "mount", "kind": "mounting_face", "face": "bottom"}
    document["definitions"][1]["placeholder"]["interfaces"].append(fan_mount)
    loose = _entries(place_product(parse_product(document)))["unconnected interfaces"]
    assert loose.status is CheckStatus.NOT_EVALUATED and "motor.mount" in loose.detail
    document["open_interfaces"] = [{"at": "motor.mount", "reason": "held by the grille"}]
    assert "unconnected interfaces" not in _entries(place_product(parse_product(document)))


def test_a_pattern_with_two_partners_is_reported_naming_all_three():
    document = _document()
    second = {"id": "plate", "identity": {"description": "plate", "source": "make"},
              "placeholder": _holder((57, 57, 5), 0.1, _square("q", 25, -2.5, "bottom"),
                                     [_pattern("under", "q", "bottom")])}  # fmt: skip
    document["definitions"].append(second)
    document["instances"].append({"name": "plate", "item": "plate"})
    document["connections"].append({"on": "bracket.motor_mount", "place": "plate.under"})
    entries = _entries(place_product(parse_product(document)))
    over = entries["bracket.motor_mount partners"]
    assert over.status is CheckStatus.FAIL
    assert "motor.flange" in over.detail and "plate.under" in over.detail


@pytest.mark.parametrize(("shaft", "status"), [(8.0, CheckStatus.PASS), (8.2, CheckStatus.FAIL)])
def test_a_shaft_larger_than_its_bore_fails(shaft, status):
    document = _document()
    document["definitions"][0]["placeholder"]["interfaces"].append(
        {"name": "bore", "kind": "bore", "axis": "z", "parameters": {"diameter": _mm(8.1)}}
    )
    document["definitions"][1]["placeholder"]["interfaces"].append(
        {"name": "shaft", "kind": "shaft", "axis": "z", "parameters": {"diameter": _mm(shaft)}}
    )
    document["open_interfaces"] = [{"at": "bracket.bore", "reason": "checked below"},
                                   {"at": "motor.shaft", "reason": "checked below"}]  # fmt: skip
    product = parse_product(document)
    assert product  # the shaft and bore are offered; a fit is only checked when they meet
    document["open_interfaces"] = []
    document["connections"].append({"on": "bracket.bore", "place": "motor.shaft"})
    entries = _entries(place_product(parse_product(document)))
    assert entries["bracket.bore ~ motor.shaft diameter"].status is status


def test_an_interface_naming_a_hole_its_item_lacks_is_refused():
    document = _document()
    document["definitions"][0]["placeholder"]["interfaces"][0]["holes"][0] = "b9"
    with pytest.raises(ProductError, match=r"names holes \['b9'\], which it does not have"):
        parse_product(document)


def test_the_docs_tables_are_the_vocabulary_and_the_compatibility_table():
    import re
    from pathlib import Path

    from anvilate.interfaces import COMPATIBLE, KINDS

    page = (Path(__file__).resolve().parents[1] / "docs" / "interfaces.md").read_text()
    kinds = {}
    for kind, located, requires, partners in re.findall(
        r"^\| `(\w+)` \| (face|axis)[^|]* \| ([^|]+) \| (one|any number) \|", page, re.M
    ):
        kinds[kind] = (located, tuple(re.findall(r"`(\w+)`", requires)),
                       1 if partners == "one" else None)  # fmt: skip
    assert kinds == {k: (loc, tuple(w), n) for k, (loc, w, n) in KINDS.items()}
    pairs = {}
    for a, b, agree in re.findall(r"^\| `(\w+)` with `(\w+)` \| ([^|]+) \|", page, re.M):
        pairs[(a, b)] = tuple(re.findall(r"`(\w+)`", agree))
    assert pairs == {pair: agree for pair, (agree, _checks) in COMPATIBLE.items()}


def test_every_build_writes_an_interface_control_table():
    document = _document()
    fan_mount = {"name": "mount", "kind": "mounting_face", "face": "bottom"}
    document["definitions"][1]["placeholder"]["interfaces"].append(fan_mount)
    document["open_interfaces"] = [{"at": "motor.mount", "reason": "=held by the grille"}]
    table = place_product(parse_product(document)).interfaces
    connection, opened = table.rows
    assert (connection.node, connection.on, connection.place) == (
        "drive",
        "bracket.motor_mount",
        "motor.flange",
    )
    assert connection.on_values == "4 holes on top" and connection.on_owner == "make, bracket"
    assert connection.place_owner == "buy, motor" and connection.checks == ("hole pattern: pass",)
    assert opened.place is None and opened.reason == "=held by the grille"
    csv_text = table.to_csv()
    assert csv_text.splitlines()[0].startswith("product,on,on kind,on values,on owner,place")
    assert "'=held by the grille" in csv_text  # a cell a spreadsheet would run is quoted
    section = table.section()
    assert "| drive | bracket.motor_mount | bolt_pattern | 4 holes on top |" in section
    assert "- drive motor.mount (mounting_face): =held by the grille" in section


def _plate_with_motor(pitch_x: float = 100.0, binding=("m6_1_1", "m6_2_1", "m6_2_2", "m6_1_2")):
    """The catalog mounting plate (its m6 pattern 100 × 60 on its top face, z = 6) and a
    motor placeholder whose four bottom holes are on the same 100 × 60 rectangle."""
    import copy
    from pathlib import Path

    from anvilate._models import parse_yaml

    plate = parse_yaml((Path(__file__).resolve().parents[1] / "examples" / "parts"
                        / "mounting_plate.spec.yaml").read_text())  # fmt: skip
    plate = copy.deepcopy(plate)
    plate["element_params"]["hole_patterns"][0]["pitch_x"] = _mm(pitch_x)
    corners = [(-50, -30), (50, -30), (50, 30), (-50, 30)]
    motor_holes = [{"tag": f"m{i}", "x": _mm(x), "y": _mm(y), "z": _mm(-20), "face": "bottom",
                    "diameter": _mm(5.5)} for i, (x, y) in enumerate(corners, start=1)]  # fmt: skip
    return {
        "name": "drive",
        "definitions": [
            {"id": "plate", "identity": {"description": "plate", "source": "make"}, "spec": plate,
             "interfaces": [{"name": "motor_mount", "kind": "bolt_pattern",
                             "features": list(binding)},
                            {"name": "pilot", "kind": "bore", "features": ["cb"]}]},
            {"id": "motor", "identity": {"description": "motor", "source": "buy"},
             "placeholder": _holder((110, 70, 40), 1.0, motor_holes,
                                    [_pattern("flange", "m", "bottom")])},
        ],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "motor", "item": "motor"}],
        "ground": "plate",
        "connections": [{"on": "plate.motor_mount", "place": "motor.flange"}],
        "open_interfaces": [{"at": "plate.pilot", "reason": "no pilot on this motor"}],
    }  # fmt: skip


def test_a_parts_interface_is_read_from_the_built_part():
    placed = place_product(parse_product(_plate_with_motor()))
    motor = next(b for b in placed.bodies if b.path == "drive/motor")
    assert motor.box_min_mm[2] == pytest.approx(6)  # on the plate's top, where its holes open
    assert _entries(placed)["plate.motor_mount ~ motor.flange hole pattern"].status is (
        CheckStatus.PASS
    )
    (row,) = [r for r in placed.interfaces.rows if r.place is not None]
    assert row.on_values == "4 holes on top"
    (pilot,) = [r for r in placed.interfaces.rows if r.place is None]
    assert pilot.on_kind == "bore" and pilot.on_values == "diameter 6.6 mm"


def test_a_change_to_the_holes_changes_the_interface():
    placed = place_product(parse_product(_plate_with_motor(pitch_x=110.0)))
    pattern = _entries(placed)["plate.motor_mount ~ motor.flange hole pattern"]
    assert pattern.status is CheckStatus.FAIL and "do not line up" in pattern.detail


def test_an_interface_bound_to_nothing_is_refused_naming_it_and_the_tag():
    document = _plate_with_motor(binding=("m6_1_1", "m6_9_9"))
    document["definitions"][1]["placeholder"]["interfaces"][0]["holes"] = ["m1", "m2"]
    with pytest.raises(ProductError, match=r"interface 'motor_mount' is bound to \['m6_9_9'\], "
                       "which the built part does not have"):  # fmt: skip
        place_product(parse_product(document))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda d: d["definitions"][0]["interfaces"].append(
                {"name": "track", "kind": "rail", "features": ["adj"]}
            ),
            "offer it on a placeholder or component",
        ),
        (
            lambda d: d["definitions"][1].update(
                interfaces=[{"name": "x", "kind": "mounting_face", "face": "top"}]
            ),
            "is not a catalog part",
        ),
        (
            lambda d: d.update(connections=[{"on": "motor.flange", "place": "plate.motor_mount"}]),
            "places the ground 'plate'",
        ),
    ],
)
def test_a_part_interface_the_document_cannot_hold_is_refused(change, message):
    document = _plate_with_motor()
    change(document)
    with pytest.raises((ProductError, ValueError), match=message):
        parse_product(document)
