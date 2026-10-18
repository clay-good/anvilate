"""A card for every node of a product, rolled up: the spec's failure deep in the tree.

A drive module seats a motor and a bracket flush with the same corner of its plate, so
the two overlap inside it. The stage places two drives 200 mm apart on a 400 mm base:
the drives clear each other and the base, so each drive owns its clash, and the stage
fails only by reference to them.
"""

from __future__ import annotations

import pytest

pytest.importorskip("build123d")

from anvilate.product import NodeCard, ProductError, parse_product, place_product  # noqa: E402
from anvilate.scorecard import CheckStatus  # noqa: E402


def _box(x: float, y: float, z: float, kg: float) -> dict:
    return {"envelope": [{"magnitude": v, "unit": "mm"} for v in (x, y, z)],
            "mass": {"magnitude": kg, "unit": "kg"}, "reason": "not yet detailed"}  # fmt: skip


def _definition(id_: str, **kind) -> dict:
    return {"id": id_, "identity": {"description": id_, "source": "make"}, **kind}


def _seat(part: str, on: str) -> list[dict]:
    return [
        {"id": f"{part}-sit", "kind": "face_to_face", "place": {"part": part, "face": "bottom"},
         "on": {"part": on, "face": "top"}},
        {"id": f"{part}-left", "kind": "edge_flush", "place": {"part": part, "face": "left"},
         "on": {"part": on, "face": "left"}},
        {"id": f"{part}-front", "kind": "edge_flush", "place": {"part": part, "face": "front"},
         "on": {"part": on, "face": "front"}},
    ]  # fmt: skip


def _drive(clash: bool = True) -> dict:
    parts = [("plate", _box(80, 60, 8, 0.6)), ("motor", _box(40, 40, 50, 0.9))]
    if clash:
        parts.append(("bracket", _box(20, 20, 20, 0.1)))
    return {
        "name": "drive",
        "definitions": [_definition(n, placeholder=b) for n, b in parts],
        "instances": [{"name": n, "item": n} for n, _ in parts],
        "ground": "plate",
        "mates": [m for n, _ in parts[1:] for m in _seat(n, "plate")],
    }


def _stage(clash: bool = True):
    stage = parse_product({
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(400, 100, 10, 3.0)),
                        _definition("drive", product="drive")],
        "instances": [{"name": "base", "item": "base"},
                      {"name": "drive", "item": "drive",
                       "pattern": {"kind": "linear", "count": 2, "direction": "x",
                                   "spacing": {"magnitude": 200, "unit": "mm"}}}],
        "ground": "base",
        "mates": _seat("drive", "base"),
    })  # fmt: skip
    return place_product(stage, library={"drive": parse_product(_drive(clash))})


def test_every_node_has_a_card_in_tree_order():
    card = _stage().card
    assert [c.path for c in card.children] == ["stage/base", "stage/drive[1]", "stage/drive[2]"]
    drive = card.find("stage/drive[2]")
    assert drive.kind == "product"
    assert [c.path for c in drive.children] == [
        "stage/drive[2]/plate",
        "stage/drive[2]/motor",
        "stage/drive[2]/bracket",
    ]
    assert card.find("stage/drive[2]/motor").kind == "placeholder"


def test_a_clash_is_owned_by_the_node_whose_children_meet_and_referenced_above():
    card = _stage().card
    # the stage's own children clear each other: its interference passes
    assert card.entries[0].status is CheckStatus.PASS
    assert card.status is CheckStatus.FAIL
    for k in (1, 2):
        drive = card.find(f"stage/drive[{k}]")
        assert drive.entries[0].status is CheckStatus.FAIL
        assert f"stage/drive[{k}]/motor and stage/drive[{k}]/bracket" in drive.entries[0].detail
    failing = [(path, e.name) for path, e in card.findings() if e.status is CheckStatus.FAIL]
    assert failing == [("stage/drive[1]", "interference"), ("stage/drive[2]", "interference")]
    shown = str(card)
    assert "stage: fail by reference to " in shown.splitlines()[0]
    # stated once, at its owner
    assert shown.count("stage/drive[2]/motor and stage/drive[2]/bracket") == 1


def test_a_placeholder_is_never_a_pass_and_says_so_up_the_tree():
    placed = _stage(clash=False)
    card = placed.card
    assert card.find("stage/base").status is CheckStatus.NOT_EVALUATED
    assert "stands in for an undetailed item (not yet detailed)" in (
        card.find("stage/base").entries[0].detail
    )
    assert card.status is CheckStatus.NOT_EVALUATED  # every interference passed
    assert all(
        e.status is CheckStatus.PASS for path, e in card.findings() if e.name == "interference"
    )
    # each product node's interference names the placeholders under it, and only those
    detail = card.find("stage/drive[1]").entries[0].detail
    assert "provisional: 2 placeholders (stage/drive[1]/plate, stage/drive[1]/motor)" in detail
    assert "card not_evaluated" in str(placed)


def test_a_card_is_read_back_from_its_dump_unchanged():
    card = _stage().card
    dumped = card.model_dump(mode="json")
    assert dumped["status"] == "fail" and dumped["children"][1]["status"] == "fail"
    assert NodeCard.model_validate(dumped) == card


def test_a_path_not_in_the_tree_is_refused():
    with pytest.raises(ProductError, match="no node 'stage/drive\\[3\\]' under 'stage'"):
        _stage().card.find("stage/drive[3]")


def test_a_summary_past_its_bound_keeps_the_worst_and_counts_the_rest():
    from anvilate.product import product_tree, summarize_product

    stage = parse_product({
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(400, 100, 10, 3.0)),
                        _definition("drive", product="drive")],
        "instances": [{"name": "base", "item": "base"},
                      {"name": "drive", "item": "drive",
                       "pattern": {"kind": "linear", "count": 2, "direction": "x",
                                   "spacing": {"magnitude": 200, "unit": "mm"}}}],
        "ground": "base",
        "mates": _seat("drive", "base"),
    })  # fmt: skip
    library = {"drive": parse_product(_drive())}
    placed = place_product(stage, library=library)
    tree = product_tree(stage, library=library)
    whole = summarize_product(placed, tree)
    assert len(whole.nodes) == 10 and whole.omitted == 0
    cut = summarize_product(placed, tree, limit=4)
    # the three failing nodes, then the first not-evaluated one, in tree order
    assert [n.path for n in cut.nodes] == ["stage", "stage/base", "stage/drive[1]",
                                           "stage/drive[2]"]  # fmt: skip
    assert cut.omitted == 6 and "6 nodes not shown, none worse than those shown" in str(cut)
    root = cut.nodes[0]
    assert root.governing == "by reference to stage/drive[1], stage/drive[2]"
    assert root.part_number.startswith("PROV-") and root.provisional
    with pytest.raises(ProductError, match="a summary shows at least one node"):
        summarize_product(placed, tree, limit=0)
