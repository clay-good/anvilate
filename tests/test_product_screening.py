"""Product screening, worked by hand.

A 200 × 100 × 10 base (2 kg, centred on the origin) carries a 40 mm block (0.5 kg) seated
at its front-left corner, centred at (−80, −30, 25). The pair's centre of mass is
(0.5·(−80, −30, 25)) / 2.5 = (−16, −6, 5). About it, Izz is the base's
2·(200² + 100²)/12 + 2·(16² + 6²) = 8,917.33 and the block's 0.5·(40² + 40²)/12 +
0.5·(64² + 24²) = 2,469.33: 11,386.67 kg·mm².
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from anvilate._models import parse_yaml  # noqa: E402
from anvilate.product import parse_product  # noqa: E402
from anvilate.product_screening import product_screening  # noqa: E402
from anvilate.scorecard import CheckStatus, Scorecard  # noqa: E402
from test_interfaces import _hinge  # noqa: E402
from test_product_cards import _box, _definition, _seat  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]


def _named(report, name: str):
    (entry,) = [e for e in report.entries if e.name == name]
    return entry


def _q(v: float, unit: str) -> dict:
    return {"magnitude": v, "unit": unit}


def _cart(screening: dict | None = None, second_block: bool = False) -> dict:
    definitions = [_definition("base", placeholder=_box(200, 100, 10, 2.0)),
                   _definition("block", placeholder=_box(40, 40, 40, 0.5))]  # fmt: skip
    instances = [{"name": "base", "item": "base"}, {"name": "block", "item": "block"}]
    mates = _seat("block", "base")
    if second_block:
        instances.append({"name": "other", "item": "block"})
        mates += [m | {"id": f"other-{m['id']}", "place": {**m["place"], "part": "other"}}
                  for m in _seat("block", "base")]  # fmt: skip
        for mate in mates[-3:]:
            if mate["place"]["face"] == "left":
                mate["place"]["face"] = mate["on"]["face"] = "right"
    document = {"name": "cart", "definitions": definitions, "instances": instances,
                "ground": "base", "mates": mates}  # fmt: skip
    if screening is not None:
        document["screening"] = screening
    return document


def test_mass_centre_of_mass_and_inertia_roll_up_by_hand():
    report = product_screening(parse_product(_cart()))
    (top,) = [n for n in report.nodes if n.path == "cart"]
    assert top.mass_kg == pytest.approx(2.5)
    assert top.center_of_mass_mm == pytest.approx((-16, -6, 5))
    assert top.inertia_kg_mm2[2] == pytest.approx(11386.667, rel=1e-5)
    assert top.provisional == ("cart/base", "cart/block")
    assert {c.path: (c.basis, c.maturity) for c in report.contributions} == {
        "cart/base": ("placeholder", "estimated"),
        "cart/block": ("placeholder", "estimated"),
    }


def test_growth_by_maturity_and_a_mass_limit_on_the_predicted_mass():
    plate = parse_yaml((_ROOT / "examples" / "parts" / "mounting_plate.spec.yaml").read_text())
    document = _cart({"mass_growth": {"estimated": 0.15, "calculated": 0.05,
                                      "source": "program mass-growth policy"},
                      "max_mass": {"value": _q(4.0, "kg"), "source": "lift limit"}})  # fmt: skip
    document["definitions"][0]["placeholder"]["mass"] = _q(2.4, "kg")  # the gearbox estimate
    document["definitions"][1] = _definition("block", spec=plate)
    report = product_screening(parse_product(document))
    lines = {line.maturity: line for line in report.rollup.lines}
    plate_kg = lines["calculated"].basic_kg
    assert lines["estimated"].basic_kg == pytest.approx(2.4)
    assert lines["estimated"].growth_kg == pytest.approx(0.36)
    assert lines["calculated"].growth_kg == pytest.approx(0.05 * plate_kg)
    assert report.rollup.predicted_kg == pytest.approx(2.4 * 1.15 + plate_kg * 1.05)
    entry = _named(report, "product mass")
    assert entry.status is CheckStatus.PASS and "predicted" in entry.detail
    assert "provisional on cart/base" in entry.detail
    # The same figure through the budget mechanism: each body a term, growth ledgered.
    budget = report.mass_budget
    assert budget.total == pytest.approx(report.rollup.predicted_kg)
    assert budget.governing == ("cart/base",) and "governing: cart/base" in entry.detail
    assert {m.authority for m in budget.margins} == {"program mass-growth policy"}
    assert entry.comparison.measured.magnitude == pytest.approx(budget.total)
    assert entry.reference == "lift limit"


def test_a_mass_over_its_limit_fails_with_the_body_that_governs_it():
    document = _cart({"max_mass": {"value": _q(2.2, "kg"), "source": "lift limit"}})
    report = product_screening(parse_product(document))
    entry = _named(report, "product mass")
    assert entry.status is CheckStatus.FAIL
    assert report.mass_budget.total == pytest.approx(2.5)
    assert report.mass_budget.governing == ("cart/base",)
    rooms = {c.name: c.headroom for c in report.mass_budget.contributors}
    assert rooms == {"cart/base": None, "cart/block": None}  # a spent budget has no headroom
    roomy = _cart({"max_mass": {"value": _q(3.0, "kg"), "source": "lift limit"}})
    rooms = {
        c.name: c.headroom for c in product_screening(parse_product(roomy)).mass_budget.contributors
    }
    assert rooms == pytest.approx({"cart/base": 2.5, "cart/block": 1.0})  # fmt: skip


def test_the_centre_of_mass_height_against_its_limit():
    column = {"name": "column",
              "definitions": [_definition("body", placeholder=_box(100, 100, 200, 1.0))],
              "instances": [{"name": "body", "item": "body"}], "ground": "body"}  # fmt: skip
    for allowed, status in ((120, CheckStatus.PASS), (80, CheckStatus.FAIL)):
        column["screening"] = {"max_cg_height": {"value": _q(allowed, "mm"),
                                                 "source": "transport spec"}}  # fmt: skip
        entry = _named(product_screening(parse_product(column)), "centre-of-mass height")
        assert entry.status is status
        assert "is 100 mm above the lowest point" in entry.detail
        assert entry.comparison.measured.magnitude == pytest.approx(100)


def test_a_centre_of_mass_height_limit_is_a_length():
    column = {"name": "column",
              "definitions": [_definition("body", placeholder=_box(100, 100, 200, 1.0))],
              "instances": [{"name": "body", "item": "body"}], "ground": "body",
              "screening": {"max_cg_height": {"value": _q(5, "kg"), "source": "x"}}}  # fmt: skip
    with pytest.raises(ValueError, match="max_cg_height"):
        parse_product(column)


def test_the_tilt_at_which_the_centre_of_mass_leaves_the_footprint():
    column = {"name": "column",
              "definitions": [_definition("body", placeholder=_box(100, 100, 200, 1.0))],
              "instances": [{"name": "body", "item": "body"}], "ground": "body"}  # fmt: skip
    expected = math.degrees(math.atan2(50, 100))  # 26.57 degrees
    for required, status in ((20, CheckStatus.PASS), (30, CheckStatus.FAIL)):
        column["screening"] = {"min_tilt": {"value": _q(required, "degree"),
                                            "source": "transport spec"}}  # fmt: skip
        entry = _named(product_screening(parse_product(column)), "tip-over")
        assert entry.status is status
        assert f"leaves it at {expected:.3g} degrees" in entry.detail


def test_clearance_between_items_that_share_no_connection():
    document = _cart({"min_clearance": {"value": _q(150, "mm"), "source": "service access"}},
                     second_block=True)  # fmt: skip
    report = product_screening(parse_product(document))
    pair = {"cart/block", "cart/other"}
    (closest,) = [a for a in report.approaches if {a.first, a.second} == pair]
    assert closest.gap_mm == pytest.approx(120) and closest.at_mm[0] == pytest.approx(0)
    entry = _named(report, "clearance")
    assert entry.status is CheckStatus.FAIL
    assert "cart/block and cart/other come within 120 mm" in entry.detail


def test_mobility_counts_a_hinge_and_distrusts_three_coaxial_ones():
    swing = {"kind": "revolute", "range": [_q(0, "degree"), _q(90, "degree")]}
    hinge = product_screening(parse_product(_hinge(swing))).mobility
    assert (hinge.count, hinge.bodies) == (1, 2) and hinge.caveats == ()
    lid = _hinge(swing)
    base, arm = lid["definitions"][0]["placeholder"], lid["definitions"][1]["placeholder"]
    for k in (2, 3):
        base["interfaces"].append({**copy.deepcopy(base["interfaces"][0]), "name": f"pivot{k}"})
        arm["interfaces"].append({**copy.deepcopy(arm["interfaces"][0]), "name": f"pivot{k}"})
        lid["connections"].append({"on": f"base.pivot{k}", "place": f"arm.pivot{k}",
                                   "joint": swing})  # fmt: skip
    mobility = product_screening(parse_product(lid)).mobility
    assert mobility.count == 6 * (2 - 1 - 3) + 3 == -9
    assert any("does not show the product cannot move" in c for c in mobility.caveats)
    assert sum("coincident axes" in c for c in mobility.caveats) == 3


def test_a_body_with_no_mass_leaves_its_parents_unweighed_and_named():
    plate = parse_yaml((_ROOT / "examples" / "parts" / "mounting_plate.spec.yaml").read_text())
    plate["material"] = {"ref": "NOT-IN-THE-DATABASE"}
    document = _cart({"max_mass": {"value": _q(10, "kg"), "source": "lift limit"}})
    document["definitions"][1] = _definition("block", spec=plate)
    report = product_screening(parse_product(document))
    (top,) = [n for n in report.nodes if n.path == "cart"]
    assert top.mass_kg is None and top.missing == ("cart/block",)
    entry = _named(report, "product mass")
    assert (
        entry.status is CheckStatus.NOT_EVALUATED and "cart/block carries no mass" in entry.detail
    )


def test_the_docs_page_states_the_basis_and_maturity_the_code_assigns():
    import re

    page = (_ROOT / "docs" / "product-screening.md").read_text()
    rows = re.findall(r"^\| a (catalog part|purchased component|placeholder) \| .+ \| (\w+) \|$",
                      page, re.M)  # fmt: skip
    assert dict(rows) == {"catalog part": "calculated", "purchased component": "measured",
                          "placeholder": "estimated"}  # fmt: skip


def _caster() -> dict:
    from anvilate.units import Quantity
    from test_components import _record

    record = _record("caster", {"load_rating": _q(400, "N")})
    sizes = tuple(Quantity(magnitude=v, unit="mm") for v in (60, 60, 100))
    record = record.model_copy(
        update={"envelope": sizes, "mass": Quantity(magnitude=0.6, unit="kg")}
    )
    identity = {"description": "caster", "source": "buy", "part_number": "C-1"}
    return {"id": "caster", "identity": identity, "component": record.model_dump(mode="json")}


def _under(name: str, faces: tuple[str, str]) -> list[dict]:
    return [{"id": f"{name}-under", "kind": "face_to_face", "place": {"part": name, "face": "top"},
             "on": {"part": "frame", "face": "bottom"}}] + [
        {"id": f"{name}-{f}", "kind": "edge_flush", "place": {"part": name, "face": f},
         "on": {"part": "frame", "face": f}} for f in faces]  # fmt: skip


def _carted(corners: tuple[tuple[str, str], ...], plate_at: tuple[str, str], split=None) -> dict:
    """A 600 × 400 × 40 frame (12 kg) on casters at the named corners, with a 200 × 200 × 10
    plate (1 kg) carrying a 50 kg payload seated at the frame's ``plate_at`` corner."""
    definitions = [_definition("frame", placeholder=_box(600, 400, 40, 12.0)), _caster(),
                   _definition("plate", placeholder=_box(200, 200, 10, 1.0))]  # fmt: skip
    instances = [{"name": "frame", "item": "frame"}, {"name": "plate", "item": "plate"}]
    sit = {"id": "plate-sit", "kind": "face_to_face", "place": {"part": "plate", "face": "bottom"}}
    mates = [{**sit, "on": {"part": "frame", "face": "top"}}] + [
        {"id": f"plate-{f}", "kind": "edge_flush", "place": {"part": "plate", "face": f},
         "on": {"part": "frame", "face": f}} for f in plate_at]  # fmt: skip
    for k, faces in enumerate(corners, start=1):
        instances.append({"name": f"caster{k}", "item": "caster"})
        mates += _under(f"caster{k}", faces)
    screening = {"loads": [{"item": "plate", "mass": _q(50, "kg"), "source": "payload spec"}]}
    if split is not None:
        screening["splits"] = [split]
    return {"name": "cart", "definitions": definitions, "instances": instances,
            "ground": "frame", "mates": mates, "screening": screening}  # fmt: skip


