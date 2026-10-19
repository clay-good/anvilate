"""Purchased components: records with sourced ratings, checked against what the product asks.

Hand calculations, Shigley's L10 = (C/P)^3 for a ball bearing with C = 14 kN at 1,500 rpm:

- P = 1.4 kN: (C/P)^3 = 1,000 million revolutions = 10^9 / (60 · 1500) = 11,111 h, short of
  a 20,000 h requirement (0.556);
- P = 1.0 kN: 14^3 = 2,744 million revolutions = 30,489 h, which meets it (1.524).
"""

from __future__ import annotations

import pytest

from anvilate.components import ComponentError, ComponentRecord, Demand, Rating, _rating_entries
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(v: float, unit: str) -> dict:
    return {"magnitude": v, "unit": unit}


def _record(family: str, ratings: dict[str, dict], **extra) -> ComponentRecord:
    return ComponentRecord.model_validate({
        "manufacturer": "Acme", "part_number": f"{family}-1", "description": family,
        "family": family, "suppliers": [{"supplier": "Distributor", "number": "D-1"}],
        "envelope": [_q(52, "mm"), _q(52, "mm"), _q(15, "mm")],
        "envelope_source": "datasheet p.1", "mass": _q(0.13, "kg"), "mass_source": "datasheet p.1",
        "ratings": [{"name": k, "value": v, "source": "datasheet p.2"} for k, v in ratings.items()],
        **extra,
    })  # fmt: skip


def _demands(**values: dict) -> tuple[Demand, ...]:
    return tuple(Demand(name=k, value=v, source="shaft analysis") for k, v in values.items())


_BEARING = {"dynamic_load_rating": _q(14, "kN")}


@pytest.mark.parametrize(
    ("load_kn", "status", "ratio"),
    [(1.4, CheckStatus.FAIL, 0.5556), (1.0, CheckStatus.PASS, 1.5244)],
)
def test_a_bearing_is_checked_for_its_rating_life(load_kn, status, ratio):
    (entry,) = _rating_entries(
        _record("ball_bearing", _BEARING),
        _demands(equivalent_load=_q(load_kn, "kN"), speed=_q(1500, "rpm"),
                 required_life=_q(20000, "hour")),
    )  # fmt: skip
    assert entry.name == "bearing rating life" and entry.status is status
    assert entry.derivation is not None
    hours = entry.derivation.result.value
    assert hours / 20000 == pytest.approx(ratio, rel=1e-3)
    assert "datasheet p.2" in entry.detail and "shaft analysis" in entry.detail


def test_a_motor_coupling_guide_and_gas_spring_check_their_ratings():
    motor = _rating_entries(_record("motor", {"rated_torque": _q(1.26, "N*m")}),
                           _demands(torque=_q(0.9, "N*m")))  # fmt: skip
    assert motor[0].status is CheckStatus.PASS and motor[
        0
    ].derivation.result.value == pytest.approx(1.4)
    guide = _rating_entries(
        _record("linear_guide", {"stroke": _q(300, "mm"), "dynamic_load_rating": _q(8, "kN")}),
        _demands(stroke=_q(330, "mm"), load=_q(2, "kN")),
    )
    assert [(e.name, e.status) for e in guide] == [
        ("guide stroke", CheckStatus.FAIL),
        ("guide load", CheckStatus.PASS),
    ]
    spring = _rating_entries(
        _record("gas_spring", {"force": _q(400, "N")}), _demands(force=_q(450, "N"))
    )
    assert spring[0].status is CheckStatus.FAIL


def test_a_demand_the_product_does_not_state_is_not_evaluated_and_named():
    (entry,) = _rating_entries(_record("ball_bearing", _BEARING), _demands(speed=_q(1500, "rpm")))
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "equivalent load, required life" in entry.detail
    assert {n.declaration for n in entry.needs} == {
        "definitions[].demands[equivalent_load]",
        "definitions[].demands[required_life]",
    }


def test_an_unsourced_component_is_never_released():
    record = _record("motor", {"rated_torque": _q(1.26, "N*m")}, suppliers=[])
    assert not record.sourced
    entries = _rating_entries(record, _demands(torque=_q(0.9, "N*m")))
    sourcing = next(e for e in entries if e.name == "sourcing")
    assert sourcing.status is CheckStatus.NOT_EVALUATED and "names no supplier" in sourcing.detail


