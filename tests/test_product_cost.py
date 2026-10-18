"""Product cost: unit prices, cited and dated, rolled up by node and never summed as zero."""

from __future__ import annotations

import pytest

pytest.importorskip("build123d")

from anvilate.product import ProductError, parse_product  # noqa: E402
from anvilate.product_screening import product_screening  # noqa: E402
from test_product_cards import _box, _definition, _seat  # noqa: E402
from test_product_screening import _THREE, _carted  # noqa: E402


def _price(amount: float, currency: str = "USD") -> dict:
    return {"amount": amount, "currency": currency, "source": "quote Q-118", "date": "2026-09-01"}


_FRAME, _PLATE, _CASTER = _price(120.0), _price(15.0), _price(8.5)


def _cart(frame=_FRAME, plate=_PLATE, caster=_CASTER) -> dict:
    document = _carted(_THREE, ("right", "back"))
    for definition in document["definitions"]:
        if definition["id"] == "caster":
            definition["component"]["price"] = caster
        else:
            definition["price"] = frame if definition["id"] == "frame" else plate
    return document


def test_a_priced_product_totals_every_item_it_places():
    report = product_screening(parse_product(_cart()))
    (top,) = report.costs
    assert top.complete and top.currency == "USD" and top.items == 5
    assert top.priced_total == pytest.approx(120.0 + 15.0 + 3 * 8.5)
    assert str(top) == "cart: 160.50 USD over 5 items"
    caster = next(line for line in report.cost_lines if line.path == "cart/caster1")
    assert (caster.amount, caster.source, caster.as_of.isoformat()) == (
        8.5, "quote Q-118", "2026-09-01")  # fmt: skip


def test_a_component_with_no_price_leaves_the_total_incomplete_naming_it():
    report = product_screening(parse_product(_cart(caster=None)))
    (top,) = report.costs
    assert not top.complete
    assert top.unpriced == ("cart/caster1", "cart/caster2", "cart/caster3")
    assert top.priced_total == pytest.approx(135.0)
    assert str(top) == ("cart: incomplete, 135.00 USD for the priced items; no price for "
                        "cart/caster1, cart/caster2, cart/caster3")  # fmt: skip


def test_prices_in_two_currencies_are_not_summed():
    (top,) = product_screening(parse_product(_cart(plate=_price(14.0, "EUR")))).costs
    assert not top.complete and top.priced_total is None and top.currency is None
    assert top.currencies == ("EUR", "USD")
    assert str(top) == "cart: no total, priced in EUR, USD"


def test_each_product_node_rolls_up_its_own_items():
    drive = parse_product({
        "name": "drive",
        "definitions": [_definition("plate", placeholder=_box(80, 60, 8, 0.6), price=_price(9)),
                        _definition("motor", placeholder=_box(40, 40, 50, 0.9))],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "motor", "item": "motor"}],
        "ground": "plate", "mates": _seat("motor", "plate"),
    })  # fmt: skip
    stage = parse_product({
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(200, 100, 10, 2.0), price=_price(40)),
                        _definition("drive", product="drive")],
        "instances": [{"name": "base", "item": "base"}, {"name": "drive", "item": "drive"}],
        "ground": "base", "mates": _seat("drive", "base"),
    })  # fmt: skip
    costs = product_screening(stage, library={"drive": drive}).costs
    assert [(c.path, c.priced_total, c.unpriced) for c in costs] == [
        ("stage", 49.0, ("stage/drive/motor",)),
        ("stage/drive", 9.0, ("stage/drive/motor",)),
    ]


@pytest.mark.parametrize(
    ("price", "message"),
    [({**_price(5), "currency": "usd"}, "currency"), ({**_price(5), "amount": 0}, "amount"),
     ({**_price(5), "amount": float("inf")}, "amount"), ({**_price(5), "date": "soon"}, "date")],
)  # fmt: skip
def test_a_price_that_is_not_one_is_refused(price, message):
    with pytest.raises(ProductError, match=message):
        parse_product(_cart(frame=price))


def test_a_price_goes_where_it_can_be_read():
    document = _cart()
    document["definitions"].append(_definition("sub", product="drive", price=_price(3)))
    with pytest.raises(ProductError, match="states a price and is a product"):
        parse_product(document)


def test_the_docs_page_states_the_cart_the_tests_build():
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "product-screening.md").read_text()
    (whole,) = product_screening(parse_product(_cart())).costs
    (partial,) = product_screening(parse_product(_cart(caster=None))).costs
    assert f"totals {whole.priced_total:.2f} over {whole.items} items" in page
    assert f"incomplete, at {partial.priced_total:.2f} for\nthe priced items" in page
    for price in (_FRAME, _PLATE, _CASTER):
        assert f"{price['amount']:.2f}" in page