_THREE = (("left", "front"), ("right", "front"), ("right", "back"))


def test_a_payload_reaches_the_casters_through_a_determinate_path():
    report = product_screening(parse_product(_carted(_THREE, ("right", "back"))))
    steps = {s.body: s for s in report.load_path}
    g = 9.80665
    assert steps["cart/plate"].carries_n == pytest.approx(51 * g)
    frame = steps["cart/frame"]
    assert frame.carries_n == pytest.approx(63 * g)
    # resultant at (161.90, 80.95) mm over casters at (−270, −170), (270, −170), (270, 170)
    shares = {r.support: r.force_n / frame.carries_n for r in frame.reactions}
    assert shares["cart/caster3"] == pytest.approx((1 + (51 * 100 / 63) / 170) / 2)
    assert shares["cart/caster1"] == pytest.approx(1 - (1 + (51 * 200 / 63) / 270) / 2)
    assert sum(shares.values()) == pytest.approx(1)
    rated = {e.name: e for e in report.entries if e.name.endswith("caster load")}
    assert rated["cart/caster3 caster load"].status is CheckStatus.FAIL  # 456 N + its own 5.9 N
    assert rated["cart/caster1 caster load"].status is CheckStatus.PASS
    assert "reads 'load path cart/caster3'" in rated["cart/caster3 caster load"].detail


def test_a_vertical_acceleration_scales_weights_and_masses_and_not_forces():
    g = 9.80665
    still = product_screening(parse_product(_carted(_THREE, ("right", "back"))))
    document = _carted(_THREE, ("right", "back"))
    document["screening"]["vertical_acceleration"] = {"value": _q(2, "g0"),
                                                      "source": "transport shock"}  # fmt: skip
    document["screening"]["loads"].append({"item": "plate", "force": _q(100, "N"),
                                           "source": "hand on the plate"})  # fmt: skip
    shaken = product_screening(parse_product(document))
    frame = {s.body: s for s in shaken.load_path}["cart/frame"]
    assert frame.carries_n == pytest.approx(63 * 2 * g + 100)
    before = {r.support: r.force_n for r in {s.body: s for s in still.load_path}["cart/frame"]
              .reactions}  # fmt: skip
    assert sum(r.force_n for r in frame.reactions) == pytest.approx(sum(before.values()) * 2 + 100)
    assert "weights at 2 g (transport shock)" in _named(shaken, "load path cart/frame").detail
    caster = {s.body: s for s in shaken.load_path}["cart/caster1"]
    assert caster.carries_n == pytest.approx(
        next(r.force_n for r in frame.reactions if r.support == "cart/caster1") + 0.6 * 2 * g
    )
    with pytest.raises(ValueError, match="vertical_acceleration"):
        document["screening"]["vertical_acceleration"]["value"] = _q(2, "N")
        parse_product(document)


def test_a_linear_guide_on_the_path_is_checked_against_the_share_it_carries():
    """The same three supports as guide carriages rated at 400 N: each reads its load-path
    share as the guide's load, and the verdicts are the casters' verdicts."""
    from test_components import _record

    document = _carted(_THREE, ("right", "back"))
    ratings = {"stroke": _q(300, "mm"), "dynamic_load_rating": _q(400, "N")}
    envelope = [_q(60, "mm"), _q(60, "mm"), _q(100, "mm")]
    guide = _record("linear_guide", ratings, envelope=envelope, mass=_q(0.6, "kg"))
    document["definitions"][1]["component"] = guide.model_dump(mode="json")
    report = product_screening(parse_product(document))
    rated = {e.name: e for e in report.entries if e.name.endswith("guide load")}
    assert rated["cart/caster3 guide load"].status is CheckStatus.FAIL
    assert rated["cart/caster1 guide load"].status is CheckStatus.PASS
    assert "reads 'load path cart/caster3'" in rated["cart/caster3 guide load"].detail
    assert not any(e.name.endswith("caster load") for e in report.entries)


def test_a_load_outside_the_supports_lifts_one_off():
    report = product_screening(parse_product(_carted(_THREE, ("left", "front"))))
    frame = _named(report, "load path cart/frame")
    assert frame.status is CheckStatus.FAIL and "cart/caster2 would have to pull" in frame.detail


def test_four_casters_are_indeterminate_until_a_split_is_declared():
    four = _THREE + (("left", "back"),)
    report = product_screening(parse_product(_carted(four, ("right", "back"))))
    frame = _named(report, "load path cart/frame")
    assert frame.status is CheckStatus.NOT_EVALUATED
    assert "indeterminate, with 1 redundant, and no share is guessed" in frame.detail
    rated = _named(report, "cart/caster1 caster load")
    assert rated.status is CheckStatus.NOT_EVALUATED and "not evaluated" in rated.detail
    split = {"body": "cart/frame", "basis": "measured at the four wheels, run 3",
             "shares": {f"cart/caster{k}": 0.25 for k in range(1, 5)}}  # fmt: skip
    declared = product_screening(parse_product(_carted(four, ("right", "back"), split)))
    frame = _named(declared, "load path cart/frame")
    assert frame.status is CheckStatus.PASS and "divided as declared" in frame.detail
    assert _named(declared, "cart/caster1 caster load").status is CheckStatus.PASS