@pytest.mark.parametrize(
    ("family", "ratings", "message"),
    [
        ("ball_bearing", {}, "states no dynamic_load_rating"),
        ("motor", {"rated_torque": _q(3, "N")}, "it is a positive"),
    ],
)
def test_a_record_must_state_its_familys_ratings(family, ratings, message):
    with pytest.raises(ValueError, match=message):
        _record(family, ratings)


def test_a_demand_the_family_does_not_read_is_refused():
    with pytest.raises(ComponentError, match=r"\['speed'\] is not one of them"):
        _rating_entries(_record("motor", {"rated_torque": _q(1, "N*m")}),
                       _demands(speed=_q(1500, "rpm")))  # fmt: skip


def test_a_component_in_a_product_is_placed_by_its_holes_and_carded():
    pytest.importorskip("build123d")
    from anvilate.product import parse_product, place_product

    def hole(tag, x, z, face):
        return {"tag": tag, "x": _q(x, "mm"), "y": _q(0, "mm"), "z": _q(z, "mm"), "face": face,
                "diameter": _q(5, "mm")}  # fmt: skip

    holes = [hole("m1", -20, -7.5, "bottom"), hole("m2", 20, -7.5, "bottom")]
    motor = _record("motor", {"rated_torque": _q(1.26, "N*m")}, holes=holes)
    product = parse_product({
        "name": "drive",
        "definitions": [
            {"id": "plate", "identity": {"description": "plate", "source": "make"},
             "placeholder": {"envelope": [_q(100, "mm"), _q(60, "mm"), _q(8, "mm")],
                             "mass": _q(0.4, "kg"), "reason": "not yet detailed",
                             "holes": [hole("p1", -20, 4, "top"), hole("p2", 20, 4, "top")]}},
            {"id": "motor", "identity": {"description": "motor", "source": "buy"},
             "component": motor.model_dump(mode="json"),
             "demands": [{"name": "torque", "value": _q(0.9, "N*m"), "source": "axis sizing"}]},
        ],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "motor", "item": "motor"}],
        "ground": "plate",
        "mates": [{"id": "bolted", "kind": "hole_pattern",
                   "place": {"part": "motor", "face": "bottom", "holes": ["m1", "m2"]},
                   "on": {"part": "plate", "face": "top", "holes": ["p1", "p2"]}}],
    })  # fmt: skip
    placed = place_product(product)
    body = next(b for b in placed.bodies if b.path == "drive/motor")
    assert body.box_min_mm[2] == pytest.approx(4) and body.mass_kg == pytest.approx(0.13)
    node = placed.card.find("drive/motor")
    assert node.kind == "component" and node.status is CheckStatus.PASS
    assert [e.name for e in node.entries] == ["motor torque"]


def test_a_component_is_bought_and_only_a_component_states_demands():
    from anvilate.product import ProductError, parse_product

    base = {"name": "p", "instances": [{"name": "a", "item": "a"}], "ground": "a"}
    record = _record("motor", {"rated_torque": _q(1, "N*m")}).model_dump(mode="json")
    with pytest.raises(ProductError, match="a component is bought"):
        parse_product({**base, "definitions": [
            {"id": "a", "identity": {"description": "a", "source": "make"}, "component": record}
        ]})  # fmt: skip
    with pytest.raises(ProductError, match="states demands and is not a component"):
        parse_product({**base, "definitions": [
            {"id": "a", "identity": {"description": "a", "source": "make"},
             "placeholder": {"envelope": [_q(1, "mm")] * 3, "mass": _q(1, "kg"), "reason": "r"},
             "demands": [{"name": "torque", "value": _q(1, "N*m"), "source": "s"}]}
        ]})  # fmt: skip


def test_the_docs_table_names_every_familys_ratings_and_demands():
    import re
    from pathlib import Path

    from anvilate.components import FAMILY_RATINGS

    page = (Path(__file__).resolve().parents[1] / "docs" / "components.md").read_text()
    rows = {}
    for families, ratings, demands in re.findall(
        r"^\| (`[^|]+`) \| ([^|]+) \| ([^|]+) \|", page, re.M
    ):
        for family in re.findall(r"`(\w+)`", families):
            rows[family] = (
                set(re.findall(r"`(\w+)`", ratings)),
                set(re.findall(r"`(\w+)`", demands)),
            )
    checked = {f: (set(r), set(d)) for f, (r, d) in FAMILY_RATINGS.items() if r}
    assert rows == checked


