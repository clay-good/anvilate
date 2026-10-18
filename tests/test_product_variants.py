"""Named variants, each resolved to a complete product: the spec's long-stroke stage.

A 400 × 100 × 10 base carries a rail seated flush with its left and front edges, so the
rail spans x −200 to −200 + stroke, and a 40 mm motor bolted through two holes at x 150,
spanning x 130 to 170. A 250 mm stroke leaves the rail short of the motor; the long
variant's 350 mm runs it to x 150, into the motor, and only that variant fails.
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
from anvilate.scorecard import CheckStatus  # noqa: E402


def _mm(v: float) -> dict:
    return {"magnitude": v, "unit": "mm"}


def _hole(tag: str, x: float, y: float, z: float, face: str) -> dict:
    return {"tag": tag, "x": _mm(x), "y": _mm(y), "z": _mm(z), "face": face, "diameter": _mm(5)}


def _motor(height: float, tags: tuple[str, str] = ("m1", "m2")) -> dict:
    z = -height / 2
    return {"id": "motor", "identity": {"description": f"motor, {height:g} tall", "source": "buy"},
            "placeholder": {"envelope": [_mm(40), _mm(40), _mm(height)],
                            "mass": {"magnitude": 0.8, "unit": "kg"}, "reason": "not chosen",
                            "holes": [_hole(tags[0], 0, -15, z, "bottom"),
                                      _hole(tags[1], 0, 15, z, "bottom")]}}  # fmt: skip


def _stage(variants: list[dict]) -> dict:
    seat = [
        {"id": "sit", "kind": "face_to_face", "place": {"part": "rail", "face": "bottom"},
         "on": {"part": "base", "face": "top"}},
        {"id": "left", "kind": "edge_flush", "place": {"part": "rail", "face": "left"},
         "on": {"part": "base", "face": "left"}},
        {"id": "front", "kind": "edge_flush", "place": {"part": "rail", "face": "front"},
         "on": {"part": "base", "face": "front"}},
    ]  # fmt: skip
    return {
        "name": "stage",
        "layout": {"parameters": [{"name": "stroke", "value": _mm(250),
                                   "source": "customer travel"}]},
        "definitions": [
            {"id": "base", "identity": {"description": "base", "source": "make"},
             "placeholder": {"envelope": [_mm(400), _mm(100), _mm(10)],
                             "mass": {"magnitude": 3.0, "unit": "kg"}, "reason": "undetailed",
                             "holes": [_hole("b1", 150, -15, 5, "top"),
                                       _hole("b2", 150, 15, 5, "top")]}},
            {"id": "rail", "identity": {"description": "rail", "source": "buy"},
             "placeholder": {"envelope": [{"layout": "stroke"}, _mm(80), _mm(10)],
                             "mass": {"magnitude": 1.0, "unit": "kg"}, "reason": "undetailed"}},
            _motor(40),
        ],
        "instances": [{"name": "base", "item": "base"}, {"name": "rail", "item": "rail"},
                      {"name": "motor", "item": "motor"}],
        "ground": "base",
        "mates": [*seat,
                  {"id": "bolted", "kind": "hole_pattern",
                   "place": {"part": "motor", "face": "bottom", "holes": ["m1", "m2"]},
                   "on": {"part": "base", "face": "top", "holes": ["b1", "b2"]}}],
        "variants": variants,
    }  # fmt: skip


_LONG = {"name": "long", "parameters": {"stroke": _mm(350)}, "substitutions": [_motor(60)]}


def _box(placed, path):
    body = next(b for b in placed.bodies if b.path == path)
    return body.box_min_mm, body.box_max_mm


def test_each_variant_is_its_own_product_and_fails_alone():
    stage = parse_product(_stage([_LONG]))
    base = place_product(stage)
    long = place_product(resolve_variant(stage, "long"))
    assert base.name == "stage" and long.name == "stage-long"
    assert _box(base, "stage/rail")[1][0] == pytest.approx(50)
    assert _box(long, "stage-long/rail")[1][0] == pytest.approx(150)  # the stroke reached it
    assert _box(long, "stage-long/motor")[1][2] == pytest.approx(5 + 60)  # the taller motor
    assert base.interference.status is CheckStatus.PASS
    assert long.interference.status is CheckStatus.FAIL
    assert "stage-long/rail and stage-long/motor" in long.interference.detail


def test_a_variant_carries_its_values_into_its_layout_and_keeps_the_base_untouched():
    stage = parse_product(_stage([_LONG]))
    long = resolve_variant(stage, "long")
    assert long.layout.parameters[0].value.to("mm").magnitude == 350
    assert long.layout.parameters[0].read_by == ("rail:placeholder.envelope.0",)
    assert long.variants == () and long.definitions[2].placeholder.envelope[2].magnitude == 60
    assert stage.definitions[1].placeholder.envelope[0].to("mm").magnitude == 250


def test_a_substitute_reads_the_variants_value():
    rail = {"id": "rail", "identity": {"description": "long rail", "source": "buy"},
            "placeholder": {"envelope": [{"layout": "stroke"}, _mm(80), _mm(12)],
                            "mass": {"magnitude": 1.4, "unit": "kg"},
                            "reason": "undetailed"}}  # fmt: skip
    stage = parse_product(_stage([{"name": "long", "parameters": {"stroke": _mm(300)},
                                   "substitutions": [rail]}]))  # fmt: skip
    substitute = stage.variants[0].substitutions[0].placeholder
    assert substitute.envelope[0].to("mm").magnitude == 300
    long = resolve_variant(stage, "long")
    assert long.definitions[1].placeholder.envelope[2].to("mm").magnitude == 12
    # the substitute's own read is not one of the base product's readers
    assert long.layout.parameters[0].read_by == ()


def test_a_substitute_missing_an_interface_a_mate_uses_is_refused_naming_the_mate():
    stage = parse_product(_stage([{"name": "cheap", "substitutions": [_motor(40, ("a", "b"))]}]))
    with pytest.raises(ProductError, match=r"variant 'cheap' puts 'motor' where mate 'bolted' "
                       r"uses \['m1', 'm2'\], which it does not offer \(a, b\)"):  # fmt: skip
        resolve_variant(stage, "cheap")


@pytest.mark.parametrize(
    ("variants", "message"),
    [
        ([_LONG, _LONG], "variant 'long' is declared twice"),
        ([{"name": "x", "parameters": {"travel": _mm(1)}}], "overrides 'travel', which the layout"),
        (
            [{"name": "x", "substitutions": [{**_motor(40), "id": "gearbox"}]}],
            "substitutes 'gearbox', which is not a definition",
        ),
    ],
)
def test_a_variant_naming_what_is_not_there_is_refused(variants, message):
    with pytest.raises(ProductError, match=message):
        parse_product(_stage(variants))


def test_an_unknown_variant_is_refused_listing_those_declared():
    with pytest.raises(ProductError, match=r"no variant 'short' \(long\)"):
        resolve_variant(parse_product(_stage([_LONG])), "short")