def _plate(material: str) -> dict:
    """A 640 × 80 mounting plate with one hole near each end, 600 mm apart."""
    plate = parse_yaml((_ROOT / "examples" / "parts" / "mounting_plate.spec.yaml").read_text())
    plate["material"] = {"ref": material}
    params = plate["element_params"]
    params["width"] = _q(640, "mm")
    params["holes"] = [{"tag": tag, "x": _q(x, "mm"), "y": _q(0, "mm"), "diameter": _q(6.6, "mm")}
                       for tag, x in (("end1", -300), ("end2", 300))]  # fmt: skip
    params["hole_patterns"] = []
    params["slots"] = []
    return plate


def _bolted(slip: float | None, coefficients: bool = True) -> dict:
    document = {
        "name": "deck",
        "definitions": [_definition("frame", spec=_plate("ASTM-A36")),
                        _definition("plate", spec=_plate("AA-6061-T6"))],
        "instances": [{"name": "frame", "item": "frame"}, {"name": "plate", "item": "plate"}],
        "ground": "frame",
        "mates": [{"id": "bolted", "kind": "hole_pattern",
                   "place": {"part": "plate", "face": "bottom", "holes": ["end1", "end2"]},
                   "on": {"part": "frame", "face": "top", "holes": ["end1", "end2"]}}],
    }  # fmt: skip
    if slip is not None:
        thermal = {"range": _q(60, "K"), "slip": _q(slip, "mm"), "source": "service envelope",
                   "coefficients": [
                       {"material": "ASTM-A36", "coefficient": _q(11.7e-6, "1/K"),
                        "source": "test fixture value"},
                       {"material": "AA-6061-T6", "coefficient": _q(23.4e-6, "1/K"),
                        "source": "test fixture value"}][: 2 if coefficients else 1]}  # fmt: skip
        document["screening"] = {"thermal": thermal}
    return document


@pytest.mark.parametrize(("slip", "status"), [(0.5, CheckStatus.PASS), (0.3, CheckStatus.FAIL)])
def test_an_aluminium_plate_on_a_steel_frame_grows_against_its_slip(slip, status):
    # (23.4 − 11.7)e−6 /K × 60 K × 600 mm between the bolts = 0.4212 mm
    entry = _named(product_screening(parse_product(_bolted(slip))), "thermal frame ~ plate")
    assert entry.status is status
    assert entry.detail.startswith("0.421 mm of differential growth over 600 mm between the "
                                   "outermost of 2 mated holes and 60 K")  # fmt: skip
    assert "ASTM-A36 11.7e-6/K (test fixture value)" in entry.detail


def test_a_dissimilar_joint_with_no_range_or_coefficient_is_not_evaluated():
    bare = _named(product_screening(parse_product(_bolted(None))), "thermal frame ~ plate")
    assert bare.status is CheckStatus.NOT_EVALUATED and "no temperature range" in bare.detail
    half = _named(product_screening(parse_product(_bolted(0.5, coefficients=False))),
                  "thermal frame ~ plate")  # fmt: skip
    assert half.status is CheckStatus.NOT_EVALUATED and "AA-6061-T6" in half.detail


def test_assembly_economy_counts_parts_and_bought_items_and_offers_merges():
    report = product_screening(parse_product(_carted(_THREE, ("right", "back"))))
    assert report.economy.parts == 5
    assert report.economy.purchased == (("Acme caster-1", 3),)
    same = _bolted(None)
    same["definitions"][1] = _definition("plate", spec=_plate("ASTM-A36"))
    merged = product_screening(parse_product(same)).economy
    (candidate,) = merged.merge_candidates
    assert candidate == ("frame + plate: one material (ASTM-A36), joined without relative "
                         "motion, neither separated for service")  # fmt: skip
    same["screening"] = {"serviced": ["plate"]}
    assert product_screening(parse_product(same)).economy.merge_candidates == ()


def _stacked(required: tuple[float, float], samples: int | None = None) -> dict:
    """A 6 mm plate (±0.05 declared) seated on a 15 mm rail that declares no tolerance."""
    plate = parse_yaml((_ROOT / "examples" / "parts" / "mounting_plate.spec.yaml").read_text())
    band = {"type": "symmetric", "plus_minus": _q(0.05, "mm")}
    plate["dimensions"] = [{"tag": "thickness", "nominal": _q(6, "mm"), "tolerance": band}]
    chain = {"name": "carriage height", "required_min": _q(required[0], "mm"),
             "required_max": _q(required[1], "mm"),
             "links": [{"item": "rail", "dimension": "height", "nominal": _q(15, "mm")},
                       {"connection": "plate-sit", "allowance": _q(0.02, "mm"),
                        "source": "seating flatness, rail datasheet"},
                       {"item": "plate", "dimension": "thickness"}]}  # fmt: skip
    if samples is not None:
        chain |= {"samples": samples, "seed": 7}
    return {
        "name": "axis",
        "definitions": [_definition("rail", placeholder=_box(300, 20, 15, 1.0)),
                        _definition("plate", spec=plate)],
        "instances": [{"name": "rail", "item": "rail"}, {"name": "plate", "item": "plate"}],
        "ground": "rail",
        "mates": [{"id": "plate-sit", "kind": "face_to_face",
                   "place": {"part": "plate", "face": "bottom"},
                   "on": {"part": "rail", "face": "top"}}] + [
            {"id": f"plate-{f}", "kind": "edge_flush", "place": {"part": "plate", "face": f},
             "on": {"part": "rail", "face": f}} for f in ("left", "front")],
        "screening": {"chains": [chain]},
    }  # fmt: skip


def test_a_chain_through_a_product_reports_worst_case_rss_and_the_governing_link():
    from anvilate.tolerance import general_tolerance
    from anvilate.units import Quantity

    rail = general_tolerance(Quantity(magnitude=15, unit="mm")).deviation.to("mm").magnitude
    worst = 0.05 + rail + 0.02
    rss = math.sqrt(0.05**2 + rail**2 + 0.02**2)
    passing = _named(product_screening(parse_product(_stacked((20.5, 21.5), samples=2000))),
                     "stack-up: carriage height")  # fmt: skip
    assert passing.status is CheckStatus.PASS
    assert f"+{21 - worst:.3f} to +{21 + worst:.3f} mm" in passing.detail
    assert f"RSS +{21 - rss:.3f} to +{21 + rss:.3f} mm, which fits" in passing.detail
    assert "each link's share of the worst case: rail.height " in passing.detail
    assert "governed by rail.height" in passing.detail
    assert f"rail.height takes the general tolerance ±{rail:g} mm" in passing.detail
    assert "Monte Carlo over 2000 samples, seed 7" in passing.detail
    tight = _named(product_screening(parse_product(_stacked((20.9, 21.1)))),
                   "stack-up: carriage height")  # fmt: skip
    assert tight.status is CheckStatus.FAIL
    assert tight.reference is None and tight.detail.endswith("; the band states no source")


def test_a_chains_band_cites_its_source():
    document = _stacked((20.5, 21.5))
    document["screening"]["chains"][0]["source"] = "carriage drawing 300-4, note 2"
    entry = _named(product_screening(parse_product(document)), "stack-up: carriage height")
    assert entry.reference == "carriage drawing 300-4, note 2"
    assert entry.detail.endswith("; the band is from carriage drawing 300-4, note 2")


def test_a_chain_naming_what_the_product_lacks_is_refused():
    from anvilate.product import ProductError

    document = _stacked((20.5, 21.5))
    document["screening"]["chains"][0]["links"][1]["connection"] = "glued"
    with pytest.raises(ProductError, match="names the connection 'glued'"):
        product_screening(parse_product(document))
    document = _stacked((20.5, 21.5))
    del document["screening"]["chains"][0]["links"][0]["nominal"]
    with pytest.raises(ProductError, match="no nominal to take the general tolerance on"):
        product_screening(parse_product(document))


def test_each_check_against_a_declared_limit_cites_that_limits_source():
    """docs/product-screening.md's Cites column: the entry's reference is the source the
    document declared with the limit, so a reader of the card sees what it was held to."""
    limits = {"max_mass": ("lift limit", "kg", 10), "max_cg_height": ("transport", "mm", 500),
              "min_tilt": ("tilt table", "degree", 5),
              "min_clearance": ("service access", "mm", 1)}  # fmt: skip
    screening = {key: {"value": _q(v, unit), "source": source}
                 for key, (source, unit, v) in limits.items()}  # fmt: skip
    report = product_screening(parse_product(_cart(screening, second_block=True)))
    cited = {e.name: e.reference for e in report.entries}
    assert cited["product mass"] == "lift limit"
    assert cited["centre-of-mass height"] == "transport"
    assert cited["tip-over"] == "tilt table"
    assert cited["clearance"] == "service access"
    thermal = _named(product_screening(parse_product(_bolted(0.5))), "thermal frame ~ plate")
    assert thermal.reference == "service envelope"


