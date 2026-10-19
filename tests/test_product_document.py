"""The product document as a published schema, and sub-documents by path or embedded.

The spec's two scenarios: a product with a layout, a pattern and two variants round-trips
unchanged; and a reference to a missing ``drive/drive.product.yaml`` is refused naming the
path and the item that references it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from anvilate._models import parse_yaml
from anvilate.product import ProductError, load_product, parse_product, product_tree
from test_product_cards import _box, _definition, _drive, _seat

_ROOT = Path(__file__).resolve().parents[1]
_STAGE = _ROOT / "examples" / "products" / "linear_stage.product.yaml"


def _stage_with_two_variants() -> dict:
    document = parse_yaml(_STAGE.read_text(encoding="utf-8"))
    document["variants"].append(
        {"name": "short", "parameters": {"rail_length": {"magnitude": 300, "unit": "mm"}}}
    )
    return document


def test_a_product_round_trips_unchanged():
    product = parse_product(_stage_with_two_variants())
    assert len(product.variants) == 2 and product.layout is not None
    assert any(i.pattern is not None for i in product.instances)
    dumped = product.model_dump(mode="json")
    again = parse_product(yaml.safe_load(yaml.safe_dump(dumped)))
    assert again == product and again.model_dump(mode="json") == dumped


def test_every_worked_product_holds_to_the_released_schema():
    jsonschema = pytest.importorskip("jsonschema")
    from anvilate.contracts import PRODUCT_DOCUMENT_SCHEMA_VERSION

    released = json.loads(
        (_ROOT / "docs" / "api" / "schemas" / "released"
         / f"product-document-{PRODUCT_DOCUMENT_SCHEMA_VERSION}.json").read_text()
    )  # fmt: skip
    assert (
        released["$id"] == f"urn:anvilate:schema:product-document:{PRODUCT_DOCUMENT_SCHEMA_VERSION}"
    )
    validator = jsonschema.Draft202012Validator(released)
    for path in sorted((_ROOT / "examples" / "products").glob("*.product.yaml")):
        product, _library = load_product(path)
        errors = [e.message for e in validator.iter_errors(product.model_dump(mode="json"))]
        assert not errors, (path.name, errors[:3])


def test_an_unknown_document_version_is_refused():
    document = _stage_with_two_variants()
    document["anvilate_product"] = "2.0.0"
    with pytest.raises(ProductError, match="not valid at anvilate_product"):
        parse_product(document)


def _stage(drive: object) -> dict:
    return {
        "anvilate_product": "1.0.0",
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(400, 100, 10, 3.0)),
                        _definition("drive", product=drive)],
        "instances": [{"name": "base", "item": "base"}, {"name": "drive", "item": "drive"}],
        "ground": "base",
        "mates": _seat("drive", "base"),
    }  # fmt: skip


def _write(path: Path, document: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_a_sub_product_is_read_by_its_relative_path(tmp_path):
    _write(tmp_path / "drive" / "drive.product.yaml", _drive())
    top = _write(tmp_path / "stage.product.yaml", _stage({"file": "drive/drive.product.yaml"}))
    product, library = load_product(top)
    assert product.definitions[1].product == "drive" and set(library) == {"drive"}
    paths = [node.path for node in product_tree(product, library=library).walk()]
    assert "stage/drive/motor" in paths


def test_a_sub_product_may_be_embedded_whole(tmp_path):
    top = _write(tmp_path / "stage.product.yaml", _stage(_drive()))
    product, library = load_product(top)
    assert product.definitions[1].product == "drive" and library["drive"].name == "drive"


def test_a_missing_sub_document_is_refused_naming_the_path_and_the_item(tmp_path):
    top = _write(tmp_path / "stage.product.yaml", _stage({"file": "drive/drive.product.yaml"}))
    with pytest.raises(ProductError) as refused:
        load_product(top)
    message = str(refused.value)
    assert "definition 'drive'" in message and "drive/drive.product.yaml" in message
    assert "cannot be read" in message


def test_files_that_contain_themselves_are_refused(tmp_path):
    drive = _drive()
    drive["definitions"].append(_definition("again", product={"file": "../stage.product.yaml"}))
    _write(tmp_path / "drive" / "drive.product.yaml", drive)
    top = _write(tmp_path / "stage.product.yaml", _stage({"file": "drive/drive.product.yaml"}))
    with pytest.raises(ProductError, match="the product files contain themselves"):
        load_product(top)


def test_two_different_sub_products_under_one_name_are_refused(tmp_path):
    other = copy.deepcopy(_drive())
    other["definitions"][0]["placeholder"]["mass"]["magnitude"] = 9.9
    stage = _stage(_drive())
    stage["definitions"].append(_definition("drive2", product=other))
    top = _write(tmp_path / "stage.product.yaml", stage)
    with pytest.raises(ProductError, match="two different sub-products are named 'drive'"):
        load_product(top)


def _reachable_models(root):
    import inspect
    import typing

    from pydantic import BaseModel

    found: list[type] = []

    def walk(annotation):
        for argument in typing.get_args(annotation):
            walk(argument)
        if (inspect.isclass(annotation) and issubclass(annotation, BaseModel)
                and annotation not in found):  # fmt: skip
            found.append(annotation)
            for field in annotation.model_fields.values():
                walk(field.annotation)

    walk(root)
    return found


def test_every_model_a_product_document_reaches_states_requirements():
    """A product document is written outside this library, so every number in it is finite:
    an infinite caster rating passed every load, an infinite placeholder mass reached the
    roll-up, an infinite clearance passed every pair. The finite rule is opt-in per model
    and the walk trusts a sub-model to have checked itself, so the whole reachable graph
    opts in, and a model added to the document later cannot skip it."""
    from anvilate.product import Product
    from anvilate.units import Quantity

    models = [m for m in _reachable_models(Product) if m is not Quantity]
    assert len(models) >= 40
    assert [m.__name__ for m in models if not m.states_requirements] == []


def test_an_infinite_rating_or_placeholder_mass_is_refused():
    from anvilate.product import parse_product

    inf = {"magnitude": float("inf"), "unit": "kg"}
    document = {
        "name": "box",
        "definitions": [{"id": "body", "identity": {"description": "body", "source": "make"},
                         "placeholder": {"envelope": [{"magnitude": 10, "unit": "mm"}] * 3,
                                         "mass": inf, "reason": "not drawn yet"}}],
        "instances": [{"name": "body", "item": "body"}], "ground": "body",
    }  # fmt: skip
    with pytest.raises(ValueError, match="not a number a document can state"):
        parse_product(document)
