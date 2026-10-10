"""Part combinations: parts placed by the features they share, and checked where they meet.

add-part-combinations. Every test starts from one of the five worked combinations in
``examples/combinations`` and changes it, so the examples are the fixtures. The positions
asserted below are arithmetic from the parts' own dimensions: a 5 mm bracket on a 6 mm
plate has its foot at z = 6.
"""

from __future__ import annotations

import copy
import math
import re
from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")

from anvilate.combination import (  # noqa: E402
    CombinationError,
    build_combination,
    parse_combination,
    render_combination,
    write_step_assembly,
)
from anvilate.scorecard import CheckStatus  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "combinations"
_WORKED = (
    "bracket_on_plate",
    "collar_on_shaft",
    "flange_pair",
    "lug_on_base_plate",
    "portal_frame",
)


def _document(name: str) -> dict:
    return yaml.safe_load((_EXAMPLES / f"{name}.combination.yaml").read_text(encoding="utf-8"))


def _built(name: str, change=None):
    document = copy.deepcopy(_document(name))
    if change is not None:
        change(document)
    return build_combination(parse_combination(document))


def _mm(value: float) -> dict:
    return {"magnitude": value, "unit": "mm"}


def _box(part) -> tuple[tuple[float, ...], tuple[float, ...]]:
    box = part.shape.bounding_box()
    return (
        tuple(round(v, 6) for v in (box.min.X, box.min.Y, box.min.Z)),
        tuple(round(v, 6) for v in (box.max.X, box.max.Y, box.max.Z)),
    )


def _entry(built, name: str):
    return next(entry for entry in built.card.entries if entry.name == name)


def _disc(diameter: float) -> float:
    return math.pi * diameter**2 / 4


def test_the_worked_combinations_are_the_ones_shipped():
    shipped = {path.name.removesuffix(".combination.yaml") for path in _EXAMPLES.glob("*.yaml")}
    assert shipped == set(_WORKED) and len(_WORKED) == 5


@pytest.mark.parametrize("name", _WORKED)
def test_a_worked_combination_builds_with_no_coordinate_in_its_document(name):
    document = _document(name)
    built = _built(name)
    assert [part.id for part in built.parts] == [part["id"] for part in document["parts"]]
    assert _entry(built, "interference").status is CheckStatus.PASS
    # A mate names features. Nothing in one is a position.
    for mate in document["mates"]:
        assert set(mate) <= {"id", "kind", "place", "on", "offset", "rotation_deg", "fit"}
        for side in ("place", "on"):
            assert set(mate[side]) <= {"part", "face", "holes", "axis", "feature"}
    again = _built(name)
    assert [(p.rotation, p.translation) for p in again.parts] == [
        (p.rotation, p.translation) for p in built.parts
    ]


def test_a_bracket_lands_on_its_holes():
    """The bracket's two base holes are 42.5 mm from its heel; the plate's are at x = 20."""
    built = _built("bracket_on_plate")
    plate, bracket = built.parts
    assert _box(plate) == ((-60.0, -40.0, 0.0), (60.0, 40.0, 6.0))
    assert _box(bracket) == ((-22.5, -25.0, 6.0), (37.5, 25.0, 86.0))
    for tag, on in (("b1", "a1"), ("b2", "a2")):
        mine = next(f for f in bracket.built.features if f.tag == tag)
        theirs = next(f for f in plate.built.features if f.tag == on)
        here, there = bracket.point(tuple(mine.position_mm)), plate.point(tuple(theirs.position_mm))
        assert here[:2] == pytest.approx(there[:2], abs=1e-9)
    pattern = _entry(built, "bolted hole pattern")
    assert (
        pattern.status is CheckStatus.PASS and "the farthest pair is 0 mm apart" in pattern.detail
    )


def test_a_part_is_turned_to_meet_holes_that_run_the_other_way():
    """The plate's holes along x instead of y: the bracket turns a quarter to meet them."""

    def along_x(document):
        holes = document["parts"][0]["spec"]["element_params"]["holes"]
        holes[0].update(x=_mm(-15), y=_mm(20))
        holes[1].update(x=_mm(15), y=_mm(20))

    built = _built("bracket_on_plate", along_x)
    low, high = _box(built.parts[1])
    assert (high[0] - low[0], high[1] - low[1], high[2] - low[2]) == pytest.approx((50, 60, 80))
    assert _entry(built, "bolted hole pattern").status is CheckStatus.PASS
    assert _entry(built, "interference").status is CheckStatus.PASS


def test_patterns_that_do_not_match_fail_naming_the_holes():
    def wider(document):
        holes = document["parts"][0]["spec"]["element_params"]["holes"]
        holes[0]["y"], holes[1]["y"] = _mm(-17), _mm(17)

    built = _built("bracket_on_plate", wider)
    pattern = _entry(built, "bolted hole pattern")
    assert pattern.status is CheckStatus.FAIL
    # 34 mm against 30 mm: placed as near as they go, each pair is 2 mm out.
    assert (
        "the farthest pair is 2 mm apart" in pattern.detail and "do not line up" in pattern.detail
    )
    assert "0.6 mm an M6 bolt has to spare" in pattern.detail
    # And the bolts now pass through plate that is not a hole.
    assert _entry(built, "interference").status is CheckStatus.FAIL

    def tolerant(document):
        wider(document)
        document["mates"][0]["position_tolerance"] = _mm(2.5)
        document["hardware"] = []

    assert (
        _entry(_built("bracket_on_plate", tolerant), "bolted hole pattern").status
        is CheckStatus.PASS
    )