@pytest.mark.parametrize(
    ("field", "unit"),
    [("max_mass", "kg"), ("max_cg_height", "mm"), ("min_tilt", "degree"),
     ("min_clearance", "mm"), ("vertical_acceleration", "g0")],
)  # fmt: skip
@pytest.mark.parametrize("value", [float("inf"), float("nan"), -1.0])
def test_a_screening_limit_is_finite_and_not_negative(field, unit, value):
    """An infinite clearance passed every pair, an infinite mass limit crashed inside its
    budget, and an infinite acceleration carried infinite loads: each is refused when the
    document is read, naming the field."""
    from anvilate.refusal import RefusalError

    document = _cart({field: {"value": _q(value, unit), "source": "x"}})
    with pytest.raises((RefusalError, ValueError), match=f"screening.{field}|{field}"):
        parse_product(document)


def test_every_number_a_screening_declares_is_finite():
    """The nested declarations too: an infinite slip passed every connection, and an
    infinite load or chain nominal reached the arithmetic. Each opts into the finite rule
    every requirement model follows (`states_requirements`)."""
    inf = float("inf")
    alpha = {"material": "A", "coefficient": _q(1e-5, "1/K"), "source": "x"}
    thermal = {"range": _q(60, "K"), "slip": _q(0.5, "mm"), "source": "x",
               "coefficients": [alpha]}  # fmt: skip
    link = {"item": "base", "dimension": "h", "nominal": _q(1, "mm")}
    chain = {"name": "c", "required_min": _q(0, "mm"), "required_max": _q(1, "mm"), "links": [link]}
    cases = [
        {"thermal": {**thermal, "range": _q(inf, "K")}},
        {"thermal": {**thermal, "slip": _q(inf, "mm")}},
        {"thermal": {**thermal, "coefficients": [{**thermal["coefficients"][0],
                                                  "coefficient": _q(inf, "1/K")}]}},
        {"loads": [{"item": "base", "force": _q(inf, "N"), "source": "x"}]},
        {"loads": [{"item": "base", "mass": _q(inf, "kg"), "source": "x"}]},
        {"chains": [{**chain, "required_max": _q(inf, "mm")}]},
        {"chains": [{**chain, "links": [{**link, "nominal": _q(inf, "mm")}]}]},
    ]  # fmt: skip
    for screening in cases:
        with pytest.raises(ValueError, match="not a number a document can state"):
            parse_product(_cart(screening))


# --- A split that is a solve, not a guess ----------------------------------------------
#
# The load path refuses to divide a load among more supports than determine it, and that
# refusal is right when nothing is declared. It is also where the work stops for every
# real frame: four legs under a skid is four supports, and four is more than three. A
# frame declared over the product's connections turns the guess into a solve.


def _skid_frame(loads):
    """A four-legged skid: two beams and two cross members on four legs."""
    from anvilate.frame import (
        Frame,
        FrameMaterial,
        FrameMember,
        FrameNode,
        FrameSection,
        Freedom,
        Support,
    )
    from anvilate.units import Quantity

    q = Quantity.parse
    section = FrameSection(
        name="s",
        area=q("5e-3 m**2"),
        second_moment_y=q("10e-6 m**4"),
        second_moment_z=q("100e-6 m**4"),
        torsion_constant=q("1e-6 m**4"),
        source="a declared section, for this case",
    )
    material = FrameMaterial(
        name="steel",
        elastic_modulus=q("200 GPa"),
        shear_modulus=q("77 GPa"),
        source="a declared elastic steel, for this case",
    )

    def node(name, x, y, z):
        return FrameNode(name=name, x=q(f"{x} mm"), y=q(f"{y} mm"), z=q(f"{z} mm"))

    def member(name, start, end):
        return FrameMember(name=name, start=start, end=end, section=section, material=material)

    nodes = (
        node("a", 0, 0, 0),
        node("b", 2000, 0, 0),
        node("c", 0, 1000, 0),
        node("d", 2000, 1000, 0),
        node("fa", 0, 0, -500),
        node("fb", 2000, 0, -500),
        node("fc", 0, 1000, -500),
        node("fd", 2000, 1000, -500),
    )
    members = (
        member("beam1", "a", "b"),
        member("beam2", "c", "d"),
        member("cross1", "a", "c"),
        member("cross2", "b", "d"),
        member("leg_a", "fa", "a"),
        member("leg_b", "fb", "b"),
        member("leg_c", "fc", "c"),
        member("leg_d", "fd", "d"),
    )
    return Frame(
        name="skid",
        nodes=nodes,
        members=members,
        supports=tuple(
            Support(node=name, restrained=tuple(Freedom)) for name in ("fa", "fb", "fc", "fd")
        ),
        node_loads=loads,
    )


def _legs() -> dict[str, str]:
    return {f"skid/leg_{k}": f"f{k}" for k in "abcd"}


def test_a_four_legged_skid_divides_its_load_by_the_solve():
    """Four equal corner loads divide evenly, which is the case statics could have had."""
    from anvilate.frame import NodeLoad, solve_frame
    from anvilate.product_screening import frame_split
    from anvilate.units import Quantity

    q = Quantity.parse
    even = tuple(NodeLoad(node=n, fz=q("-10 kN")) for n in "abcd")
    split = frame_split(body="skid/deck", solution=solve_frame(_skid_frame(even)), supports=_legs())
    assert set(split.shares) == set(_legs())
    for share in split.shares.values():
        assert share == pytest.approx(0.25)
    assert sum(split.shares.values()) == pytest.approx(1.0)
    assert "direct stiffness" in split.basis and "out of balance" in split.basis


def test_a_biased_load_divides_unevenly_which_is_the_point_of_solving_it():
    """The figure statics on four supports cannot give.

    A load biased to one corner puts 40% of it into that leg and a fifth into each of the
    others. Nothing short of a solve distinguishes that from the even quarter a reader
    would otherwise assume, and the leg is sized on the difference.
    """
    from anvilate.frame import NodeLoad, solve_frame
    from anvilate.product_screening import frame_split
    from anvilate.units import Quantity

    q = Quantity.parse
    biased = (
        NodeLoad(node="a", fz=q("-16 kN")),
        NodeLoad(node="b", fz=q("-8 kN")),
        NodeLoad(node="c", fz=q("-8 kN")),
        NodeLoad(node="d", fz=q("-8 kN")),
    )
    split = frame_split(
        body="skid/deck", solution=solve_frame(_skid_frame(biased)), supports=_legs()
    )
    assert split.shares["skid/leg_a"] == pytest.approx(0.398, abs=0.002)
    assert split.shares["skid/leg_b"] == pytest.approx(0.200, abs=0.002)
    assert sum(split.shares.values()) == pytest.approx(1.0)


def test_a_leg_the_solve_puts_in_uplift_is_refused_not_given_a_share():
    """A share of a load a support does not carry reads as a load path it is not on.

    40 kN on one corner of this skid lifts the diagonally opposite leg: the solve says
    −11 N there. A normalised share would quietly turn that into a positive fraction.
    """
    from anvilate.frame import NodeLoad, solve_frame
    from anvilate.product_screening import frame_split
    from anvilate.units import Quantity

    solution = solve_frame(_skid_frame((NodeLoad(node="a", fz=Quantity.parse("-40 kN")),)))
    assert solution.reaction("fd").fz < 0
    with pytest.raises(ValueError, match="being pulled or carries nothing"):
        frame_split(body="skid/deck", solution=solution, supports=_legs())


def test_a_split_names_the_frame_node_it_could_not_find():
    from anvilate.frame import NodeLoad, solve_frame
    from anvilate.product_screening import frame_split
    from anvilate.units import Quantity

    solution = solve_frame(
        _skid_frame(tuple(NodeLoad(node=n, fz=Quantity.parse("-10 kN")) for n in "abcd"))
    )
    with pytest.raises(ValueError, match="which is not a supported node"):
        frame_split(
            body="skid/deck",
            solution=solution,
            supports={"skid/leg_a": "fa", "skid/leg_b": "nowhere"},
        )
    # And a split of one support is the load path's own arithmetic, not a declaration.
    with pytest.raises(ValueError, match="a split divides a load among supports"):
        frame_split(body="skid/deck", solution=solution, supports={"skid/leg_a": "fa"})


