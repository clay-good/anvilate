"""A product through the existing build tool: the summary tree, then one node by its path.

The product is the card tests' stage, whose two drives each hold a motor and a bracket
that meet: the summary names the failing paths, and one more call reads one drive's card.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

pytest.importorskip("build123d")
jsonschema = pytest.importorskip("jsonschema")

from anvilate._models import parse_yaml  # noqa: E402
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


# --- The "design a product" journey, walked call by call (guided design journey 4.1) ------
#
# Offline: every call here goes through the server's own request handler in this process,
# and the two specs are read from files in this repository.

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "products"
_REDUCER = _EXAMPLES / "gear_reducer.product.yaml"


def _screened_shaft(name: str) -> dict:
    """The worked reducer's output-shaft spec, renamed: a part that screens to a verdict."""
    document = parse_yaml(_REDUCER.read_text(encoding="utf-8"))
    spec = copy.deepcopy(next(d for d in document["definitions"] if d["id"] == "shaft")["spec"])
    spec["name"] = name
    return spec


def _rig(detailed: bool) -> dict:
    """Two items on a plate; the second is a placeholder until ``detailed`` says otherwise."""

    def made(id_: str, spec: dict) -> dict:
        return {"id": id_, "identity": {"description": id_, "source": "make"}, "spec": spec}

    block = (made("block", _screened_shaft("upper-shaft")) if detailed
             else _definition("block", placeholder=_box(60, 60, 140, 1.1)))  # fmt: skip
    return {
        "name": "rig",
        "definitions": [made("base", _screened_shaft("lower-shaft")), block],
        "instances": [{"name": "base", "item": "base"}, {"name": "block", "item": "block"}],
        "ground": "base",
        "mates": _seat("block", "base"),
    }


def test_the_design_a_product_journey_is_walked_call_by_call():
    """Two calls, and the second is the step the first one named.

    The point is not that the stage advances — it is that an agent with nothing but the
    result can tell what to do next, do exactly that, and see the gap it was told about
    close. So the walk reads the step out of the first result rather than knowing it, and
    the assertions below are about what CHANGED between the two.
    """
    first = _call({"combination": _rig(detailed=False)})["result"]
    assert not first.get("isError")
    _valid(first)
    before = first["structuredContent"]

    # Where it is, and what holds the next stage back.
    assert before["journey"]["stage"] == "described"
    screened = next(s for s in before["journey"]["stages"] if s["stage"] == "screened")
    assert screened["state"] == "not_reached"
    assert screened["gaps"] == ["rig/block placeholder has no verdict"]
    # The whole-product checks come back too, and they are not what holds it back.
    assert before["whole_product"]["status"] == "pass"

    # What to do about it, read from the result and not chosen here.
    step = before["next"]["steps"][0]
    assert step["tool"] == "build_combination"
    assert step["arguments"] == {"declare": "definitions[].spec"}
    assert "in place of its placeholder" in step["reason"]

    # Do that, and only that: the placeholder becomes a spec. Then call the tool it named.
    second = _call({"combination": _rig(detailed=True)})["result"]
    assert not second.get("isError")
    _valid(second)
    after = second["structuredContent"]

    assert after["journey"]["stage"] == "screened"
    assert next(s for s in after["journey"]["stages"] if s["stage"] == "screened")["gaps"] == []
    assert after["product"]["status"] == "pass"
    # And the step has moved on with it: nothing is held back now but the package itself.
    assert after["next"]["steps"][0]["tool"] == "export_artifact"
    assert "write the review package" in after["next"]["steps"][0]["reason"]
    review = next(s for s in after["journey"]["stages"] if s["stage"] == "review_ready")
    assert review["gaps"] == ["the review package is not written for this content"]