def test_holes_with_no_fastener_and_no_tolerance_are_held_to_each_other():
    def bare(document):
        document["hardware"] = []
        document["parts"][0]["spec"]["element_params"]["holes"][1]["y"] = _mm(15.01)

    pattern = _entry(_built("bracket_on_plate", bare), "bolted hole pattern")
    assert pattern.status is CheckStatus.FAIL and "held to a micrometre" in pattern.detail


def test_a_bolt_that_is_too_short_says_how_long_it_must_be():
    def short(document):
        document["hardware"][0]["length"] = _mm(16)

    length = _entry(_built("bracket_on_plate", short), "bolted bolt length")
    assert length.status is CheckStatus.FAIL
    # 6 + 5 of parts, two 1.6 washers and a 5.2 nut.
    assert (
        "needs 19.4 mm to fill the nut" in length.detail and "it is 3.4 mm short" in length.detail
    )
    ok = _entry(_built("bracket_on_plate"), "bolted bolt length")
    assert ok.status is CheckStatus.PASS and "through 11 mm of parts" in ok.detail


def test_a_hole_too_small_for_its_bolt_says_what_to_open_it_to():
    def tight(document):
        for hole in document["parts"][0]["spec"]["element_params"]["holes"]:
            hole["diameter"] = _mm(6.1)

    clearance = _entry(_built("bracket_on_plate", tight), "bolted bolt clearance")
    assert clearance.status is CheckStatus.FAIL
    assert "smallest mated hole is 6.1 mm" in clearance.detail
    assert "open the holes to 6.6 mm" in clearance.detail and "ISO 273" in clearance.reference


def test_a_bolt_with_no_nut_is_not_called_long_enough():
    def tapped(document):
        document["hardware"][0].pop("nut")

    built = _built("bracket_on_plate", tapped)
    assert _entry(built, "bolted bolt length").status is CheckStatus.NOT_EVALUATED
    assert [body.kind for body in built.hardware] == ["washer", "bolt"] * 2


def test_hardware_fills_every_hole_and_is_counted():
    built = _built("flange_pair")
    assert [(line.name, line.quantity, line.envelope) for line in built.bom] == [
        ("lower", 1, False),
        ("upper", 1, False),
        ("ISO7089-M8", 12, True),
        ("ISO4014-M8x40", 6, True),
        ("ISO4032-M8", 6, True),
    ]
    # Each flange is (120^2 - 50^2 - 6 x 9^2) pi/4 x 12 mm^3 of steel at 7,850 kg/m^3.
    volume = (_disc(120) - _disc(50) - 6 * _disc(9)) * 12
    assert built.bom[0].mass_kg == pytest.approx(volume * 7.85e-6, rel=1e-3)
    assert str(built.bom[3]) == " 4  6 x ISO4014-M8x40: bolt (envelope)"
    # Heads above the upper flange, nuts below the lower one.
    bolts = [body for body in built.hardware if body.kind == "bolt"]
    nuts = [body for body in built.hardware if body.kind == "nut"]
    assert {round(body.translation[2], 6) for body in bolts} == {24 + 1.6}
    assert {round(body.translation[2], 6) for body in nuts} == {-1.6}
    assert _entry(built, "joint bolt length").status is CheckStatus.PASS


def test_a_collar_sits_on_its_shaft_where_the_offset_puts_it():
    built = _built("collar_on_shaft")
    shaft, collar = built.parts
    assert _box(collar) == ((-25.0, -25.0, 60.0), (25.0, 25.0, 72.0))
    assert collar.turns_freely and not shaft.turns_freely
    placed = _entry(built, "collar placement")
    assert placed.status is CheckStatus.PASS and "nothing fixes its turn" in placed.detail

    def turned(document):
        document["mates"][0]["rotation_deg"] = 30.0

    again = _built("collar_on_shaft", turned).parts[1]
    assert not again.turns_freely
    assert again.direction((1.0, 0.0, 0.0)) == pytest.approx(
        (math.cos(math.radians(30)), math.sin(math.radians(30)), 0.0)
    )


def test_two_parts_in_one_place_are_named_with_the_volume_they_share():
    """A 20 mm bore on the shaft's 30 mm step: a ring of steel is in two parts at once."""

    def tight(document):
        document["parts"][1]["spec"]["element_params"]["bore"] = _mm(20)

    clash = _entry(_built("collar_on_shaft", tight), "interference")
    assert clash.status is CheckStatus.FAIL and "shaft and collar by" in clash.detail
    volume = float(re.search(r"by ([\d.e+]+) mm\^3", clash.detail).group(1))
    assert volume == pytest.approx((_disc(30) - _disc(20)) * 12, rel=1e-3)


def test_a_lug_stands_on_the_middle_of_its_base_and_its_weld_is_declared():
    built = _built("lug_on_base_plate")
    base, lug = built.parts
    assert _box(base) == ((-150.0, -120.0, 0.0), (150.0, 120.0, 25.0))
    assert _box(lug) == ((-40.0, -6.0, 25.0), (40.0, 6.0, 155.0))
    weld = _entry(built, "welded weld")
    assert weld.status is CheckStatus.NOT_EVALUATED
    assert "6 mm fillet weld joins 'lug' to 'base'" in weld.detail
    assert "welded_connection" in weld.detail
    assert _entry(built, "base part").status is CheckStatus.PASS
    assert _entry(built, "lug part").status is CheckStatus.PASS
    assert not built.card.passed  # the weld is declared and unchecked