def test_one_placeholder_named_as_a_string_is_refused_not_spelled_out():
    """A string iterates over its characters, so one name would read as five placeholders."""
    from anvilate.frame import NodeLoad, solve_frame
    from anvilate.product_screening import frame_split
    from anvilate.units import Quantity

    solution = solve_frame(
        _skid_frame(tuple(NodeLoad(node=n, fz=Quantity.parse("-10 kN")) for n in "abcd"))
    )
    with pytest.raises(ValueError, match="placeholders is a sequence of str"):
        frame_split(body="skid/deck", solution=solution, supports=_legs(), placeholders="leg_d")


def test_a_placeholders_assumed_stiffness_is_named_in_the_basis():
    """The basis is what the load path prints, so an assumption has to be in it."""
    from anvilate.frame import NodeLoad, solve_frame
    from anvilate.product_screening import PLACEHOLDER_STIFFNESS_NOTE, frame_split
    from anvilate.units import Quantity

    solution = solve_frame(
        _skid_frame(tuple(NodeLoad(node=n, fz=Quantity.parse("-10 kN")) for n in "abcd"))
    )
    plain = frame_split(body="skid/deck", solution=solution, supports=_legs())
    assumed = frame_split(
        body="skid/deck",
        solution=solution,
        supports=_legs(),
        placeholders=("leg_c", "leg_d"),
    )
    assert PLACEHOLDER_STIFFNESS_NOTE.format(items="leg_c, leg_d") in assumed.basis
    assert "assumed stiffness" not in plain.basis


def test_a_declared_split_is_attributed_on_every_entry_below_it():
    """A number that rests on an assumption says so wherever it is read.

    The split's basis used to appear on the body it divided and nowhere else, so a reader
    following the load down to a caster met the assumption once, at the top, where it is
    easy to read as applying only there.
    """
    four = _THREE + (("left", "back"),)
    split = {
        "body": "cart/frame",
        "basis": "the frame 'cart' solved by first-order linear elastic direct stiffness",
        "shares": {f"cart/caster{k}": 0.25 for k in range(1, 5)},
    }
    report = product_screening(parse_product(_carted(four, ("right", "back"), split)))
    divided = _named(report, "load path cart/frame")
    assert divided.status is CheckStatus.PASS and "divided as declared" in divided.detail
    for k in range(1, 5):
        caster = _named(report, f"load path cart/caster{k}")
        assert "it carries a share assumed above it" in caster.detail
        assert "direct stiffness" in caster.detail
    # The plate is ABOVE the split, so it carries no assumption and says nothing.
    assert "share assumed above it" not in _named(report, "load path cart/plate").detail


def test_a_determinate_path_attributes_nothing_because_there_is_nothing_to_attribute():
    """The attack on the check above: a path with no declared split must stay silent."""
    report = product_screening(parse_product(_carted(_THREE, ("right", "back"))))
    for step in report.load_path:
        entry = _named(report, f"load path {step.body}")
        assert "share assumed above it" not in entry.detail


# --- A sideways acceleration, and the part that goes first ------------------------------
#
# A vertical acceleration scales every weight. A lateral one makes a horizontal force at
# each body's centre of mass, and the moment of it moves the point the vertical load acts
# at. That is how a product that stands up under gravity tips over on a truck.


def _shoved(g: float, direction=(1.0, 0.0)) -> dict:
    document = _carted(_THREE, ("right", "back"))
    if g:
        document["screening"]["lateral_acceleration"] = {
            "value": {"magnitude": g, "unit": "g0"},
            "direction": list(direction),
            "source": "transport shock, declared",
        }
    return document


def _statuses(g: float) -> dict[str, CheckStatus]:
    report = product_screening(parse_product(_shoved(g)))
    return {step.body: step.status for step in report.load_path}


def test_a_lateral_acceleration_moves_the_point_the_load_acts_at():
    still = {s.body: s for s in product_screening(parse_product(_shoved(0))).load_path}
    shoved = {s.body: s for s in product_screening(parse_product(_shoved(0.3))).load_path}
    assert still["cart/frame"].lateral_n == 0.0 and still["cart/frame"].shift_mm == 0.0
    # 63 kg at 0.3 g is 185 N sideways, and it moves the frame's load point outward.
    assert shoved["cart/frame"].lateral_n == pytest.approx(63 * 0.3 * 9.80665, rel=1e-3)
    assert shoved["cart/frame"].shift_mm > 0
    assert shoved["cart/frame"].at_mm[0] > still["cart/frame"].at_mm[0]
    # Along x only: the direction is declared and nothing moves across it.
    assert shoved["cart/frame"].at_mm[1] == pytest.approx(still["cart/frame"].at_mm[1])


def test_the_direction_is_the_declared_one_and_not_an_axis():
    across = {
        s.body: s for s in product_screening(parse_product(_shoved(0.3, (0.0, 1.0)))).load_path
    }
    still = {s.body: s for s in product_screening(parse_product(_shoved(0))).load_path}
    assert across["cart/frame"].at_mm[1] > still["cart/frame"].at_mm[1]
    assert across["cart/frame"].at_mm[0] == pytest.approx(still["cart/frame"].at_mm[0])


def test_the_caster_goes_over_ten_times_before_the_cart_does():
    """The finding: the slender part in the stack fails first, by an order of magnitude.

    A caster is 60 mm across and 100 mm tall. The sideways force arrives at its top and
    has the whole of that height as a lever, so its own load walks outside its own
    footprint at **0.30 g**. The cart on its three casters does not tip until **2.99 g**.
    A check on the product as a whole would have reported it standing up through ten times
    the acceleration that lays a wheel over.
    """
    assert all(status is CheckStatus.PASS for status in _statuses(0.0).values())
    assert all(status is CheckStatus.PASS for status in _statuses(0.29).values())
    at_three_tenths = _statuses(0.31)
    assert at_three_tenths["cart/caster3"] is CheckStatus.FAIL
    assert at_three_tenths["cart/frame"] is CheckStatus.PASS
    # And the frame itself holds out to very nearly three g.
    assert _statuses(2.9)["cart/frame"] is CheckStatus.PASS
    assert _statuses(3.1)["cart/frame"] is CheckStatus.FAIL


def test_the_sideways_force_is_named_on_the_entry_with_its_source():
    report = product_screening(parse_product(_shoved(0.3)))
    entry = _named(report, "load path cart/frame")
    assert "N sideways (transport shock, declared)" in entry.detail
    assert "moved that point" in entry.detail
    # A product with no lateral acceleration says nothing about one.
    quiet = _named(product_screening(parse_product(_shoved(0))), "load path cart/frame")
    assert "sideways" not in quiet.detail


def test_a_load_given_as_a_force_is_not_accelerated_sideways():
    """A mass has a sideways force; a force is a force, and no direction is invented."""
    as_mass = product_screening(parse_product(_shoved(0.5)))
    document = _shoved(0.5)
    document["screening"]["loads"] = [
        {"item": "plate", "force": _q(50 * 9.80665, "N"), "source": "payload spec"}
    ]
    as_force = product_screening(parse_product(document))
    by_mass = {s.body: s for s in as_mass.load_path}["cart/frame"]
    by_force = {s.body: s for s in as_force.load_path}["cart/frame"]
    assert by_mass.carries_n == pytest.approx(by_force.carries_n, rel=1e-6)
    assert by_mass.lateral_n > by_force.lateral_n


def test_a_lateral_acceleration_points_somewhere_and_is_finite():
    for bad, message in (
        ({"magnitude": 1.0, "unit": "g0"}, None),
        ({"magnitude": -1.0, "unit": "g0"}, "non-negative"),
        ({"magnitude": 1.0, "unit": "m"}, "acceleration"),
    ):
        document = _shoved(0)
        document["screening"]["lateral_acceleration"] = {
            "value": bad,
            "direction": [1.0, 0.0],
            "source": "declared",
        }
        if message is None:
            product_screening(parse_product(document))
            continue
        with pytest.raises(ValueError, match=message):
            parse_product(document)
    # A direction with no length is this model's own refusal; a non-finite one is caught
    # a layer up, by the base class that refuses any infinity in a document.
    for direction, says in (([0.0, 0.0], "has no length"), ([float("inf"), 0.0], "is inf")):
        document = _shoved(0)
        document["screening"]["lateral_acceleration"] = {
            "value": {"magnitude": 1.0, "unit": "g0"},
            "direction": direction,
            "source": "declared",
        }
        with pytest.raises(ValueError, match=says):
            parse_product(document)


# --- A declared drive train over the product's items (drive trains 1.1) ------------------

_LOSSLESS = "the reducer's efficiency, taken as 1.0 for this screening"


