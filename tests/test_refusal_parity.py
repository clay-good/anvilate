"""One mistake is refused in the same words on the command line and over MCP.

audit-agent-surface 4.3. An agent that reads a refusal from `run_validation` and a person
who reads it from `anvilate check` are fixing the same document, and a sentence that
differs between them is two things to learn. Each mistake here is made once and sent
through both doors: what the MCP server says, less the argument it names, has to be on the
command line's standard error word for word.

It also holds what a refusal must not be (4.1): pydantic's own report, with the model's
name, a dump of the input and a URL. The build path printed exactly that for an element
its model refused, and the dump differed between the two surfaces.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")

from anvilate.mcp import handle_request  # noqa: E402
from cli_output import run_cli  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "parts"

# What a refusal is never made of: a library's internals in place of a sentence.
_NOT_A_SENTENCE = (
    "errors.pydantic.dev",
    "input_value=",
    "validation error for",
    "Traceback",
    "signed_fields",
)
# The longest any of these refusals runs, with room: the unknown-element refusal lists every
# module and element, and is the long one. A refusal past this is a page, not an answer.
_LONGEST = 2000


def _mm(value: float) -> dict:
    return {"magnitude": value, "unit": "mm"}


def _lug(change) -> dict:
    document = yaml.safe_load((_EXAMPLES / "lifting_lug.spec.yaml").read_text(encoding="utf-8"))
    document["constraints"] = {"min_safety_factor": {"value": 2.0, "origin": "user_stated"}}
    change(document)
    return document


def _lid(change) -> dict:
    document = yaml.safe_load((_EXAMPLES / "enclosure_lid.spec.yaml").read_text(encoding="utf-8"))
    change(document)
    return document


def _swap(params: dict, old: str, new: str) -> None:
    params[new] = params.pop(old)


_SCREENED = {
    "an element nobody screens": _lug(lambda d: d.update(element_type="lifting_lugg")),
    "a required field left out": _lug(lambda d: d["element_params"].pop("thickness")),
    "a field misspelled": _lug(lambda d: _swap(d["element_params"], "thickness", "thicknes")),
    "a length where a force goes": _lug(lambda d: d["element_params"].update(load=_mm(50))),
    "a unit nobody defines": _lug(
        lambda d: d["element_params"].update(width={"magnitude": 80, "unit": "mmm"})
    ),
    "a negative size": _lug(lambda d: d["element_params"].update(thickness=_mm(-12))),
    "a hole wider than the lug": _lug(lambda d: d["element_params"].update(hole_diameter=_mm(90))),
    "a value with no origin": _lug(lambda d: d.update(units={"value": "SI"})),
    "a quantity written as text": _lug(lambda d: d["element_params"].update(load="50 kN")),
    "no material": _lug(lambda d: d.pop("material")),
}

_BUILT = {
    "a hole standing on the lip": _lid(
        lambda d: d["element_params"]["hole_patterns"][0].update(pitch_x=_mm(108))
    ),
    "a lip with no opening": _lid(lambda d: d["element_params"].update(lip_wall=_mm(37))),
    "a lip stated in part": _lid(lambda d: d["element_params"].pop("lip_wall")),
    "an element nobody draws": _lid(lambda d: d.update(element_type="lid")),
    "a required field left out": _lid(lambda d: d["element_params"].pop("thickness")),
    "a field misspelled": _lid(lambda d: _swap(d["element_params"], "thickness", "thicknes")),
    "a force where a length goes": _lid(
        lambda d: d["element_params"].update(thickness={"magnitude": 3.0, "unit": "kN"})
    ),
    "a negative size": _lid(lambda d: d["element_params"].update(thickness=_mm(-3))),
    "a quantity written as text": _lid(lambda d: d["element_params"].update(width="120 mm")),
    "no material": _lid(lambda d: d.pop("material")),
}


def _call(tool: str, document: dict) -> dict:
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": {"spec": copy.deepcopy(document)}},
        }
    )


def _sentences(reply: dict, *prefixes: str) -> list[str]:
    """What an MCP refusal says, one string per issue, less the argument each names."""
    said = []
    for issue in reply["error"]["data"].get("issues") or [reply["error"]["message"]]:
        for prefix in prefixes:
            issue = issue.removeprefix(prefix)
        said.append(issue)
    return said


def _held(text: str, where: str) -> None:
    for fragment in _NOT_A_SENTENCE:
        assert fragment not in text, f"{where}: {fragment!r} is in the refusal: {text[:300]}"
    assert len(text) <= _LONGEST, f"{where}: a {len(text)}-character refusal"


def test_the_corpora_are_mistakes():
    """The floor: every document here is refused or not passed, on both surfaces' terms."""
    assert len(_SCREENED) >= 10 and len(_BUILT) >= 10


