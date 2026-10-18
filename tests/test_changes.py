"""Product change control: the spec's scenarios, compared revision by revision."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from anvilate._models import parse_yaml  # noqa: E402
from anvilate.changes import compare_products  # noqa: E402
from anvilate.product import parse_product  # noqa: E402
from test_product_cards import _box, _definition, _drive, _seat  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]


def _stage(rail_length: float) -> dict:
    document = parse_yaml(
        (_ROOT / "examples" / "products" / "linear_stage.product.yaml").read_text()
    )
    document["layout"]["parameters"][0]["value"]["magnitude"] = rail_length
    return document


def _by_item(record) -> dict:
    return {item.item: item for item in record.items}


def test_a_longer_stroke_changes_the_rail_and_the_stage_and_not_the_motor():
    record = compare_products(parse_product(_stage(450)), parse_product(_stage(520)))
    items = _by_item(record)
    rail = items["rail"]
    assert rail.status == "changed" and rail.classes == ("form",) and rail.flag == "new_revision"
    assert any(c.startswith("geometry: volume") and "450 × 15 × 15 → 520 × 15 × 15" in c
               for c in rail.changes)  # fmt: skip
    # the product's two rails, and the two of its long variant
    assert rail.where_used == tuple(
        f"{stage}/rail[{k}]" for stage in ("linear-stage", "linear-stage-long") for k in (1, 2)
    )
    assert items["motor"].status == "unchanged" and items["base"].status == "unchanged"
    assert items["linear-stage"].status == "changed"
    assert record.mass_after_kg == pytest.approx(record.mass_before_kg)  # a placeholder's mass


def _mm(value: float) -> dict:
    return {"magnitude": value, "unit": "mm"}


def _housing(bore: float, pocket: bool = False) -> dict:
    plate = copy.deepcopy(parse_yaml(
        (_ROOT / "examples" / "parts" / "mounting_plate.spec.yaml").read_text()))  # fmt: skip
    if pocket:
        plate["element_params"]["holes"].append(
            {"tag": "lighten", "x": _mm(30), "y": _mm(0), "diameter": _mm(12)}
        )
    housing = _box(80, 80, 30, 0.8)
    housing["interfaces"] = [{"name": "bearing_bore", "kind": "bore", "axis": "z",
                              "parameters": {"diameter": _mm(bore)}}]  # fmt: skip
    return {
        "name": "gearbox",
        "definitions": [
            _definition("plate", spec=plate),
            _definition("housing", placeholder=housing),
        ],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "housing", "item": "housing"}],
        "ground": "plate",
        "mates": _seat("housing", "plate"),
        "open_interfaces": [{"at": "housing.bearing_bore", "reason": "bearing not yet chosen"}],
    }


def test_a_grown_bore_is_a_fit_change_flagged_for_a_new_part_number():
    record = compare_products(parse_product(_housing(47)), parse_product(_housing(52)))
    housing = _by_item(record)["housing"]
    assert housing.classes == ("fit",) and housing.flag == "new_part_number"
    assert housing.evidence[0] == "interface bearing_bore"
    assert any("diameter 47 mm" in c and "diameter 52 mm" in c for c in housing.changes)
    assert _by_item(record)["plate"].status == "unchanged"


def test_a_pocket_for_weight_is_a_form_change_flagged_for_a_revision():
    record = compare_products(parse_product(_housing(47)), parse_product(_housing(47, pocket=True)))
    plate = _by_item(record)["plate"]
    assert plate.classes == ("form",) and plate.flag == "new_revision"
    assert any(c.startswith("element_params.holes[1].tag: absent → lighten") for c in plate.changes)
    assert (
        record.mass_after_kg < record.mass_before_kg
    )  # the plate is steel, and lost a hole's worth


def _stage_of_drives() -> dict:
    return {
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(900, 100, 10, 3.0)),
                        _definition("drive", product="drive")],
        "instances": [{"name": "base", "item": "base"},
                      {"name": "drive", "item": "drive",
                       "pattern": {"kind": "linear", "count": 4, "direction": "x",
                                   "spacing": {"magnitude": 200, "unit": "mm"}}}],
        "ground": "base",
        "mates": _seat("drive", "base"),
    }  # fmt: skip


def test_a_bracket_shared_by_four_drives_lists_its_four_paths():
    stage = parse_product(_stage_of_drives())
    old_drive, new_drive = _drive(), _drive()
    new_drive["definitions"][2]["placeholder"]["envelope"][2]["magnitude"] = 25
    record = compare_products(stage, stage,
                              library_before={"drive": parse_product(old_drive)},
                              library_after={"drive": parse_product(new_drive)})  # fmt: skip
    bracket = _by_item(record)["drive/bracket"]
    assert bracket.status == "changed"
    assert bracket.where_used == tuple(f"stage/drive[{k}]/bracket" for k in range(1, 5))
    assert _by_item(record)["drive/motor"].status == "unchanged"


def test_the_record_is_markdown_and_json_and_says_when_its_reason_is_missing():
    before, after = parse_product(_housing(47)), parse_product(_housing(52))
    record = compare_products(before, after)
    text = record.to_markdown()
    assert "Reason: **reason missing**" in text
    assert "| housing |" in text and "new part number" in text
    dumped = json.loads(record.model_dump_json())
    assert dumped["reason"] is None and dumped["items"][0]["item"] == "gearbox"
    given = compare_products(before, after, reason="customer bearing upgrade, ECR-114")
    assert "Reason: customer bearing upgrade, ECR-114" in given.to_markdown()


def test_the_docs_page_states_the_classes_the_code_assigns():
    import re

    page = (_ROOT / "docs" / "changes.md").read_text()
    rows = dict(re.findall(r"^\| `(fit|function|form)` \| [^|]+ \| `(\w+)` \|", page, re.M))
    assert rows == {"fit": "new_part_number", "function": "new_part_number",
                    "form": "new_revision"}  # fmt: skip
