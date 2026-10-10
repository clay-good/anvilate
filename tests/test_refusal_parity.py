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