def test_a_frame_of_members_stands_on_its_columns():
    built = _built("portal_frame")
    left, beam, right = built.parts
    assert _box(left) == ((-50.0, -100.0, -1500.0), (50.0, 100.0, 1500.0))
    assert _box(beam) == ((-50.0, -100.0, 1500.0), (50.0, 1900.0, 1700.0))
    assert _box(right) == ((-50.0, 1700.0, -1500.0), (50.0, 1900.0, 1500.0))
    assert built.card.passed and built.card.status is CheckStatus.PASS


def test_each_parts_own_verdict_is_on_the_combinations_card():
    def overload(document):
        document["parts"][1]["spec"]["element_params"]["load"] = {"magnitude": 500.0, "unit": "kN"}

    failed = _entry(_built("lug_on_base_plate", overload), "lug part")
    assert failed.status is CheckStatus.FAIL and "its own card is fail" in failed.detail
    drawn = _entry(_built("bracket_on_plate"), "plate part")
    assert drawn.status is CheckStatus.NOT_EVALUATED and "drawn" in drawn.detail


# --- what cannot be placed -------------------------------------------------------------


def test_a_part_left_free_to_slide_is_refused_saying_which_way():
    def one_contact(document):
        document["mates"] = [document["mates"][0]]
        document["welds"] = []

    with pytest.raises(CombinationError, match="leave 'lug' free to slide along") as refused:
        _built("lug_on_base_plate", one_contact)
    message = str(refused.value)
    assert "(1, 0, 0)" in message and "(0, 1, 0)" in message and "'welded'" in message
    assert "Add a mate that fixes it" in message and refused.value.remedies

    def two_of_three(document):
        document["mates"] = document["mates"][:2]

    with pytest.raises(CombinationError, match=r"free to slide along \(0, 1, 0\)"):
        _built("lug_on_base_plate", two_of_three)


def test_mates_that_contradict_each_other_are_refused_naming_them():
    def both_sides(document):
        document["mates"].append(
            {
                "id": "other-side",
                "kind": "edge_flush",
                "place": {"part": "lug", "face": "right"},
                "on": {"part": "base", "face": "right"},
            }
        )

    with pytest.raises(CombinationError, match="contradict each other for 'lug'") as refused:
        _built("lug_on_base_plate", both_sides)
    assert "'across'" in str(refused.value) and "'other-side'" in str(refused.value)

    def two_ways(document):
        document["mates"].append(
            {
                "id": "upside-down",
                "kind": "face_to_face",
                "place": {"part": "lug", "face": "top"},
                "on": {"part": "base", "face": "top"},
            }
        )

    with pytest.raises(CombinationError, match="face two ways at once"):
        _built("lug_on_base_plate", two_ways)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda d: d["mates"][0]["place"].update(part="bracket2"), "names the part 'bracket2'"),
        (lambda d: d["mates"][0]["place"].update(holes=["b1"]), "pairs 1 holes with 2"),
        (lambda d: d["mates"][0]["place"].pop("face"), "names no face"),
        (lambda d: d["mates"][0]["place"].update(holes=[]), "lists no holes"),
        (lambda d: d["mates"][0]["place"].update(holes=["b1", "b9"]), "names the hole 'b9'"),
        (lambda d: d["mates"][0].update(place=d["mates"][0]["on"]), "to itself"),
        (lambda d: d["parts"].reverse(), "which is the base"),
        (lambda d: d["parts"].append(copy.deepcopy(d["parts"][1])), "more than once"),
        (lambda d: d["mates"].append(copy.deepcopy(d["mates"][0])), "more than once"),
        (lambda d: d["hardware"][0].update(mate="nowhere"), "not a hole_pattern mate"),
        (lambda d: d["hardware"][0].update(bolt="ISO4762-M7"), "no bundled bolt is designated"),
        (lambda d: d["hardware"][0].update(washer="ISO7089-M7"), "no bundled washer"),
        (lambda d: d["hardware"][0].update(nut="ISO4032-M7"), "no bundled nut"),
        (lambda d: d["hardware"][0].update(length=_mm(-5)), "bolt length"),
        (lambda d: d["mates"][0].update(offset={"magnitude": 1, "unit": "kN"}), "not a length"),
        (lambda d: d["mates"][0].update(kind="glued"), "not valid"),
        (lambda d: d.update(extra=1), "not valid"),
        (
            lambda d: d["parts"][1]["spec"]["element_params"].update(thickness=_mm(-1)),
            "cannot be built",
        ),
    ],
)
def test_a_document_that_cannot_be_placed_is_refused(change, reason):
    with pytest.raises(CombinationError, match=reason) as refused:
        _built("bracket_on_plate", change)
    assert refused.value.remedies


def test_a_part_nothing_places_and_a_weld_on_no_contact_are_refused():
    def adrift(document):
        document["parts"].append({"id": "spare", "spec": document["parts"][1]["spec"]})

    with pytest.raises(CombinationError, match=r"no mate places \['spare'\]"):
        _built("bracket_on_plate", adrift)

    def welded_holes(document):
        document["welds"] = [{"mate": "bolted", "type": "fillet", "size": _mm(4)}]

    with pytest.raises(CombinationError, match="not a face_to_face mate"):
        _built("bracket_on_plate", welded_holes)

    def base_placed(document):
        document["mates"][0]["place"], document["mates"][0]["on"] = (
            document["mates"][0]["on"],
            document["mates"][0]["place"],
        )

    with pytest.raises(CombinationError, match="which is the base"):
        _built("bracket_on_plate", base_placed)