def test_the_docs_page_names_every_source_a_record_requires():
    """'Citing a datasheet' claims every stated value carries its source: the page's table
    is held to the Provenance fields the record, its ratings and its demands declare."""
    from pathlib import Path

    from anvilate.components import ComponentRecord, Demand, Price, Rating

    page = (Path(__file__).resolve().parents[1] / "docs" / "components.md").read_text()
    section = page.split("## Citing a datasheet")[1].split("\n## ")[0]
    # Keyed on the name: `Provenance` is an annotated `str`, so its annotation is `str`.
    sources = [
        (model.__name__, name)
        for model in (ComponentRecord, Rating, Demand, Price)
        for name, field in model.model_fields.items()
        if (name == "source" or name.endswith("_source")) and field.is_required()
    ]
    assert len(sources) == 5, sources
    for model_name, name in sources:
        assert f"`{name}`" in section, (model_name, name)
    assert "`date`" in section


def _vendor_step(folder):
    """A 57 × 57 × 76 motor body with four 5 mm blind holes, 10 deep, in its bottom face."""
    build123d = pytest.importorskip("build123d")
    from build123d import Align, Box, Cylinder, Location, export_step

    body = Box(57, 57, 76)
    for x in (-23.5, 23.5):
        for y in (-23.5, 23.5):
            hole = Cylinder(2.5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
            body = body - hole.moved(Location((x, y, -38)))
    path = folder / "motor.step"
    export_step(body, str(path))
    del build123d
    return path


def _drafted(path):
    from anvilate.components import draft_component
    from anvilate.units import Quantity

    return draft_component(
        path, manufacturer="Acme", part_number="23HS", description="stepper", family="motor",
        mass=Quantity(magnitude=1.0, unit="kg"), mass_source="datasheet p.1",
        ratings=(Rating(name="rated_torque", value=Quantity(magnitude=1.26, unit="N*m"),
                        source="datasheet p.2"),),
    )  # fmt: skip


def test_a_record_is_drafted_from_a_measured_vendor_model(tmp_path):
    record = _drafted(_vendor_step(tmp_path))
    assert [q.to("mm").magnitude for q in record.envelope] == pytest.approx([57, 57, 76])
    assert record.drafted and record.confirmed_by is None
    assert record.model.file == "motor.step" and len(record.model.sha256) == 64
    assert len(record.holes) == 4 and {h.face for h in record.holes} == {"bottom"}
    corners = sorted((h.x.magnitude, h.y.magnitude) for h in record.holes)
    assert corners == pytest.approx([(-23.5, -23.5), (-23.5, 23.5), (23.5, -23.5), (23.5, 23.5)])
    assert [h.z.magnitude for h in record.holes] == pytest.approx([-38.0] * 4)


def test_a_drafted_record_says_so_until_someone_confirms_it(tmp_path):
    record = _drafted(_vendor_step(tmp_path))
    names = {e.name: e.status for e in _rating_entries(record, root=tmp_path)}
    assert names["drafted record"] is CheckStatus.NOT_EVALUATED
    assert names["vendor model"] is CheckStatus.PASS
    confirmed = record.model_copy(update={"confirmed_by": "J. Engineer"})
    assert "drafted record" not in {e.name for e in _rating_entries(confirmed, root=tmp_path)}


def test_a_vendor_model_that_changed_or_is_absent_leaves_geometry_not_evaluated(tmp_path):
    path = _vendor_step(tmp_path)
    record = _drafted(path)

    def model_entry(root):
        return next(e for e in _rating_entries(record, root=root) if e.name == "vendor model")

    assert "no folder was given" in model_entry(None).detail
    path.write_text(path.read_text() + "\n", encoding="utf-8")
    changed = model_entry(tmp_path)
    assert (
        changed.status is CheckStatus.NOT_EVALUATED
        and "has changed since the record" in changed.detail
    )
    path.unlink()
    assert "not found in" in model_entry(tmp_path).detail


def test_a_vendor_model_that_does_not_fit_its_record_fails(tmp_path):
    record = _drafted(_vendor_step(tmp_path))
    wrong = record.model_copy(update={"envelope": (record.envelope[0], record.envelope[1],
                                                   Quantity(magnitude=82, unit="mm"))})  # fmt: skip
    entry = next(e for e in _rating_entries(wrong, root=tmp_path) if e.name == "vendor model")
    assert entry.status is CheckStatus.FAIL and "off by 6 mm" in entry.detail
