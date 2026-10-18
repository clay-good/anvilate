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
from anvilate.scorecard import CheckStatus  # noqa: E402
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