def test_a_shaft_in_bore_mate_takes_an_axis_or_a_feature_and_not_both():
    def both(document):
        document["mates"][0]["place"]["feature"] = "bore"

    with pytest.raises(CombinationError, match="exactly one"):
        _built("collar_on_shaft", both)


# --- what the engineer takes away ------------------------------------------------------


def test_the_assembly_opens_as_an_assembly_with_named_components(tmp_path):
    from anvilate.context import read_cad_file
    from anvilate.export.gate import authorize_export

    built = _built("flange_pair")
    path = write_step_assembly(
        built, tmp_path / "pair.step", authorization=authorize_export(built.card, override=True)
    )
    text = path.read_text(encoding="utf-8")
    assert re.findall(r"PRODUCT\('([^']*)'", text) == [
        "flange-pair",
        "lower",
        "upper",
        "ISO7089-M8 (envelope)",
        "ISO4014-M8x40 (envelope)",
        "ISO4032-M8 (envelope)",
    ]
    # One usage per body: two flanges, twelve washers, six bolts, six nuts.
    assert text.count("NEXT_ASSEMBLY_USAGE_OCCURRENCE(") == 26 == len(built.bodies)
    assert "UNVALIDATED" in text and "AP242" in text
    facts = read_cad_file(path)
    assert len(facts.solids) == 26
    assert facts.volume_mm3 == pytest.approx(
        sum(float(s.volume) for _l, s in built.bodies), rel=1e-9
    )
    assert facts.size_mm == pytest.approx((120.0, 120.0, 45.3), abs=1e-6)


def test_the_assembly_keeps_each_part_where_the_mates_put_it(tmp_path):
    from anvilate.context import read_cad_file
    from anvilate.export.gate import authorize_export

    built = _built("portal_frame")
    path = write_step_assembly(
        built, tmp_path / "frame.step", authorization=authorize_export(built.card)
    )
    assert "VALIDATED" in path.read_text(encoding="utf-8")
    facts = read_cad_file(path)
    assert facts.size_mm == pytest.approx((100.0, 2000.0, 3200.0), abs=1e-6)
    assert len(facts.solids) == 3 and "left_column" in facts.products


def test_the_picture_numbers_each_line_of_the_parts_list():
    built = _built("bracket_on_plate")
    svg, width, height = render_combination(built, width_px=800, format="svg")
    drawn = svg.decode("utf-8")
    assert (width, height > 600) == (800, True)
    assert re.findall(r'data-balloon="(\d+)"', drawn) == ["1", "2", "3", "4", "5"]
    assert len(built.bom) == 5
    tones = set(re.findall(r'<polygon data-face="\d+" points="[^"]+" fill="(#[0-9a-f]{6})"', drawn))
    from anvilate import projection

    assert tones & set(projection.ASSEMBLY_PALETTES[0]) and tones & set(
        projection.ASSEMBLY_PALETTES[1]
    )
    assert tones & set(projection.ENVELOPE_PALETTE)
    png, _w, _h = render_combination(built, width_px=640)
    assert png.startswith(b"\x89PNG") and len(png) > 5000
    with pytest.raises(CombinationError, match="png or svg"):
        render_combination(built, format="gif")
    with pytest.raises(CombinationError, match="width_px"):
        render_combination(built, width_px=10)


def test_neighbouring_parts_stay_apart_on_a_greyscale_print():
    """The middle tone of each palette, as a printer's grey: no two within 0.04 of each other
    in relative luminance, and the hardware's grey lighter than every designed part's."""
    from anvilate import projection

    def luminance(colour: str) -> float:
        channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    middles = sorted(luminance(palette[1]) for palette in projection.ASSEMBLY_PALETTES)
    assert len(middles) == 6
    assert min(b - a for a, b in zip(middles, middles[1:], strict=False)) >= 0.04, middles
    assert luminance(projection.ENVELOPE_PALETTE[1]) > max(middles[:-1])
    for dark, middle, light in (*projection.ASSEMBLY_PALETTES, projection.ENVELOPE_PALETTE):
        assert luminance(dark) < luminance(middle) < luminance(light)


def test_a_part_is_listed_after_the_parts_it_is_placed_on():
    def out_of_order(document):
        left, beam, right = document["parts"]
        document["parts"] = [left, right, beam]

    with pytest.raises(CombinationError, match="comes after it; list a part after"):
        _built("portal_frame", out_of_order)


def test_each_balloon_sits_on_its_own_part_and_no_two_share_a_place():
    """Two flanges on one axis had both balloons in the bore, at the middle of each part's
    box, and a bolt, its washer and its nut were three balloons on one stack."""
    built = _built("flange_pair")
    svg, _width, _height = render_combination(built, width_px=900, format="svg")
    centres = {}
    for label, points in re.findall(r'data-balloon="(\d+)" points="([^"]+)"', svg.decode("utf-8")):
        pairs = [tuple(map(float, point.split(","))) for point in points.split()]
        centres[label] = (
            sum(x for x, _y in pairs) / len(pairs),
            sum(y for _x, y in pairs) / len(pairs),
        )
    assert sorted(centres) == ["1", "2", "3", "4", "5"]
    labels = sorted(centres)
    for index, first in enumerate(labels):
        for second in labels[index + 1 :]:
            assert math.dist(centres[first], centres[second]) > 18, (first, second)
    # The two flanges' balloons are apart from top to bottom, as the flanges are.
    assert centres["1"][1] > centres["2"][1]


