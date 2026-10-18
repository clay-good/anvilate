"""Geometric DFM rules measured on built solids, each finding held to a hand reading.

The parts are the catalog's examples and a few small solids built here, whose geometry is
known exactly: an L-shaped block has one sharp inside corner along z; an extrusion tapered
by 2° has 2° of draft on every side.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from anvilate.dfm import DfmProcess, default_profile, screen_dfm  # noqa: E402
from anvilate.features import Feature  # noqa: E402
from anvilate.geometry import BuiltGeometry, build_spec  # noqa: E402
from anvilate.refusal import RefusalError  # noqa: E402
from anvilate.scorecard import CheckStatus  # noqa: E402
from anvilate.spec import load_spec_yaml  # noqa: E402

_PARTS = Path(__file__).resolve().parents[1] / "examples" / "parts"


def _part(name: str) -> BuiltGeometry:
    return build_spec(load_spec_yaml((_PARTS / f"{name}.spec.yaml").read_text()))


def _solid(shape, name="block", **dims) -> BuiltGeometry:
    return BuiltGeometry(name=name, pattern="test/1", shape=shape, faces={}, dimensions_mm=dims)


def _l_block() -> BuiltGeometry:
    from build123d import Box, Pos

    # 40 × 40 × 10 with a 20 × 20 quarter removed: one concave edge along z, sharp
    return _solid(Box(40, 40, 10) - Pos(10, 10, 0) * Box(20, 20, 10), name="l-block")


# --- CNC milling ---------------------------------------------------------------------------


def test_a_sharp_inside_corner_along_the_tool_axis_is_radius_zero():
    (radius, _) = screen_dfm(_l_block(), default_profile(DfmProcess.CNC_MILLING),
                               tool_direction=(0, 0, 1))  # fmt: skip
    assert radius.status is CheckStatus.FAIL
    assert (
        "1 of 1 internal corner radii" in radius.detail and "sharp internal edge" in radius.detail
    )
    assert radius.comparison.measured.magnitude == 0.0
    assert "a practice default" in radius.detail


def test_a_corner_across_the_tool_axis_takes_no_cutter_radius():
    (radius, _) = screen_dfm(_l_block(), default_profile(DfmProcess.CNC_MILLING),
                               tool_direction=(1, 0, 0))  # fmt: skip
    assert radius.status is CheckStatus.PASS


def test_an_enclosure_pocket_is_judged_on_its_vertical_corners_only():
    enclosure = _part("enclosure")  # corner radius 6, wall 3: pocket corners of radius 3
    profile = default_profile(DfmProcess.CNC_MILLING)
    (radius, holes) = screen_dfm(enclosure, profile, tool_direction=(0, 0, 1))
    # four pocket corners about z; the floor-to-wall edges, across the axis, are not judged
    assert radius.status is CheckStatus.PASS and "all 4 internal corner radii" in radius.detail
    shop = profile.override("internal_radius_min", 4.0, source="shop: smallest pocket tool Ø8")
    (radius, _) = screen_dfm(enclosure, shop, tool_direction=(0, 0, 1))
    assert radius.status is CheckStatus.FAIL
    assert radius.comparison.measured.magnitude == pytest.approx(3.0, abs=1e-6)
    assert "shop: smallest pocket tool Ø8" in radius.detail
    assert radius.repair_hint is None  # the pocket radius is the part's, not this screen's
    assert holes.status is CheckStatus.PASS


def test_a_deep_hole_is_reported_by_its_ratio():
    plate = _part("mounting_plate")
    deep = Feature(tag="deep", kind="blind_hole", diameter_mm=3.0, depth_mm=36.0,
                   position_mm=(0.0, 0.0, 6.0), axis=(0.0, 0.0, 1.0))  # fmt: skip
    built = dataclasses.replace(plate, features=(*plate.features, deep))
    (_, holes) = screen_dfm(built, default_profile(DfmProcess.CNC_MILLING),
                              tool_direction=(0, 0, 1))  # fmt: skip
    assert holes.status is CheckStatus.FAIL and "deep (blind_hole" in holes.detail
    assert holes.comparison.measured.magnitude == pytest.approx(12.0)  # 36/3


# --- sheet metal ---------------------------------------------------------------------------


def test_bend_radius_against_thickness():
    bracket = _part("sheet_metal_bracket")  # inside radius 2, thickness 2: ratio 1
    profile = default_profile(DfmProcess.SHEET_METAL)
    (bend, _, _, _) = screen_dfm(bracket, profile)
    assert bend.status is CheckStatus.PASS
    brake = profile.override("bend_radius_ratio_min", 1.5, source="shop brake tooling list")
    (bend, _, _, _) = screen_dfm(bracket, brake)
    assert bend.status is CheckStatus.FAIL
    assert "an inside_radius of 3 mm meets the limit" in bend.detail  # 1.5 × 2 mm


def test_a_hole_too_close_to_a_bend():
    bracket = _part("sheet_metal_bracket")
    (a, _), _ = bracket.profile.bends[0]  # the first bend line at x = 28.26
    near = dataclasses.replace(bracket.profile, circles=((a + 5.0, 0.0, 4.0),))
    built = dataclasses.replace(bracket, profile=near)
    (_, to_bend, to_edge, _) = screen_dfm(built, default_profile(DfmProcess.SHEET_METAL))
    # edge of a Ø4 hole 5 mm from the bend: 3 mm, 1.5 thicknesses, under 2.5
    assert to_bend.status is CheckStatus.FAIL
    assert to_bend.comparison.measured.magnitude == pytest.approx(1.5, abs=1e-9)
    # 18 mm from the blank's long edge (y = ±20): 9 thicknesses
    assert to_edge.status is CheckStatus.PASS
    assert to_edge.comparison.measured.magnitude == pytest.approx(9.0, abs=1e-9)


def test_a_part_that_is_not_formed_is_refused_for_sheet_metal():
    with pytest.raises(RefusalError, match="not a formed sheet-metal part"):
        screen_dfm(_part("mounting_plate"), default_profile(DfmProcess.SHEET_METAL))


# --- injection molding and additive --------------------------------------------------------


def test_an_undrafted_box_fails_and_a_drafted_one_passes():
    from build123d import Rectangle, extrude

    enclosure = _part("enclosure")
    (draft, _) = screen_dfm(enclosure, default_profile(DfmProcess.INJECTION_MOLDING),
                            pull_direction=(0, 0, 1))  # fmt: skip
    assert draft.status is CheckStatus.FAIL and draft.comparison.measured.magnitude == 0.0
    tapered = _solid(extrude(Rectangle(40, 30), amount=20, taper=2), name="tapered")
    (draft, _) = screen_dfm(tapered, default_profile(DfmProcess.INJECTION_MOLDING),
                            pull_direction=(0, 0, 1))  # fmt: skip
    assert draft.status is CheckStatus.PASS
    assert draft.comparison.measured.magnitude == pytest.approx(2.0, abs=1e-6)


def test_an_upside_down_enclosure_has_a_floor_to_support():
    enclosure = _part("enclosure")
    profile = default_profile(DfmProcess.ADDITIVE)
    (upright,) = screen_dfm(enclosure, profile, build_direction=(0, 0, 1))
    assert upright.status is CheckStatus.PASS
    (flipped,) = screen_dfm(enclosure, profile, build_direction=(0, 0, -1))
    # built rim-down, the inside of the floor faces straight down: 0° above horizontal
    assert flipped.status is CheckStatus.FAIL
    assert flipped.comparison.measured.magnitude == pytest.approx(0.0, abs=1e-9)


# --- refusals ------------------------------------------------------------------------------


def test_each_process_needs_its_direction():
    with pytest.raises(RefusalError, match="tool_direction"):
        screen_dfm(_l_block(), default_profile(DfmProcess.CNC_MILLING))
    with pytest.raises(RefusalError, match="pull_direction"):
        screen_dfm(_l_block(), default_profile(DfmProcess.INJECTION_MOLDING))
    with pytest.raises(ValueError, match="build_direction"):
        screen_dfm(_l_block(), default_profile(DfmProcess.ADDITIVE),
                     build_direction=(0, 0, float("nan")))  # fmt: skip


def test_an_override_names_its_source_and_its_rule():
    profile = default_profile(DfmProcess.CNC_MILLING)
    with pytest.raises(RefusalError, match="source"):
        profile.override("internal_radius_min", 2.0, source=" ")
    with pytest.raises(RefusalError, match="no rule 'draft_min'"):
        profile.override("draft_min", 2.0, source="shop")
    assert all(t.practice_default for t in profile.thresholds)


def test_the_docs_page_states_the_defaults_the_code_bundles():
    page = (Path(__file__).resolve().parents[1] / "docs" / "dfm-rules.md").read_text()
    for process in DfmProcess:
        for t in default_profile(process).thresholds:
            unit = "°" if t.unit == "degree" else (" mm" if t.unit == "mm" else "")
            assert f"| `{t.rule}` |" in page and f"| {t.value:g}{unit} |" in page, t.rule


def test_die_casting_reads_draft_and_wall_uniformity():
    enclosure = _part("enclosure")  # wall 3, floor 3, thickness not declared
    profile = default_profile(DfmProcess.DIE_CASTING)
    (draft, walls) = screen_dfm(enclosure, profile, pull_direction=(0, 0, 1))
    assert draft.status is CheckStatus.FAIL
    assert walls.status is CheckStatus.PASS and walls.comparison.measured.magnitude == 1.0
    uneven = dataclasses.replace(enclosure, dimensions_mm={**enclosure.dimensions_mm,
                                                           "wall": 2.0, "floor": 5.0})  # fmt: skip
    (_, walls) = screen_dfm(uneven, profile, pull_direction=(0, 0, 1))
    assert walls.status is CheckStatus.FAIL
    assert walls.comparison.measured.magnitude == pytest.approx(2.5)  # 5/2


def test_a_short_flange_against_the_brake():
    bracket = _part("sheet_metal_bracket")  # flanges 30, 50, 25 at t = 2: 15, 25, 12.5
    profile = default_profile(DfmProcess.SHEET_METAL)
    flange = screen_dfm(bracket, profile)[-1]
    assert flange.status is CheckStatus.PASS
    assert flange.comparison.measured.magnitude == pytest.approx(12.5)
    deep_die = profile.override("flange_length_min", 15.0, source="shop: 30 mm V-die")
    flange = screen_dfm(bracket, deep_die)[-1]
    assert flange.status is CheckStatus.FAIL and "flange_c 25 mm" in flange.detail