def _reducer_document(**train_overrides) -> dict:
    """Four instances — a base, two shafts and a gear on each — and a train over them."""
    definitions = [_definition("base", placeholder=_box(300, 120, 12, 5.4)),
                   _definition("shaft", placeholder=_box(200, 30, 30, 1.1)),
                   _definition("gear", placeholder=_box(60, 60, 20, 0.8))]  # fmt: skip
    instances = [{"name": "base", "item": "base"},
                 {"name": "fast", "item": "shaft"}, {"name": "slow", "item": "shaft"},
                 {"name": "pinion", "item": "gear"}, {"name": "wheel", "item": "gear"}]  # fmt: skip
    mates = [m for name in ("fast", "slow", "pinion", "wheel") for m in _seat(name, "base")]
    train = {
        "shafts": [
            {"name": "fast", "carries": ["pinion"],
             "supports": [{"name": "A", "at": _q(0, "mm")}, {"name": "B", "at": _q(200, "mm")}],
             "stations": [{"item": "pinion", "at": _q(100, "mm")}],
             "stiffness": {"diameter": _q(30, "mm"), "elastic_modulus": _q(207, "GPa"),
                           "source": "AISI 1045, Shigley Table A-5"}},
            {"name": "slow", "carries": ["wheel"]},
        ],
        "gears": [{"item": "pinion", "teeth": 18, "pitch_diameter": _q(54, "mm")},
                  {"item": "wheel", "teeth": 72, "pitch_diameter": _q(216, "mm")}],
        "meshes": [{"name": "pinion-wheel", "driver": "pinion", "driven": "wheel",
                    "efficiency": 1.0, "source": _LOSSLESS,
                    "pressure_angle": _q(20, "degree")}],
        "input": {"shaft": "fast", "speed": _q(1500, "rpm"), "power": _q(2.2, "kW")},
        "output": {"shaft": "slow", "speed_low": _q(370, "rpm"), "speed_high": _q(380, "rpm"),
                   "source": "the driven machine's rated speed"},
    }  # fmt: skip
    train.update(train_overrides)
    return {"anvilate_product": "1.17.0", "name": "reducer", "definitions": definitions,
            "instances": instances, "ground": "base", "mates": mates,
            "drive_train": train}  # fmt: skip


def test_a_product_carries_its_drive_train_and_screens_its_output_speed():
    """18/72 from 1,500 rpm is 375 rpm, inside the 370 to 380 band the machine asks for."""
    product = parse_product(_reducer_document())
    assert product.drive_train is not None
    report = product_screening(product)
    entry = _named(report, "output speed")
    assert entry.status is CheckStatus.PASS and "375 rpm, inside" in entry.detail


def test_a_product_whose_train_misses_its_band_fails_on_the_products_own_card():
    document = _reducer_document()
    document["drive_train"]["output"]["speed_low"] = _q(400, "rpm")
    document["drive_train"]["output"]["speed_high"] = _q(410, "rpm")
    entry = _named(product_screening(parse_product(document)), "output speed")
    assert (
        entry.status is CheckStatus.FAIL and "outside the required 400 to 410 rpm" in entry.detail
    )


def test_a_shaft_that_declares_its_bearings_and_stiffness_is_read_for_bending():
    """The fast shaft declares two bearings and a stiffness, so it gets a curve; the slow
    one declares neither, so the card says nothing about it rather than inventing a verdict.
    """
    document = _reducer_document()
    document["drive_train"]["shafts"][0]["stations"][0]["deflection_limit"] = _q(0.05, "mm")
    document["drive_train"]["shafts"][0]["stations"][0]["limit_source"] = "the gear maker's note"
    report = product_screening(parse_product(document))
    entry = _named(report, "fast pinion deflection")
    assert entry.status in (CheckStatus.PASS, CheckStatus.FAIL)
    assert "against a declared limit of 0.05 mm" in entry.detail
    assert not [e for e in report.entries if e.name.startswith("slow ")]


def test_a_train_naming_something_the_product_does_not_have_is_refused_at_parse():
    document = _reducer_document()
    document["drive_train"]["shafts"][1]["carries"] = ["flywheel"]
    with pytest.raises(ValueError, match=r"carries \['flywheel'\], which are not instances"):
        parse_product(document)
    document = _reducer_document()
    document["drive_train"]["gears"][0]["item"] = "sprocket"
    with pytest.raises(ValueError, match="declares a gear 'sprocket', which is not an instance"):
        parse_product(document)
    document = _reducer_document()
    document["drive_train"]["shafts"][0]["name"] = "layshaft"
    with pytest.raises(ValueError, match="declares a shaft 'layshaft', which is not an instance"):
        parse_product(document)


def test_a_train_that_cannot_be_a_machine_is_refused_before_anything_is_built():
    """The point of declaring the machine: the document does not parse if it is not one."""
    document = _reducer_document()
    document["drive_train"]["shafts"].append({"name": "base", "carries": ["base"]})
    with pytest.raises(ValueError, match="driven by nothing from the input"):
        parse_product(document)
    # 54 mm on 18 teeth and 216 mm on 72 are both module 3, and their radii sum to 135 mm.
    document = _reducer_document()
    document["drive_train"]["meshes"][0]["center_distance"] = _q(150, "mm")
    with pytest.raises(ValueError, match="declares a center distance of 150 mm and its "
                                         "pitch radii sum to 135 mm"):  # fmt: skip
        parse_product(document)
    # And a mesh whose two gears are not cut to one module, which the centre-distance check
    # cannot see at all: the sum of the two pitch radii closes whatever the modules are, so
    # this pair would have passed above with a centre distance of 77 mm declared on it.
    document = _reducer_document()
    document["drive_train"]["gears"][1]["pitch_diameter"] = _q(100, "mm")
    document["drive_train"]["meshes"][0]["center_distance"] = _q(77, "mm")
    with pytest.raises(ValueError, match="joins pinion at a module of 3 mm to wheel at "
                                         "1.389 mm"):  # fmt: skip
        parse_product(document)


def test_a_product_with_no_drive_train_adds_no_drive_train_entries():
    report = product_screening(parse_product(_cart()))
    assert [e for e in report.entries if e.name == "output speed"] == []


# --- Nothing typed twice inside a declared train (drive trains 1.4) ---------------------


def _shaft_spec(**params) -> dict:
    """A transmission shaft whose screen inputs the drive train derives.

    It REQUIRES its torque and its bending moment, which is why the refusal below cannot say
    "leave it out": the element has no state without them. It names the derived value to
    write instead.
    """
    return {
        "anvilate_spec": "1.3.0", "name": "shaft", "description": "a shaft inside the train",
        "units": {"value": "SI", "origin": "user_stated"},
        "material": {"ref": "ASTM-A36"}, "manufacturing": {"process": "cnc_turning"},
        "element_type": "transmission_shaft",
        "element_params": {"diameter": _q(30, "mm"), "length": _q(200, "mm"),
                           "yield_strength": _q(250, "MPa"),
                           "bending_moment": _q(27.6009, "N*m"), "torque": _q(14.0056, "N*m"),
                           **params},
        "acceptance": {"tiers": ["T1_analytical"]},
    }  # fmt: skip


def _reducer_with_shaft_spec(**params) -> dict:
    """The reducer, with its FAST shaft a real part instead of a placeholder.

    Only the fast one: the slow shaft keeps the placeholder, so the refusals below are read
    against one shaft's derived torque rather than whichever instance shared a definition.
    """
    document = _reducer_document()
    document["definitions"].append(_definition("fastpart", spec=_shaft_spec(**params)))
    for instance in document["instances"]:
        if instance["name"] == "fast":
            instance["item"] = "fastpart"
    return document


def test_a_shaft_inside_the_train_that_types_a_torque_the_flow_contradicts_is_refused():
    """2.2 kW at 1,500 rpm is 14.006 N·m on the fast shaft. A part that types 20 is a
    second source of truth, and a screen reading it would pass on the number it was given.
    """
    product = parse_product(_reducer_with_shaft_spec(torque=_q(20, "N*m")))
    with pytest.raises(ValueError, match="typed with a torque of 20 N.m and the drive train"):
        product_screening(product)
    # The remedy is actionable, because the element cannot omit the field: the refusal names
    # the value to write and the other way out.
    try:
        product_screening(product)
    except ValueError as refused:
        assert "Write 14.0056 N*m, or take 'fast' out of the drive train" in str(refused)
    # And the derived value is accepted: the refusal is for a contradiction, not for stating
    # a number the train agrees with.
    report = product_screening(parse_product(_reducer_with_shaft_spec()))
    assert _named(report, "output speed").status is CheckStatus.PASS


def test_a_shaft_that_types_a_bending_moment_its_own_statics_contradicts_is_refused():
    """The fast shaft declares two bearings, so its bending moment is derived too."""
    document = _reducer_with_shaft_spec(bending_moment=_q(500, "N*m"))
    with pytest.raises(ValueError, match="typed with a bending_moment of 500 N.m"):
        product_screening(parse_product(document))


