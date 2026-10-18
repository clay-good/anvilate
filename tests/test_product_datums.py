"""Layout datums: items placed against planes, axes and points the layout fixes.

A 400 × 100 × 10 base is the ground (z −5 to 5). The layout puts a ``deck`` plane at
z = deck_height (40 mm) and a ``rail_line`` plane at x = −150. A 40 mm block sat on the
deck, flush with the rail line and the base's front, spans x −150 to −110, y −50 to −10,
z 40 to 80. A 20 × 20 × 100 shaft on the ``spindle`` axis through (100, 0, 0), standing on
the base, spans x 90 to 110, y −10 to 10, z 5 to 105.
"""

from __future__ import annotations

import pytest

pytest.importorskip("build123d")

from anvilate.product import (  # noqa: E402
    ProductError,
    parse_product,
    place_product,
    resolve_variant,
)


def _mm(v: float) -> dict:
    return {"magnitude": v, "unit": "mm"}


def _holder(x: float, y: float, z: float, kg: float) -> dict:
    return {"envelope": [_mm(x), _mm(y), _mm(z)], "mass": {"magnitude": kg, "unit": "kg"},
            "reason": "not yet detailed"}  # fmt: skip


def _mate(id_: str, kind: str, place: dict, on: dict) -> dict:
    return {"id": id_, "kind": kind, "place": place, "on": on}


def _document() -> dict:
    return {
        "name": "frame",
        "layout": {
            "parameters": [{"name": "deck_height", "value": _mm(40), "source": "clearance study"}],
            "datums": [
                {"name": "deck", "kind": "plane", "direction": "z",
                 "at": [_mm(0), _mm(0), {"layout": "deck_height"}]},
                {"name": "rail_line", "kind": "plane", "direction": "x",
                 "at": [_mm(-150), _mm(0), _mm(0)]},
                {"name": "spindle", "kind": "axis", "direction": "z",
                 "at": [_mm(100), _mm(0), _mm(0)]},
            ],
        },
        "definitions": [
            {"id": "base", "identity": {"description": "base", "source": "make"},
             "placeholder": _holder(400, 100, 10, 3.0)},
            {"id": "block", "identity": {"description": "block", "source": "make"},
             "placeholder": _holder(40, 40, 40, 0.5)},
            {"id": "shaft", "identity": {"description": "shaft", "source": "make"},
             "placeholder": _holder(20, 20, 100, 0.2)},
        ],
        "instances": [{"name": "base", "item": "base"}, {"name": "block", "item": "block"},
                      {"name": "shaft", "item": "shaft"}],
        "ground": "base",
        "mates": [
            _mate("on-deck", "face_to_face", {"part": "block", "face": "bottom"},
                  {"part": "deck", "face": "top"}),
            _mate("on-line", "edge_flush", {"part": "block", "face": "left"},
                  {"part": "rail_line", "face": "left"}),
            _mate("front", "edge_flush", {"part": "block", "face": "front"},
                  {"part": "base", "face": "front"}),
            {**_mate("on-axis", "shaft_in_bore", {"part": "shaft", "axis": "z"},
                     {"part": "spindle", "axis": "z"}), "rotation_deg": 0.0},
            _mate("stands", "face_to_face", {"part": "shaft", "face": "bottom"},
                  {"part": "base", "face": "top"}),
        ],
    }  # fmt: skip


def _box(placed, path):
    body = next(b for b in placed.bodies if b.path == path)
    return body.box_min_mm, body.box_max_mm


def test_an_item_sits_on_a_plane_and_lines_up_with_another():
    placed = place_product(parse_product(_document()))
    low, high = _box(placed, "frame/block")
    assert low == pytest.approx((-150, -50, 40)) and high == pytest.approx((-110, -10, 80))


def test_an_item_runs_on_an_axis():
    placed = place_product(parse_product(_document()))
    low, high = _box(placed, "frame/shaft")
    assert low[0] == pytest.approx(90) and high[0] == pytest.approx(110)
    assert (low[2], high[2]) == pytest.approx((5, 105))


def test_a_datum_is_in_no_body_and_no_mass():
    placed = place_product(parse_product(_document()))
    assert [b.path for b in placed.bodies] == ["frame/base", "frame/block", "frame/shaft"]
    assert placed.mass_kg == pytest.approx(3.7)


def test_a_datum_reads_a_layout_parameter_and_a_variant_moves_it():
    document = _document()
    document["variants"] = [{"name": "tall", "parameters": {"deck_height": _mm(60)}}]
    product = parse_product(document)
    assert product.layout.parameters[0].read_by == ("@layout:datums.0.at.2",)
    tall = place_product(resolve_variant(product, "tall"))
    assert _box(tall, "frame-tall/block")[0][2] == pytest.approx(60)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda m: m[0]["on"].update(face="left"), "asks the z plane 'deck' for its left face"),
        (lambda m: m[3]["on"].update(axis="x"), "asks the z axis 'spindle' for the x axis"),
        (
            lambda m: m.append(
                _mate(
                    "back",
                    "edge_flush",
                    {"part": "deck", "face": "top"},
                    {"part": "base", "face": "top"},
                )
            ),
            "places the datum 'deck'",
        ),
        (lambda m: m[0]["on"].update(part="nowhere"), "not an instance or datum of 'frame'"),
    ],
)
def test_a_mate_a_datum_cannot_meet_is_refused(change, message):
    document = _document()
    change(document["mates"])
    with pytest.raises(ProductError, match=message):
        place_product(parse_product(document))


@pytest.mark.parametrize(
    ("datum", "message"),
    [
        ({"name": "base", "kind": "point", "at": [_mm(0)] * 3}, r"\['base'\] are declared twice"),
        ({"name": "p", "kind": "point", "direction": "z", "at": [_mm(0)] * 3}, "a point none"),
        ({"name": "p", "kind": "plane", "at": [_mm(0)] * 3}, "states no direction"),
    ],
)
def test_a_datum_that_cannot_be_one_is_refused(datum, message):
    document = _document()
    document["layout"]["datums"].append(datum)
    with pytest.raises(ProductError, match=message):
        parse_product(document)
