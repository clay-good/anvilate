"""Content-keyed rebuilds: change one item, rebuild one, and agree with a cold build.

A stage of a base, a catalog mounting plate and two drive modules (a plate, a motor and a
bracket each) holds five distinct items. Changing the motor's mass changes one item's
content, so a warm rebuild builds one and reuses four, and its result is the cold build's.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")

import anvilate.geometry  # noqa: E402
from anvilate.product import BuildCache, ProductError, parse_product, place_product  # noqa: E402

_PLATE = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "examples" / "parts" / "mounting_plate.spec.yaml")
    .read_text()
)  # fmt: skip


def _box(x: float, y: float, z: float, kg: float) -> dict:
    return {"envelope": [{"magnitude": v, "unit": "mm"} for v in (x, y, z)],
            "mass": {"magnitude": kg, "unit": "kg"}, "reason": "not yet detailed"}  # fmt: skip


def _definition(id_: str, **kind) -> dict:
    return {"id": id_, "identity": {"description": id_, "source": "make"}, **kind}


def _seat(part: str, on: str, flush: str = "left") -> list[dict]:
    return [
        {"id": f"{part}-sit", "kind": "face_to_face", "place": {"part": part, "face": "bottom"},
         "on": {"part": on, "face": "top"}},
        {"id": f"{part}-{flush}", "kind": "edge_flush", "place": {"part": part, "face": flush},
         "on": {"part": on, "face": flush}},
        {"id": f"{part}-front", "kind": "edge_flush", "place": {"part": part, "face": "front"},
         "on": {"part": on, "face": "front"}},
    ]  # fmt: skip


def _drive(motor_kg: float = 0.9) -> dict:
    parts = [("plate", _box(80, 60, 8, 0.6)), ("motor", _box(40, 40, 50, motor_kg)),
             ("bracket", _box(20, 20, 20, 0.1))]  # fmt: skip
    return {
        "name": "drive",
        "definitions": [_definition(n, placeholder=b) for n, b in parts],
        "instances": [{"name": n, "item": n} for n, _ in parts],
        "ground": "plate",
        "mates": [*_seat("motor", "plate"), *_seat("bracket", "plate", "right")],
    }


def _place(motor_kg: float = 0.9, cache: BuildCache | None = None):
    stage = parse_product({
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(600, 150, 10, 3.0)),
                        _definition("mount", spec=copy.deepcopy(_PLATE)),
                        _definition("drive", product="drive")],
        "instances": [{"name": "base", "item": "base"},
                      {"name": "mount", "item": "mount"},
                      {"name": "drive", "item": "drive",
                       "pattern": {"kind": "linear", "count": 2, "direction": "x",
                                   "spacing": {"magnitude": 200, "unit": "mm"}}}],
        "ground": "base",
        "mates": [*_seat("mount", "base", "right"), *_seat("drive", "base")],
    })  # fmt: skip
    return place_product(stage, library={"drive": parse_product(_drive(motor_kg))}, cache=cache)


def _same(a, b) -> bool:
    exclude = {"rebuilt", "reused"}
    return a.model_dump(mode="json", exclude=exclude) == b.model_dump(mode="json", exclude=exclude)


def test_a_change_to_one_item_rebuilds_that_item_alone(monkeypatch):
    builds: list[str] = []
    real = anvilate.geometry.build_spec

    def counted(spec, **kw):
        builds.append(spec.name)
        return real(spec, **kw)

    monkeypatch.setattr(anvilate.geometry, "build_spec", counted)
    cache = BuildCache()
    first = _place(cache=cache)
    assert (first.rebuilt, first.reused, len(cache)) == (5, 0, 5)
    assert builds == ["motor-mounting-plate"]
    second = _place(motor_kg=1.2, cache=cache)
    assert (second.rebuilt, second.reused) == (1, 4)
    assert builds == ["motor-mounting-plate"]  # the catalog part was not built again
    assert "1 of 5 items built, 4 reused" in str(second)
    assert second.mass_kg == pytest.approx(first.mass_kg + 2 * 0.3)


def test_a_warm_rebuild_is_the_cold_build():
    cache = BuildCache()
    _place(cache=cache)
    warm, cold = _place(motor_kg=1.2, cache=cache), _place(motor_kg=1.2)
    assert (cold.rebuilt, cold.reused) == (5, 0)
    assert _same(warm, cold) and warm.card == cold.card


def test_an_unchanged_product_reuses_everything_and_is_the_same():
    cache = BuildCache()
    first = _place(cache=cache)
    again = _place(cache=cache)
    assert (again.rebuilt, again.reused) == (0, 5) and _same(first, again)


def test_a_cache_is_a_build_cache():
    with pytest.raises(ProductError, match="cache is a dict; pass a BuildCache"):
        _place(cache={})  # type: ignore[arg-type]