def test_a_mesh_inside_the_train_that_types_its_pinion_torque_is_refused():
    mesh_spec = {
        "anvilate_spec": "1.3.0", "name": "mesh", "description": "a mesh inside the train",
        "units": {"value": "SI", "origin": "user_stated"},
        "material": {"ref": "ASTM-A36"}, "manufacturing": {"process": "cnc_turning"},
        "element_type": "spur_gear_mesh",
        "element_params": {"pinion_teeth": 18, "gear_teeth": 72,
                           "module": _q(3, "mm"), "face_width": _q(20, "mm"),
                           "pressure_angle": 20.0, "pinion_torque": _q(99, "N*m"),
                           "bending_geometry_factor": 0.31,
                           "contact_geometry_factor": 0.107,
                           "pinion_modulus": _q(207, "GPa"), "gear_modulus": _q(207, "GPa"),
                           "allowable_bending_stress": _q(200, "MPa"),
                           "allowable_contact_stress": _q(700, "MPa")},
        "acceptance": {"tiers": ["T1_analytical"]},
    }  # fmt: skip
    document = _reducer_document()
    document["definitions"].append(_definition("meshpart", spec=mesh_spec))
    document["instances"].append({"name": "pinion-wheel", "item": "meshpart"})
    document["mates"] += _seat("pinion-wheel", "base")
    with pytest.raises(ValueError, match="'pinion-wheel' is typed with a pinion_torque of 99"):
        product_screening(parse_product(document))


def test_a_part_the_train_does_not_name_may_type_whatever_it_likes():
    """The refusal covers the items the train names. A part beside the train is screened on
    what its own document states, as it always was — including a torque of its own."""
    document = _reducer_document()
    document["definitions"].append(_definition("stirrer", spec=_shaft_spec(torque=_q(20, "N*m"))))
    document["instances"].append({"name": "stirrer", "item": "stirrer"})
    document["mates"] += _seat("stirrer", "base")
    report = product_screening(parse_product(document))
    assert _named(report, "output speed").status is CheckStatus.PASS


# --- Envelopes of revolution and swept clearance (drive trains 4.2) ---------------------

_HOUSING = {"value": _q(3, "mm"), "source": "the housing's internal clearance rule"}


def _on_top(part: str, on: str) -> list[dict]:
    """Seat ``part`` on ``on``'s top, flush left and front: same footprint, so concentric."""
    return [
        {"id": f"{part}-sit", "kind": "face_to_face",
         "place": {"part": part, "face": "bottom"}, "on": {"part": on, "face": "top"}},
        {"id": f"{part}-left", "kind": "edge_flush",
         "place": {"part": part, "face": "left"}, "on": {"part": on, "face": "left"}},
        {"id": f"{part}-front", "kind": "edge_flush",
         "place": {"part": part, "face": "front"}, "on": {"part": on, "face": "front"}},
    ]  # fmt: skip


def _turning_document(
    *,
    axis: str | None = "z",
    gap: float = 200.0,
    gear: tuple[float, float, float] = (40, 40, 20),
    clearance: dict | None = _HOUSING,
) -> dict:
    """Two 40 x 40 posts standing on a base, their axes ``gap`` apart, each carrying a gear.

    Each gear has the post's footprint and is seated on its top flush left and front, so it
    is concentric with the post and its envelope of revolution is the post's: a cylinder of
    radius hypot(20, 20) = 28.284 mm. Pass a wider ``gear`` to move its envelope off the
    axis, which is the case the check exists to catch.
    """
    definitions = [_definition("base", placeholder=_box(600, 200, 12, 8.0)),
                   _definition("post", placeholder=_box(40, 40, 100, 1.0)),
                   _definition("disc", placeholder=_box(*gear, 0.6))]  # fmt: skip
    instances = [{"name": "base", "item": "base"}, {"name": "one", "item": "post"},
                 {"name": "rotor", "item": "disc"}, {"name": "two", "item": "post"},
                 {"name": "idler", "item": "disc"}]  # fmt: skip
    mates = [
        *_seat("one", "base"),
        *_on_top("rotor", "one"),
        {"id": "two-sit", "kind": "face_to_face",
         "place": {"part": "two", "face": "bottom"}, "on": {"part": "base", "face": "top"}},
        {"id": "two-beside", "kind": "face_to_face",
         "place": {"part": "two", "face": "left"}, "on": {"part": "one", "face": "right"},
         "offset": {"magnitude": gap - 40, "unit": "mm"}},
        {"id": "two-front", "kind": "edge_flush",
         "place": {"part": "two", "face": "front"}, "on": {"part": "base", "face": "front"}},
        *_on_top("idler", "two"),
    ]  # fmt: skip
    turning = {"axis": axis} if axis is not None else {}
    document = {
        "anvilate_product": "1.18.0", "name": "spinner", "definitions": definitions,
        "instances": instances, "ground": "base", "mates": mates,
        "drive_train": {
            "shafts": [{"name": "one", "carries": ["rotor"], **turning},
                       {"name": "two", "carries": ["idler"], **turning}],
            "gears": [{"item": "rotor", "teeth": 20, "pitch_diameter": _q(40, "mm")},
                      {"item": "idler", "teeth": 20, "pitch_diameter": _q(40, "mm")}],
            "meshes": [{"name": "pair", "driver": "rotor", "driven": "idler",
                        "efficiency": 1.0, "source": "taken as lossless for this screening"}],
            "input": {"shaft": "one", "speed": _q(600, "rpm"), "torque": _q(5, "N*m")},
        },
    }  # fmt: skip
    if clearance is not None:
        document["screening"] = {"min_clearance": clearance}
    return document


def _swept_between(report, turning: str, against: str):
    found = [a for a in report.swept
             if {a.turning, a.against} == {turning, against}]  # fmt: skip
    return found[0] if found else None


def test_a_turning_item_sweeps_a_cylinder_about_its_shafts_declared_axis():
    """Two 40 x 40 posts 200 mm apart each sweep a cylinder of radius hypot(20, 20), so the
    gap between their envelopes is 200 - 2 x 28.2843 = 143.431 mm, where the still gap
    between the two boxes is 160 mm."""
    report = product_screening(parse_product(_turning_document()))
    between = _swept_between(report, "rotor", "two")
    assert between is not None and between.both_turn
    assert between.gap_mm == pytest.approx(200 - 2 * math.hypot(20, 20), abs=1e-3)
    # The two posts themselves are not gauged: a mate places one off the other, and a pair a
    # mate holds is not a clearance.
    assert _swept_between(report, "one", "two") is None
    assert _named(report, "swept clearance").status is CheckStatus.PASS


def test_two_gears_in_mesh_are_not_gauged_because_touching_is_what_a_mesh_does():
    report = product_screening(parse_product(_turning_document()))
    assert _swept_between(report, "rotor", "idler") is None
    # And items on ONE shaft turn together, so they are not gauged against each other.
    assert _swept_between(report, "one", "rotor") is None
    assert _swept_between(report, "two", "idler") is None


def test_an_item_off_its_shafts_axis_sweeps_wider_and_the_check_says_so():
    """A gear whose footprint overhangs its shaft sweeps a ring reaching past its own body.
    A 120 x 40 disc seated flush left on a 40 x 40 post has its centre 40 mm off the post's
    axis, so its furthest corner is hypot(100, 20) = 101.98 mm out and its envelope is that
    cylinder — far past its own 120 mm width. Against the post 200 mm away, whose envelope
    reaches 28.284 mm, that leaves 200 - 101.98 - 28.284 = 69.7 mm.
    """
    report = product_screening(parse_product(_turning_document(gear=(120, 40, 20))))
    reach = _swept_between(report, "rotor", "two")
    assert reach is not None
    assert reach.gap_mm == pytest.approx(200 - math.hypot(100, 20) - math.hypot(20, 20), abs=1e-3)
    # Closed right up it fails, and the detail says the envelope came from a bounding box, so
    # a reader knows a round gear modelled as a box sweeps wider than the gear does.
    close = product_screening(parse_product(_turning_document(gear=(120, 40, 20), gap=100)))
    entry = _named(close, "swept clearance")
    assert entry.status is CheckStatus.FAIL
    assert "sweeps within" in entry.detail and "bounding box sweeps" in entry.detail


def test_a_clearance_that_holds_stopped_can_close_when_the_machine_runs():
    """The whole reason for the check. With the axes 50 mm apart the parts clear each other
    standing still — every still gap is past the 3 mm the housing asks for — and two
    envelopes of radius 28.284 mm overlap the moment the machine runs."""
    report = product_screening(parse_product(_turning_document(gap=50)))
    assert _named(report, "clearance").status is CheckStatus.PASS
    assert _named(report, "swept clearance").status is CheckStatus.FAIL
    # Two solids that overlap are zero apart, not a negative distance: the gauge measures a
    # gap and there is none. Zero is below every positive limit, so the verdict is the same.
    assert _swept_between(report, "rotor", "two").gap_mm == 0.0
    # And it really is an overlap, not a touch: pull them apart and the gap appears.
    apart = product_screening(parse_product(_turning_document(gap=70)))
    assert _swept_between(apart, "rotor", "two").gap_mm == pytest.approx(
        70 - 2 * math.hypot(20, 20), abs=1e-3
    )