@pytest.mark.parametrize("mistake", _SCREENED)
def test_a_mistake_is_screened_in_the_same_words_on_both_surfaces(mistake, tmp_path):
    document = _SCREENED[mistake]
    path = tmp_path / "part.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    code, _out, err = run_cli("check", str(path))
    reply = _call("run_validation", document)
    assert code != 0, "the command line passed a mistake"
    _held(err, "anvilate check")
    if "error" in reply:
        assert code == 3
        said = _sentences(reply, "spec.")
    else:
        card = reply["result"]["structuredContent"]["scorecard"]
        said = [entry["detail"] for entry in card["entries"] if entry["status"] != "pass"]
        assert card["status"] != "pass"
    assert said, "the MCP server said nothing about a mistake"
    for sentence in said:
        _held(sentence, "run_validation")
        assert sentence in err, f"MCP says {sentence!r}; the command line says {err!r}"


@pytest.mark.parametrize("mistake", _BUILT)
def test_a_mistake_is_refused_a_build_in_the_same_words_on_both_surfaces(mistake, tmp_path):
    document = _BUILT[mistake]
    path = tmp_path / "part.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    code, _out, err = run_cli("build", str(path), "--output", str(tmp_path / "part.step"))
    reply = _call("build_part", document)
    assert code in (3, 4) and "error" in reply and not (tmp_path / "part.step").exists()
    _held(err, "anvilate build")
    for sentence in _sentences(reply, "spec.element_params: ", "spec."):
        _held(sentence, "build_part")
        assert sentence in err, f"MCP says {sentence!r}; the command line says {err!r}"


@pytest.mark.parametrize(
    ("corpus", "mistake", "command", "tool", "shown"),
    [
        (
            _SCREENED,
            "a length where a force goes",
            "check",
            "run_validation",
            "write `load` as a force, such as `{magnitude: 5, unit: kN}`",
        ),
        (
            _BUILT,
            "a force where a length goes",
            "build",
            "build_part",
            "write `thickness` as a length, such as `{magnitude: 6, unit: mm}`",
        ),
    ],
)
def test_a_value_of_the_wrong_kind_is_shown_a_valid_one(
    corpus, mistake, command, tool, shown, tmp_path
):
    """The spec's own scenario: a thickness given as a force is told what a length looks like.

    The refusal used to say what was wrong and stop. It names the field, the kind it takes
    and a value of that kind as a document writes one, on both doors.
    """
    document = corpus[mistake]
    path = tmp_path / "part.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    arguments = (command, str(path))
    if command == "build":
        arguments += ("--output", str(tmp_path / "part.step"))
    _code, _out, err = run_cli(*arguments)
    reply = _call(tool, document)
    said = (
        " ".join(_sentences(reply, "spec.element_params: ", "spec."))
        if "error" in reply
        else " ".join(
            e["detail"] for e in reply["result"]["structuredContent"]["scorecard"]["entries"]
        )
    )
    assert shown in err and shown in said


def test_the_example_follows_from_the_kind_the_refusal_names():
    from anvilate.spec.validate import _a_valid_quantity

    assert _a_valid_quantity("width must be a [length] quantity; got 5 kN") == (
        "write `width` as a length, such as `{magnitude: 6, unit: mm}`"
    )
    assert _a_valid_quantity("Value error, net_area must be an area ([length]**2); got 5 mm") == (
        "write `net_area` as an area, such as `{magnitude: 600, unit: mm**2}`"
    )
    assert "MPa" in _a_valid_quantity("allowable_shear must be a stress; got 1 kN ([force])")
    # A refusal that names no kind, or a kind with no example recorded, is left as it is.
    assert _a_valid_quantity("thickness must not be negative; got -3 mm") is None
    assert _a_valid_quantity("ratio must be a [dimensionless] quantity; got 5 mm") is None


def test_every_required_element_field_left_out_is_shown_a_value_to_write():
    """Over every element a spec can declare, and every field each requires.

    Leaving a required field out is refused naming the field, and with the value the
    element's own shipped example gives it, so the refusal shows what to write and not only
    that something is missing. A value too long for a sentence (a list of steps) is pointed
    to instead, and those are counted, so the rule cannot quietly stop applying.
    """
    import json

    from anvilate.screening import element_registry
    from anvilate.spec.validate import _element_reasons

    examples = json.loads(
        (
            Path(__file__).resolve().parents[1] / "src/anvilate/packs/element_examples.json"
        ).read_text("utf-8")
    )
    shown, too_long, checked = 0, [], 0
    for tag, (model, _screen) in element_registry().items():
        required = [name for name, field in model.model_fields.items() if field.is_required()]
        for name in required:
            params = {key: value for key, value in examples[tag].items() if key != name}
            try:
                model.model_validate(params)
            except ValueError as refused:
                said = _element_reasons(refused, model, tag)
            else:  # pragma: no cover - a required field cannot be left out
                raise AssertionError(f"{tag}.{name} is required and was not missed")
            checked += 1
            assert f"{name}: Field required" in said and f"add `{name}`" in said, (tag, name)
            if f", for example `{name}: " in said:
                shown += 1
            else:
                assert f"`anvilate parts {tag}` and the describe_part tool show `{name}`" in said
                too_long.append(f"{tag}.{name}")
    assert checked > 200, f"only {checked} required fields were tried"
    # A section, a list of steps or members, a timber grade: each a paragraph, so each is
    # pointed to. Seven of them; a longer list means the examples grew, and is looked at.
    assert len(too_long) <= 7, too_long
    assert shown == checked - len(too_long)