def _doweled(pin: str = "ISO2338-4", length: float = 8.0, hole: float = 4.0):
    """The bracket on its plate, with two dowel holes beside the bolts and a pin in each.

    The bracket's holes sit 10 mm nearer its heel than the plate's are from its middle, as
    its bolt holes do, so the two patterns place it in the same position.
    """

    def change(document: dict) -> None:
        plate = document["parts"][0]["spec"]["element_params"]
        bracket = document["parts"][1]["spec"]["element_params"]
        for tag, y in (("d1", -12.0), ("d2", 12.0)):
            plate["holes"].append({"tag": tag, "x": _mm(0.0), "y": _mm(y), "diameter": _mm(hole)})
        for tag, y in (("p1", -12.0), ("p2", 12.0)):
            bracket["base_holes"].append(
                {"tag": tag, "x": _mm(-10.0), "y": _mm(y), "diameter": _mm(hole)}
            )
        document["mates"].append(
            {
                "id": "doweled",
                "kind": "hole_pattern",
                "place": {"part": "bracket", "face": "bottom", "holes": ["p1", "p2"]},
                "on": {"part": "plate", "face": "top", "holes": ["d1", "d2"]},
            }
        )
        document["hardware"].append({"mate": "doweled", "pin": pin, "length": _mm(length)})

    return change


def test_a_dowel_pin_sits_in_each_hole_half_each_side_of_the_mating_plane():
    """Two 4 x 8 pins between a 5 mm bracket and a 6 mm plate that meet at z = 6."""
    plain, built = _built("bracket_on_plate"), _built("bracket_on_plate", _doweled())
    # The second pattern agrees with the first: the bracket is where the bolts put it.
    assert _box(built.parts[1]) == _box(plain.parts[1])
    pins = [body for body in built.hardware if body.kind == "pin"]
    assert len(pins) == 2 and {body.designation for body in pins} == {"ISO2338-4x8"}
    for pin, y in zip(pins, (-12.0, 12.0), strict=True):
        box = pin.shape.bounding_box()
        assert (box.min.Z, box.max.Z) == pytest.approx((2.0, 10.0), abs=1e-6)
        assert ((box.min.X + box.max.X) / 2, (box.min.Y + box.max.Y) / 2) == pytest.approx(
            (0.0, y), abs=1e-6
        )
        assert pin.shape.volume == pytest.approx(_disc(4) * 8, rel=1e-6)
    assert str(built.bom[-1]) == " 6  2 x ISO2338-4x8: pin (envelope)"
    assert _entry(built, "doweled pin fit").status is CheckStatus.PASS
    assert _entry(built, "doweled pin length").status is CheckStatus.PASS
    # No edition of ISO 2338 is recorded with the bundled table, so none is cited.
    assert _entry(built, "doweled pin fit").reference is None
    assert _entry(built, "doweled pin length").reference is None
    assert "held to a micrometre" in _entry(built, "doweled hole pattern").detail
    # A pin filling its hole touches it and overlaps nothing.
    assert _entry(built, "interference").status is CheckStatus.PASS
    assert len(built.bodies) == len(plain.bodies) + 2


@pytest.mark.parametrize(
    ("change", "check", "said"),
    [
        # A pin in a clearance hole locates nothing.
        ({"hole": 4.5}, "pin fit", "p1 is 4.5 mm, d1 is 4.5 mm, p2 is 4.5 mm, d2 is 4.5 mm"),
        # Half of 12 is 6, and the bracket is 5 thick.
        ({"length": 12.0}, "pin length", "stands 1 mm proud; 10 mm or less sits inside both"),
        # ISO 2338 stocks a 4 mm pin from 8 mm.
        ({"length": 6.0}, "pin length", "stocks this pin from 8 to 40 mm"),
        # A 6 mm pin starts at 12 mm, which the 5 mm bracket cannot take either.
        (
            {"pin": "ISO2338-6", "hole": 6.0, "length": 10.0},
            "pin length",
            "stocks this pin from 12 to 60 mm",
        ),
    ],
)
def test_a_dowel_pin_that_cannot_locate_or_does_not_fit_fails_and_says_why(change, check, said):
    built = _built("bracket_on_plate", _doweled(**change))
    entry = _entry(built, f"doweled {check}")
    assert entry.status is CheckStatus.FAIL and said in entry.detail
    other = "pin length" if check == "pin fit" else "pin fit"
    assert _entry(built, f"doweled {other}").status is CheckStatus.PASS
    assert built.card.status is not CheckStatus.PASS


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda h: h.update(bolt="ISO4762-M4"), "a bolt and a pin"),
        (lambda h: h.pop("pin"), "neither a bolt nor a pin"),
        (lambda h: h.update(washer="ISO7089-M4"), "a pin locates and does not clamp"),
        (lambda h: h.update(nut="ISO4032-M4"), "a pin locates and does not clamp"),
        (lambda h: h.update(length=_mm(0)), "its pin length"),
        (lambda h: h.update(pin="ISO2338-7"), "no bundled pin is designated 'ISO2338-7'"),
    ],
)
def test_hardware_is_a_bolt_or_a_pin_and_a_pin_takes_nothing_else(change, reason):
    def broken(document: dict) -> None:
        _doweled()(document)
        change(document["hardware"][-1])

    with pytest.raises(CombinationError, match=reason):
        _built("bracket_on_plate", broken)


def _collar(change=None):
    return _built("collar_on_shaft", change)


