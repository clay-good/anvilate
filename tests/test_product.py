"""Product structure: definitions placed as instances, identity, paths, parts list."""

from __future__ import annotations

import pytest

from anvilate.product import (
    ItemSource,
    ProductError,
    parse_product,
    parts_list,
    product_tree,
)


def _placeholder(reason: str = "motor not yet chosen") -> dict:
    return {
        "envelope": [{"magnitude": 60, "unit": "mm"}] * 3,
        "mass": {"magnitude": 0.8, "unit": "kg"},
        "reason": reason,
    }


def _definition(id_: str, *, number: str | None = None, description: str = "", **kind) -> dict:
    identity = {"description": description or id_, "source": "make"}
    if number:
        identity["part_number"] = number
    return {"id": id_, "identity": identity, **kind}


def _drive() -> dict:
    return {
        "name": "drive",
        "definitions": [
            _definition("plate", number="100-0001", placeholder=_placeholder("plate not drawn")),
            _definition("motor", number="200-0001", placeholder=_placeholder()),
        ],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "motor", "item": "motor"}],
        "ground": "plate",
    }


def _stage(**overrides) -> dict:
    document = {
        "name": "stage",
        "definitions": [
            _definition("base", number="300-0001", placeholder=_placeholder("base not drawn")),
            _definition("drive", number="400-0001", product="drive"),
            _definition("foot", number="500-0001", placeholder=_placeholder("foot not drawn")),
        ],
        "instances": [
            {"name": "base", "item": "base"},
            {"name": "drive", "item": "drive",
             "pattern": {"kind": "linear", "count": 2, "spacing": {"magnitude": 200, "unit": "mm"},
                         "direction": "x"}},
            {"name": "foot", "item": "foot",
             "pattern": {"kind": "linear", "count": 4, "spacing": {"magnitude": 100, "unit": "mm"},
                         "direction": "y"}},
        ],
        "ground": "base",
    }  # fmt: skip
    document.update(overrides)
    return document


def _library() -> dict:
    return {"drive": parse_product(_drive())}


def test_a_sub_assembly_is_placed_as_one_item():
    tree = product_tree(parse_product(_stage()), library=_library())
    paths = [n.path for n in tree.walk()]
    assert "stage/drive[2]/motor" in paths and "stage/drive[1]/plate" in paths
    # the drive's own instances are not restated in the stage document
    assert [d["id"] for d in _stage()["definitions"]] == ["base", "drive", "foot"]


def test_four_feet_from_one_definition():
    lines = {line.part_number: line for line in parts_list(product_tree(
        parse_product(_stage()), library=_library()))}  # fmt: skip
    assert lines["500-0001"].quantity == 4
    assert lines["200-0001"].quantity == 2  # a motor in each of two drives
    assert lines["400-0001"].quantity == 2 and lines["400-0001"].kind == "product"


def test_paths_do_not_depend_on_sibling_order():
    forward = product_tree(parse_product(_stage()), library=_library())
    document = _stage()
    document["instances"] = list(reversed(document["instances"]))
    backward = product_tree(parse_product(document), library=_library())
    assert sorted(n.path for n in forward.walk()) == sorted(n.path for n in backward.walk())


def test_provisional_numbers_are_visible_and_deterministic():
    document = _stage()
    document["definitions"][2]["identity"].pop("part_number")
    tree = product_tree(parse_product(document), library=_library())
    (foot,) = [line for line in parts_list(tree) if line.description == "foot"]
    assert foot.provisional and foot.part_number.startswith("PROV-")
    assert "(provisional)" in str(foot)
    again = product_tree(parse_product(document), library=_library())
    assert [n.part_number for n in again.walk()] == [n.part_number for n in tree.walk()]


def test_a_duplicated_part_number_is_refused_naming_both_paths():
    document = _stage()
    document["definitions"][2]["identity"]["part_number"] = "300-0001"  # the base's number
    with pytest.raises(ProductError, match="300-0001.*'stage/base'.*'stage/foot\\[1\\]'"):
        product_tree(parse_product(document), library=_library())


def test_a_product_that_contains_itself_is_refused_before_any_geometry():
    a = parse_product({"name": "a", "definitions": [_definition("b", product="b")],
                       "instances": [{"name": "b", "item": "b"}], "ground": "b"})  # fmt: skip
    b = parse_product({"name": "b", "definitions": [_definition("a", product="a")],
                       "instances": [{"name": "a", "item": "a"}], "ground": "a"})  # fmt: skip
    with pytest.raises(ProductError, match="contains itself: a → b → a"):
        product_tree(a, library={"a": a, "b": b})


def test_a_mirrored_bracket_needs_its_own_definition():
    document = _stage()
    document["instances"][0]["mirrored"] = True
    with pytest.raises(ProductError, match="its own definition and part number"):
        parse_product(document)


def test_a_sub_product_the_library_does_not_hold():
    with pytest.raises(ProductError, match="the library does not hold"):
        product_tree(parse_product(_stage()), library={})


@pytest.mark.parametrize(
    ("change", "match"),
    [({"ground": "nowhere"}, "ground"),
     ({"instances": [{"name": "x", "item": "missing"}], "ground": "x"}, "not a definition"),
     ({"instances": [{"name": "a/b", "item": "base"}], "ground": "a/b"}, "path"),
     ({"definitions": [{"id": "z", "identity": {"description": "z", "source": "make"}}]},
      "exactly one")],
)  # fmt: skip
def test_document_refusals(change, match):
    with pytest.raises(ProductError, match=match):
        parse_product(_stage(**change))


def test_a_bought_item_keeps_its_source():
    document = _drive()
    document["definitions"][1]["identity"]["source"] = "buy"
    lines = parts_list(product_tree(parse_product(document)))
    assert {line.part_number: line.source for line in lines}["200-0001"] is ItemSource.BUY


def test_a_node_renders_its_path_number_and_kind():
    tree = product_tree(parse_product(_stage()), library=_library())
    motor = next(n for n in tree.walk() if n.path == "stage/drive[2]/motor")
    assert str(motor) == "stage/drive[2]/motor: 200-0001 motor [placeholder]"
