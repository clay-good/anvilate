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
        assert set(mate) <= {"id", "kind", "place", "on", "offset", "rotation_deg"}
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