def test_a_collar_sits_on_the_step_its_bore_is_made_for():
    """A 30 mm bore on the shaft's 30 mm step, over the collar's 12 mm width."""
    seat = _entry(_collar(), "seated fit")
    assert seat.status is CheckStatus.PASS
    assert "the 30 mm bore of 'collar' sits on 30 mm of 'shaft' over 12 mm" in seat.detail
    assert "30 mm H7/g6 is a clearance fit" in seat.detail  # the example states its fit
    bare = _entry(_collar(lambda d: d["mates"][0].pop("fit")), "seated fit")
    assert bare.status is CheckStatus.PASS
    assert "no fit is declared" in bare.detail and "declare fit on the mate" in bare.detail


@pytest.mark.parametrize(
    ("fit", "said"),
    [
        # 30 mm: H7 is +21/0 um, g6 -7/-20, k6 +15/+2, p6 +35/+22 (ISO 286-2).
        ("H7/g6", "30 mm H7/g6 is a clearance fit, 0.007 to 0.041 mm of clearance"),
        ("H7/h6", "30 mm H7/h6 is a clearance fit, 0.000 to 0.034 mm of clearance"),
        (
            "H7/k6",
            "30 mm H7/k6 is a transition fit, from 0.015 mm of interference to 0.019 mm of "
            "clearance",
        ),
        ("H7/p6", "30 mm H7/p6 is an interference fit, 0.001 to 0.035 mm of interference"),
    ],
)
def test_a_declared_fit_is_stated_with_what_it_leaves_between_bore_and_shaft(fit, said):
    seat = _entry(_collar(lambda d: d["mates"][0].update(fit=fit)), "seated fit")
    assert seat.status is CheckStatus.PASS and said in seat.detail
    assert seat.reference == "ISO 286-1:2010, standard tolerance grades and fundamental deviations"


@pytest.mark.parametrize(
    ("change", "said"),
    [
        # 105 mm up the shaft is its 25 mm step: the collar is placed, clear, and loose.
        (
            lambda d: d["mates"][1].update(offset=_mm(-105.0)),
            "'collar' has a 30 mm bore where 'shaft' is 25 mm",
        ),
        (
            lambda d: d["parts"][1]["spec"]["element_params"].update(bore=_mm(32.0)),
            "'collar' has a 32 mm bore where 'shaft' is 30 mm",
        ),
    ],
)
def test_a_bore_on_a_shaft_of_another_size_is_not_seated(change, said):
    built = _collar(change)
    seat = _entry(built, "seated fit")
    assert seat.status is CheckStatus.FAIL and said in seat.detail
    # Nothing overlaps, which is why nothing else on the card noticed.
    assert _entry(built, "interference").status is CheckStatus.PASS
    assert built.card.status is CheckStatus.FAIL


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda d: d["mates"][0].update(fit="h6/H7"), "must be hole/shaft"),
        (lambda d: d["mates"][0].update(fit="H7"), "expected a hole and shaft zone"),
        (lambda d: d["mates"][0].update(fit="X9/z3"), "zone 'X' is not yet encoded"),
        (lambda d: d["mates"][1].update(fit="H7/g6"), "is edge_flush and states a fit"),
    ],
)
def test_a_fit_that_is_not_one_is_refused_and_names_the_mate(change, reason):
    with pytest.raises(CombinationError, match=reason) as refused:
        _collar(change)
    assert "Value error" not in str(refused.value)
    assert refused.value.remedies


def test_parts_that_only_share_an_axis_have_no_seat_to_check():
    """Stacked end to end, a collar past the end of the shaft sits on nothing.

    With no fit declared that is an alignment and there is nothing to say. With one
    declared, the fit has no shaft in a bore to be between, and fails.
    """

    def beyond(document: dict) -> None:
        document["mates"][1].update(offset=_mm(-140.0))

    def aligned(document: dict) -> None:
        beyond(document)
        document["mates"][0].pop("fit")

    assert not [e for e in _collar(aligned).card.entries if e.name == "seated fit"]
    seat = _entry(_collar(beyond), "seated fit")
    assert seat.status is CheckStatus.FAIL and "no bore of one part has the other" in seat.detail


def test_a_part_that_is_a_bare_primitive_goes_out_under_its_own_name(tmp_path):
    """The lug's base plate is a plain box standing on z = 0, and that is a location.

    The document stored the located box as an unnamed prototype, the product went out
    under the kernel's placeholder name, and the writer refused its own file: this worked
    combination could not be exported at all, and no test had tried. The part is where it
    was put, at the size it was built.
    """
    from anvilate.context import read_cad_file
    from anvilate.export.gate import authorize_export

    built = _built("lug_on_base_plate")
    path = write_step_assembly(
        built, tmp_path / "lug.step", authorization=authorize_export(built.card, override=True)
    )
    text = path.read_text(encoding="utf-8")
    assert re.findall(r"PRODUCT\('([^']*)'", text) == ["lug-on-base-plate", "base", "lug"]
    facts = read_cad_file(path)
    assert [(o.name, o.translation_mm) for o in facts.assembly][0] == ("base", (0.0, 0.0, 0.0))
    assert facts.volume_mm3 == pytest.approx(
        sum(part.built.volume_mm3 for part in built.parts), rel=1e-9
    )
    low, high = _box(built.parts[0])
    assert facts.solids[0].size_mm == pytest.approx(
        [h - lo for lo, h in zip(low, high, strict=True)]
    )


def _loaded(**joint):
    """The bracket on its plate with its two M6 bolts carrying a shear across the joint."""
    stated = {
        "load": {"magnitude": 6.0, "unit": "kN"},
        "bolt_material": "ASTM-A36",
        "min_safety_factor": 2.0,
        **joint,
    }

    def change(document: dict) -> None:
        for name, value in stated.items():
            if value is None:
                document["hardware"][0].pop(name, None)
            else:
                document["hardware"][0][name] = value

    return change


