"""Material compliance: the spec's scenarios on placeholders that name their materials."""

from __future__ import annotations

import pytest

pytest.importorskip("build123d")

from anvilate.compliance import composition_export, screen_material_needs  # noqa: E402
from anvilate.product import parse_product  # noqa: E402
from anvilate.scorecard import CheckStatus  # noqa: E402
from test_product_cards import _box, _definition, _seat  # noqa: E402


def _q(v: float, unit: str) -> dict:
    return {"magnitude": v, "unit": unit}


def _instrument(needs: dict, attributes: dict, recycled: float | None = None) -> dict:
    handle = _definition("handle", placeholder=_box(120, 30, 30, 3.0))
    handle["material"] = "PA66"
    shaft = _definition("shaft", placeholder=_box(200, 10, 10, 1.2))
    shaft["material"] = "PP"
    pa66 = {"material": "PA66", "plastic": True, "attributes": attributes,
            "composition": [{"cas": "32131-17-2", "name": "polyamide 66", "fraction": 0.7},
                            {"cas": "65997-17-3", "name": "glass fibre", "fraction": 0.3}],
            "composition_source": "supplier declaration 2026-03"}  # fmt: skip
    if recycled is not None:
        pa66["recycled_fraction"] = {"value": recycled, "source": "supplier certificate"}
    pp = {"material": "PP", "plastic": True,
          "recycled_fraction": {"value": 0.0, "source": "virgin grade"}}  # fmt: skip
    return {"name": "instrument", "definitions": [handle, shaft],
            "instances": [{"name": "handle", "item": "handle"}, {"name": "shaft", "item": "shaft"}],
            "ground": "handle", "mates": _seat("shaft", "handle"),
            "screening": {"materials": [pa66, pp],
                          "needs": {"items": ["handle"], **needs}}}  # fmt: skip


def _entry(needs: dict, attributes: dict, name: str):
    product = parse_product(_instrument(needs, attributes))
    return {e.name: e for e in screen_material_needs(product)}[name]


def test_a_plastic_that_will_not_survive_the_autoclave_fails_naming_both_temperatures():
    entry = _entry(
        {"sterilization": {"method": "steam autoclave", "temperature": _q(134, "degC"),
                           "source": "reprocessing instructions"}},
        {"service_max_temperature": {"value": _q(100, "degC"), "source": "datasheet p.4"}},
        "handle sterilization",
    )  # fmt: skip
    assert entry.status is CheckStatus.FAIL
    assert "PA66 is declared for service to 100" in entry.detail
    assert "steam autoclave sterilization reaches 134" in entry.detail


def test_outgassing_in_vacuum_fails_against_the_screen_citing_both_sources():
    entry = _entry({"vacuum": {"value": 0.010, "source": "outgassing screen, TML"}},
                   {"total_mass_loss": {"value": 0.014, "source": "outgassing test report 12"}},
                   "handle vacuum outgassing")  # fmt: skip
    assert entry.status is CheckStatus.FAIL
    assert "loses 1.40% of its mass in vacuum (outgassing test report 12)" in entry.detail
    assert "against the 1.00% screen (outgassing screen, TML)" in entry.detail


@pytest.mark.parametrize(
    ("rating", "status"), [("HB", CheckStatus.FAIL), ("V-0", CheckStatus.PASS)]
)
def test_flammability_is_held_to_the_least_class_needed(rating, status):
    entry = _entry({"flammability": {"value": "V-0", "source": "enclosure standard"}},
                   {"flammability": {"value": rating, "source": "UL card"}},
                   "handle flammability")  # fmt: skip
    assert entry.status is status


def test_an_attribute_the_material_does_not_declare_is_not_evaluated():
    entry = _entry({"service_temperature": {"value": _q(85, "degC"), "source": "spec"}}, {},
                   "handle service temperature")  # fmt: skip
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "declares no service max temperature" in entry.detail


def test_recycled_plastic_rolls_up_by_mass():
    # 3.0 kg at 30% recycled and 1.2 kg virgin: 0.9 kg of 4.2 kg, 21%
    report = composition_export(parse_product(_instrument({}, {}, recycled=0.3)))
    assert report.recycled.plastic_kg == pytest.approx(4.2)
    assert report.recycled.recycled_kg == pytest.approx(0.9)
    assert report.recycled.fraction == pytest.approx(0.9 / 4.2)
    handle = next(line for line in report.lines if line.path == "instrument/handle")
    assert handle.substances[0] == ("32131-17-2", "polyamide 66", 0.7)
    undeclared = composition_export(parse_product(_instrument({}, {})))
    assert undeclared.recycled.fraction is None
    assert undeclared.recycled.undeclared == ("instrument/handle",)


def test_a_declaration_that_cannot_be_one_is_refused():
    from anvilate.product import ProductError

    document = _instrument({}, {})
    document["screening"]["materials"][0]["composition_source"] = None
    with pytest.raises(ProductError, match="composition is not cited"):
        parse_product(document)
    document = _instrument({}, {"colour": {"value": "black", "source": "x"}})
    with pytest.raises(ProductError, match=r"declares \['colour'\]"):
        parse_product(document)


@pytest.mark.parametrize(
    ("needs", "attributes", "message"),
    [
        ({}, {"service_max_temperature": {"value": 100.0, "source": "x"}},
         "service_max_temperature is 100.0; it is a temperature"),
        ({}, {"total_mass_loss": {"value": 1.4, "source": "x"}}, "it is a fraction from 0 to 1"),
        ({}, {"flammability": {"value": "V0", "source": "x"}}, "it is a UL 94 class"),
        ({"vacuum": {"value": "low", "source": "x"}}, {}, "need vacuum is 'low'"),
        ({"sterilization": {"method": "steam", "temperature": _q(134, "mm"), "source": "x"}}, {},
         "sterilization temperature"),
        ({"items": ["lid"]}, {}, "material needs name 'lid'"),
    ],
)  # fmt: skip
def test_a_value_of_the_wrong_kind_is_refused_where_it_is_declared(needs, attributes, message):
    from anvilate.product import ProductError

    with pytest.raises(ProductError, match=message):
        parse_product(_instrument(needs, attributes))


def test_a_material_declared_twice_is_refused():
    from anvilate.product import ProductError

    document = _instrument({}, {})
    document["screening"]["materials"].append({"material": "PP"})
    with pytest.raises(ProductError, match=r"materials \['PP'\] are declared twice"):
        parse_product(document)


def test_the_docs_page_states_each_check_the_code_runs():
    import re
    from pathlib import Path

    from anvilate.compliance import _CHECKS
    from anvilate.product import UL94_CLASSES

    page = (Path(__file__).parents[1] / "docs" / "material-compliance.md").read_text()
    rows = re.findall(r"^\| ([a-z ]+) \| `(\w+)` \| `(\w+)` \| .+ \|$", page, re.M)
    assert tuple(rows) == _CHECKS
    assert "rank " + ", ".join(UL94_CLASSES) + "," in page
    assert "carry 0.9 kg recycled of 4.2 kg, 21%" in page
    assert f"{0.9 / 4.2:.0%}" == "21%"
