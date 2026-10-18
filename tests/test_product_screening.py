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
    (entry,) = report.entries
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
        (entry,) = product_screening(parse_product(column)).entries
        assert entry.status is status
        assert f"leaves it at {expected:.3g} degrees" in entry.detail


def test_clearance_between_items_that_share_no_connection():
    document = _cart({"min_clearance": {"value": _q(150, "mm"), "source": "service access"}},
                     second_block=True)  # fmt: skip
    report = product_screening(parse_product(document))
    pair = {"cart/block", "cart/other"}
    (closest,) = [a for a in report.approaches if {a.first, a.second} == pair]
    assert closest.gap_mm == pytest.approx(120) and closest.at_mm[0] == pytest.approx(0)
    (entry,) = report.entries
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
    (entry,) = report.entries
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