def test_a_loaded_joint_is_screened_from_what_the_mate_measured():
    """6 kN across two M6 bolts is 3 kN each, on pi 6^2/4 of bolt and on 6 x t of each part.

    Bolt shear is 106.1 MPa against 0.577 x 250 of A36; bearing is 100 MPa on the 5 mm
    bracket and 83.3 on the 6 mm plate, each against the 250 of the part's own material.
    """
    built = _built("bracket_on_plate", _loaded())
    shear = _entry(built, "bolted bolt shear")
    assert shear.status is CheckStatus.FAIL
    assert shear.safety_factor == pytest.approx(0.577 * 250 / (3000 / _disc(6)), rel=1e-3)
    on_bracket, on_plate = (_entry(built, f"bolted bearing on {p}") for p in ("bracket", "plate"))
    assert on_bracket.safety_factor == pytest.approx(250 / (3000 / (6 * 5)))
    assert on_plate.safety_factor == pytest.approx(250 / (3000 / (6 * 6)))
    assert on_bracket.status is CheckStatus.PASS and on_plate.status is CheckStatus.PASS
    assert {e.required_safety_factor for e in (shear, on_bracket, on_plate)} == {2.0}
    assert shear.reference.startswith("AISC 360-16") and shear.derivation is not None
    # The bolt is screened once, and nothing is said of an edge distance nobody declared.
    names = [entry.name for entry in built.card.entries]
    assert names.count("bolted bolt shear") == 1 and not [n for n in names if "tear-out" in n]
    assert built.card.status is CheckStatus.FAIL
    # A lighter load passes all three, and an unloaded joint has none of them.
    light = _built("bracket_on_plate", _loaded(load={"magnitude": 3.0, "unit": "kN"}))
    assert _entry(light, "bolted bolt shear").status is CheckStatus.PASS
    assert not [e for e in _built("bracket_on_plate").card.entries if "bearing" in e.name]


def test_a_bolt_whose_strength_is_only_typical_is_not_passed():
    """The screen's own rule carries through: a typical yield is not a design allowable."""
    built = _built("bracket_on_plate", _loaded(bolt_material="AISI-4140"))
    shear = _entry(built, "bolted bolt shear")
    assert shear.status is CheckStatus.NOT_EVALUATED and "typical" in shear.detail
    assert _entry(built, "bolted bearing on plate").status is CheckStatus.NOT_EVALUATED


@pytest.mark.parametrize(
    ("joint", "reason"),
    [
        ({"bolt_material": None}, "a loaded joint without bolt_material"),
        ({"min_safety_factor": None, "load": None}, "without load and min_safety_factor"),
        ({"load": _mm(6)}, "it is the shear force the joint carries"),
        ({"load": {"magnitude": 0.0, "unit": "kN"}}, "it is the shear force the joint carries"),
        ({"min_safety_factor": 0.0}, "it is a number above zero"),
        ({"bolt_material": "STEEL"}, "cannot be screened: unknown material 'STEEL'"),
    ],
)
def test_a_loaded_joint_states_its_load_its_bolt_and_its_factor_together(joint, reason):
    with pytest.raises(CombinationError, match=reason):
        _built("bracket_on_plate", _loaded(**joint))


def test_a_dowel_pin_carries_no_declared_load():
    def loaded_pin(document: dict) -> None:
        _doweled()(document)
        document["hardware"][-1].update(
            load={"magnitude": 1.0, "unit": "kN"}, bolt_material="ASTM-A36", min_safety_factor=2.0
        )

    with pytest.raises(CombinationError, match="loads a dowel pin"):
        _built("bracket_on_plate", loaded_pin)


def _keyed(change=None, **key):
    """The collar on its shaft with a keyway under it, a keyseat in it, and a key in both.

    The shaft's 30 mm step runs from 40 to 100 mm and gets an 8 x 4 keyway from 55 to 75;
    the collar sits from 60 to 72 with an 8 x 3.3 keyseat; the key is 8 x 7 x 20.
    """

    def build(document: dict) -> None:
        document["parts"][0]["spec"]["element_params"]["keyways"].append(
            {"step": 2, "width": _mm(8), "depth": _mm(4), "length": _mm(20), "offset": _mm(15)}
        )
        document["parts"][1]["spec"]["element_params"].update(
            keyway_width=_mm(8), keyway_depth=_mm(3.3)
        )
        document["keys"] = [
            {"mate": "seated", "keyway": 2, "width": _mm(8), "height": _mm(7), "length": _mm(20)}
        ]
        for name, value in key.items():
            if value is None:
                document["keys"][0].pop(name, None)
            else:
                document["keys"][0][name] = value
        if change is not None:
            change(document)

    return _built("collar_on_shaft", build)


def test_a_key_sits_in_the_shafts_keyway_and_the_hubs_keyseat():
    built = _keyed()
    (key,) = [body for body in built.hardware if body.kind == "key"]
    box = key.shape.bounding_box()
    # On the keyway's floor, 4 mm below the 30 mm step's crown, and 7 mm tall from there.
    assert (box.min.X, box.max.X) == pytest.approx((11.0, 18.0), abs=1e-6)
    assert (box.min.Y, box.max.Y) == pytest.approx((-4.0, 4.0), abs=1e-6)
    assert (box.min.Z, box.max.Z) == pytest.approx((55.0, 75.0), abs=1e-6)
    assert str(built.bom[-1]) == " 3  1 x key 8x7x20: key (envelope)"
    assert "4 mm of the 7 mm key is in the shaft and 3 mm in the hub" in (
        _entry(built, "seated key height").detail
    )
    assert "'collar' covers 12 mm of it" in _entry(built, "seated key length").detail
    for check in ("width", "height", "length"):
        assert _entry(built, f"seated key {check}").status is CheckStatus.PASS, check
    assert _entry(built, "interference").status is CheckStatus.PASS
    assert not [e for e in built.card.entries if "shear" in e.name]