def test_a_shaft_that_declares_no_axis_sweeps_nothing_and_the_entry_names_what_to_declare():
    report = product_screening(parse_product(_turning_document(axis=None)))
    assert report.swept == ()
    entry = _named(report, "swept clearance")
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert [need.declaration for need in entry.needs] == ["drive_train.shafts[].axis"]


def test_an_item_a_mate_holds_is_not_gauged_against_what_holds_it():
    """A post standing on its base touches the base, and that is the mate working."""
    report = product_screening(parse_product(_turning_document()))
    assert _swept_between(report, "one", "base") is None
    # The gear is mated to its post, not to the base, so the base IS gauged against it.
    assert _swept_between(report, "rotor", "base") is not None


def test_a_product_with_no_declared_clearance_gets_no_swept_entry():
    report = product_screening(parse_product(_turning_document(clearance=None)))
    assert report.swept  # the envelopes are still reported
    assert [e for e in report.entries if e.name == "swept clearance"] == []


# --- A load at an interface, where that interface is (product screening 1.1) --------------


def _hung(face: str, on_item: bool = False) -> dict:
    """The cart, with the FRAME offering a mounting face and the payload arriving there.

    The frame is 600 x 400 and stands on three casters, so where its load lands decides how
    the three share it — which is the thing worth checking. The plate, by contrast, rests on
    one patch: whatever acts on it goes to that one support wherever it acted, so a position
    on the plate could not be observed from below it.

    ``on_item`` declares the same payload on the item instead. Same force, different place.
    """
    document = _carted(_THREE, ("right", "back"))
    frame = next(d for d in document["definitions"] if d["id"] == "frame")
    # A placeholder states its interfaces inside itself, not beside it.
    frame["placeholder"]["interfaces"] = [{"name": "pad", "kind": "mounting_face",
                                           "face": face}]  # fmt: skip
    payload = {"mass": _q(50, "kg"), "source": "payload spec"}
    document["screening"]["loads"] = [
        {**payload, "item": "frame"} if on_item else {**payload, "at": "frame.pad"}
    ]
    return document


def test_a_load_at_an_interface_arrives_where_the_interface_is():
    """A face is off to one side of the item it is on, and the load path is a moment
    calculation, so the two places are not interchangeable.

    The frame is 600 mm across. A load at its LEFT face acts 300 mm to the -x side of the
    load on the item, and at its RIGHT face 300 mm to the +x side, so the three put three
    different resultants over the casters and three different shares on them.
    """
    carried = {}
    for name, document in (("item", _hung("left", on_item=True)),
                           ("left", _hung("left")), ("right", _hung("right"))):  # fmt: skip
        report = product_screening(parse_product(document))
        frame = {s.body: s for s in report.load_path}["cart/frame"]
        carried[name] = {r.support: r.force_n for r in frame.reactions}
        # The same force arrives however it is declared; only where it lands differs.
        assert frame.carries_n == pytest.approx(63 * 9.80665)
    assert carried["left"] != carried["item"] != carried["right"]
    # caster1 is the -x pair's front corner, so moving the load towards -x loads it more
    # and moving it towards +x loads it less. The item's own middle sits between the two.
    assert (carried["right"]["cart/caster1"]
            < carried["item"]["cart/caster1"]
            < carried["left"]["cart/caster1"])  # fmt: skip


def test_the_load_path_entry_names_the_interface_a_load_arrived_at():
    """A reader following a number down meets where it came in, not just which item."""
    report = product_screening(parse_product(_hung("left")))
    detail = _named(report, "load path cart/frame").detail
    assert "490.3 N as the load at frame.pad (payload spec)" in detail
    on_item = product_screening(parse_product(_hung("left", on_item=True)))
    assert (
        "490.3 N as the load on frame (payload spec)"
        in _named(on_item, "load path cart/frame").detail
    )


def test_a_load_at_an_interface_nothing_offers_is_refused_at_parse():
    document = _hung("left")
    document["screening"]["loads"][0]["at"] = "frame.nowhere"
    with pytest.raises(ValueError, match="'frame' offers no interface 'nowhere'"):
        parse_product(document)
    document = _hung("left")
    document["screening"]["loads"][0]["at"] = "nosuchitem.pad"
    with pytest.raises(ValueError, match="which is not an instance of 'cart'"):
        parse_product(document)
    document = _hung("left")
    document["screening"]["loads"][0]["at"] = "frame"
    with pytest.raises(ValueError, match="is not item.interface"):
        parse_product(document)


def test_a_load_states_an_item_or_an_interface_and_not_both_or_neither():
    document = _hung("left")
    document["screening"]["loads"][0]["item"] = "frame"
    with pytest.raises(ValueError, match="states both an item and an at"):
        parse_product(document)
    document = _hung("left")
    del document["screening"]["loads"][0]["at"]
    with pytest.raises(ValueError, match="states neither an item nor an at"):
        parse_product(document)


# --- One card for the whole design, and the journey over it -------------------------------


def test_the__product_scorecard_carries_every_item_s_checks_and_the_product_s_own():
    """Two halves that have to be read together.

    The item cards are a tree and the whole-product checks are a flat list. A card carrying
    only one of them says the wrong thing: an item that passes under a product whose own
    load path is not determined is not a design anything has screened.
    """
    from anvilate.product import place_product
    from anvilate.product_screening import _product_scorecard

    product = parse_product(_carted(_THREE, ("right", "back")))
    placed = place_product(product)
    screening = product_screening(product)
    card = _product_scorecard(placed, screening)
    names = [e.name for e in card.entries]
    # Every whole-product entry, under the name it already has.
    for entry in screening.entries:
        assert entry.name in names
    # And every item's own, renamed by the path that owns it, so two items running the
    # same check are told apart.
    assert sum(1 for n in names if n.endswith(" caster load")) == 3
    assert "cart/caster1 cart/caster1 caster load" not in names
    assert len(card.entries) > len(screening.entries)
    with pytest.raises(ValueError, match="screening must be the ProductScreening"):
        _product_scorecard(placed, "not a screening")


def test_the_product_journey_reads_the_items_and_the_product_together():
    """The reducer is not a screened design: seven of its items are placeholders.

    A journey over the whole-product checks alone would call it screened, because those
    checks all pass. The step it names is the one that would actually move it on.
    """
    from pathlib import Path

    from anvilate.journey import journey_state, next_steps
    from anvilate.product import load_product, place_product
    from anvilate.product_screening import _product_scorecard

    path = Path(__file__).parents[1] / "examples" / "products" / "gear_reducer.product.yaml"
    product, library = load_product(path)
    placed = place_product(product, library=library, root=path.parent)
    screening = product_screening(product, library=library, root=path.parent)
    assert Scorecard(entries=screening.entries).status is CheckStatus.PASS
    card = _product_scorecard(placed, screening)
    state = journey_state(card)
    assert state.stage == "described"
    screened = next(s for s in state.stages if s.stage == "screened")
    assert screened.state == "not_reached"
    assert any("placeholder has no verdict" in gap for gap in screened.gaps)
    first = next_steps(card, tool="build_combination", export_format="step")[0]
    assert first.tool == "build_combination" and "definitions[].spec" in str(first)


def test_the_load_path_verdict_supersedes_the_item_s_own_no_load_stated():
    """The contradiction this closes, in the cart's own numbers.

    An item is screened when the product is placed, before any load path exists, so a
    caster's own card says the product states no load for it. The screening then derives
    that load from the declared payload and fails caster3's rating with it. Both entries
    carry the same name, and only one of them was computed with the load.
    """
    from anvilate.product import place_product
    from anvilate.product_screening import _product_scorecard, load_path_supersedes

    product = parse_product(_carted(_THREE, ("right", "back")))
    placed, screening = place_product(product), product_screening(product)

    def walk(card, found):
        found += [(f"{card.path} {e.name}", e) for e in card.entries]
        for child in card.children:
            walk(child, found)
        return found

    own = dict(walk(placed.card, []))
    # The item's own card: not evaluated, and it says why — it has no load to check with.
    assert own["cart/caster3 caster load"].status is CheckStatus.NOT_EVALUATED
    assert "states no load for this component" in own["cart/caster3 caster load"].detail
    # The product's: the same check, failed, on the load the path delivered.
    fed = next(e for e in screening.entries if e.name == "cart/caster3 caster load")
    assert fed.status is CheckStatus.FAIL

    assert set(load_path_supersedes(placed, screening)) == {
        f"cart/caster{n} caster load" for n in (1, 2, 3)
    }
    card = _product_scorecard(placed, screening)
    named = [e for e in card.entries if e.name == "cart/caster3 caster load"]
    assert len(named) == 1 and named[0].status is CheckStatus.FAIL
    # And the card's verdict is the failure, not the not-evaluated that would have masked it.
    assert card.status is CheckStatus.FAIL
