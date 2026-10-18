"""A product through the existing build tool: the summary tree, then one node by its path.

The product is the card tests' stage, whose two drives each hold a motor and a bracket
that meet: the summary names the failing paths, and one more call reads one drive's card.
"""

from __future__ import annotations

import pytest

pytest.importorskip("build123d")
jsonschema = pytest.importorskip("jsonschema")

from anvilate.mcp import handle_request, tool_catalog  # noqa: E402
from test_mcp import _released_registry  # noqa: E402
from test_product_cards import _box, _definition, _drive, _seat  # noqa: E402


def _stage() -> dict:
    return {
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(400, 100, 10, 3.0)),
                        _definition("drive", product="drive")],
        "instances": [{"name": "base", "item": "base"},
                      {"name": "drive", "item": "drive",
                       "pattern": {"kind": "linear", "count": 2, "direction": "x",
                                   "spacing": {"magnitude": 200, "unit": "mm"}}}],
        "ground": "base",
        "mates": _seat("drive", "base"),
    }  # fmt: skip


def _call(arguments: dict) -> dict:
    params = {"name": "build_combination", "arguments": arguments}
    reply = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params})
    return reply


def _valid(result: dict) -> None:
    tool = {t.name: t for t in tool_catalog()}["build_combination"]
    validator = jsonschema.Draft202012Validator(tool.output_schema, registry=_released_registry())
    errors = [e.message for e in validator.iter_errors(result["structuredContent"])]
    assert not errors, errors


def test_a_product_build_answers_with_its_summary_tree():
    result = _call({"combination": _stage(), "library": [_drive()]})["result"]
    assert not result.get("isError")
    _valid(result)
    summary = result["structuredContent"]["product"]
    assert summary["status"] == "fail"
    failing = [n["path"] for n in summary["nodes"] if n["status"] == "fail"]
    assert failing == ["stage", "stage/drive[1]", "stage/drive[2]"]
    assert "build_combination with the same product and node PATH" in summary["more"]


def test_one_further_call_reads_one_nodes_full_card():
    result = _call({"combination": _stage(), "library": [_drive()], "node": "stage/drive[2]"})[
        "result"
    ]
    _valid(result)
    node = result["structuredContent"]["node"]
    assert node["path"] == "stage/drive[2]" and node["status"] == "fail"
    assert [c["path"] for c in node["children"]] == [
        "stage/drive[2]/plate",
        "stage/drive[2]/motor",
        "stage/drive[2]/bracket",
    ]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"combination": _stage()}, "the library does not hold"),
        ({"combination": _stage(), "library": [_drive()], "node": "stage/x"}, "no node 'stage/x'"),
    ],
)
def test_a_product_the_tool_cannot_place_is_refused(arguments, message):
    error = _call(arguments)["error"]
    assert error["code"] == -32602 and message in error["message"]


def test_library_and_node_are_for_products_only():
    import pathlib

    import yaml

    worked = pathlib.Path(__file__).resolve().parents[1] / "examples" / "combinations"
    combination = yaml.safe_load((worked / "collar_on_shaft.combination.yaml").read_text())
    error = _call({"combination": combination, "node": "x"})["error"]
    assert "library and node are for a product, which states" in error["message"]