@pytest.mark.parametrize(
    ("key", "change", "check", "said"),
    [
        ({"width": _mm(6)}, None, "width", "the key is 6 mm wide and the keyway in 'shaft' is 8"),
        (
            {},
            lambda d: d["parts"][1]["spec"]["element_params"].update(keyway_width=_mm(10)),
            "width",
            "the keyseat in 'collar' is 10 mm",
        ),
        (
            {},
            lambda d: [
                d["parts"][1]["spec"]["element_params"].pop(k)
                for k in ("keyway_width", "keyway_depth")
            ],
            "width",
            "'collar' has no keyseat for it",
        ),
        (
            {},
            lambda d: d["mates"][0].update(rotation_deg=90.0),
            "width",
            "turned away from the keyway",
        ),
        ({"height": _mm(4)}, None, "height", "nothing of it stands proud"),
        ({"height": _mm(8)}, None, "height", "it is 0.7 mm too tall"),
        ({"length": _mm(24)}, None, "length", "the key is 24 mm long and the keyway is 20"),
        (
            {},
            lambda d: d["mates"][1].update(offset=_mm(-80.0)),
            "length",
            "'collar' is not over the keyway, which runs from 55 to 75 mm",
        ),
    ],
)
def test_a_key_that_does_not_fit_fails_the_check_that_names_why(key, change, check, said):
    built = _keyed(change, **key)
    entry = _entry(built, f"seated key {check}")
    assert entry.status is CheckStatus.FAIL and said in entry.detail
    assert built.card.status is CheckStatus.FAIL


def test_a_key_that_states_its_torque_is_screened_over_the_length_the_hub_covers():
    """60 N m on a 30 mm shaft through 12 mm of an 8 x 7 key.

    Shear is 2T/(d w L) = 41.67 MPa and side bearing 4T/(d h L) = 95.24 MPa.
    """
    loaded = {
        "torque": {"magnitude": 60.0, "unit": "N*m"},
        "allowable_shear": {"magnitude": 100.0, "unit": "MPa"},
        "allowable_bearing": {"magnitude": 180.0, "unit": "MPa"},
    }
    built = _keyed(**loaded)
    shear, bearing = _entry(built, "seated key shear"), _entry(built, "seated key side bearing")
    assert shear.safety_factor == pytest.approx(100 / (2 * 60000 / (30 * 8 * 12)))
    assert bearing.safety_factor == pytest.approx(180 / (4 * 60000 / (30 * 7 * 12)))
    assert shear.status is CheckStatus.PASS and bearing.status is CheckStatus.FAIL
    assert shear.required_safety_factor == 2.0 and shear.derivation is not None
    eased = _keyed(**loaded, min_safety_factor=1.5)
    assert _entry(eased, "seated key side bearing").status is CheckStatus.PASS
    # With the hub off the keyway there is no engaged length, and nothing to screen on.
    off = _keyed(lambda d: d["mates"][1].update(offset=_mm(-80.0)), **loaded)
    assert not [e for e in off.card.entries if "shear" in e.name]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda k: k.update(mate="located"), "which is not a shaft_in_bore mate"),
        (lambda k: k.update(keyway=5), "neither 'collar' nor 'shaft' is a shaft with that many"),
        (lambda k: k.update(width=_mm(0)), "states its width as 0"),
        (lambda k: k.update(torque={"magnitude": 60.0, "unit": "N*m"}), "without allowable_shear"),
        (lambda k: k.update(min_safety_factor=1.5), "for a key that states its torque"),
    ],
)
def test_a_key_document_that_cannot_be_seated_is_refused(change, reason):
    with pytest.raises(CombinationError, match=reason):
        _keyed(lambda d: change(d["keys"][0]))


def test_a_failing_check_is_marked_on_the_part_it_is_about():
    """An X beside the part a failing mate places, and a row under the parts list.

    A collar over the wrong step fails its fit: the X goes on the collar, not the shaft.
    A picture of a combination with nothing failing has no X and no extra row.
    """
    from anvilate.combination import _failing, _numbered

    sound = _collar()
    marks, rows = _failing(sound, *_numbered(sound))
    assert rows == [] and [label for label, _index in marks] == ["1", "2"]

    loose = _collar(lambda d: d["mates"][1].update(offset=_mm(-105.0)))
    bodies, numbered = _numbered(loose)
    marks, rows = _failing(loose, bodies, numbered)
    assert rows == [" X  fails: seated fit"]
    assert marks[-1] == ("X", [label for label, _s, _e in bodies].index("collar"))
    svg, _width, height = render_combination(loose, format="svg")
    assert re.findall(r'data-balloon="(\w+)"', svg.decode("utf-8")) == ["1", "2", "X"]
    assert height > render_combination(sound, format="svg")[2]  # the row it added
    # Two failing checks on one mate are two rows and one X.
    both = _keyed(None, width=_mm(6), height=_mm(8))
    marks, rows = _failing(both, *_numbered(both))
    assert len(rows) >= 2 and [label for label, _i in marks].count("X") == 1
