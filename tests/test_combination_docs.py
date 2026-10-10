"""The combinations guide is held to the worked examples and the surfaces that build them.

add-part-combinations groups 4 and 5. One picture and one section for each worked
combination and no others; the picture is the one the tool draws; and the MCP tool and the
command build the same combination the library does.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")

_REPO = Path(__file__).resolve().parents[1]
_EXAMPLES = _REPO / "examples" / "combinations"
_NAMES = sorted(path.name.removesuffix(".combination.yaml") for path in _EXAMPLES.glob("*.yaml"))


def _document(name: str) -> dict:
    return yaml.safe_load((_EXAMPLES / f"{name}.combination.yaml").read_text(encoding="utf-8"))


def _call(name: str, arguments: dict) -> dict:
    from anvilate.mcp import handle_request

    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


def test_the_guide_has_one_section_and_one_picture_for_each_worked_combination():
    page = (_REPO / "docs" / "combinations.md").read_text(encoding="utf-8")
    assert len(_NAMES) == 5
    pictured = re.findall(r"!\[[^\]]+\]\(combinations/(\w+)\.png\)", page)
    linked = re.findall(r"\]\(\.\./examples/combinations/(\w+)\.combination\.yaml\)", page)
    assert sorted(pictured) == _NAMES and sorted(linked) == _NAMES
    on_disk = sorted(path.stem for path in (_REPO / "docs" / "combinations").glob("*.png"))
    assert on_disk == _NAMES
    for name in _NAMES:
        assert (_REPO / "docs" / "combinations" / f"{name}.png").read_bytes().startswith(b"\x89PNG")


def test_the_pictures_are_the_examples_drawn():
    spec = importlib.util.spec_from_file_location(
        "combinations_build", _REPO / "tools" / "combinations" / "build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    drawn = module.pictures()
    assert sorted(drawn) == _NAMES
    assert all(image.startswith(b"\x89PNG") and len(image) > 5000 for image in drawn.values())


@pytest.mark.parametrize("name", _NAMES)
def test_the_server_builds_what_the_library_builds(name):
    from anvilate.combination import build_combination, parse_combination
    from anvilate.mcp import RESULT_BUDGET_CHARS

    document = _document(name)
    reply = _call("build_combination", {"combination": document})
    assert len(json.dumps(reply)) < RESULT_BUDGET_CHARS
    body = reply["result"]["structuredContent"]
    built = build_combination(parse_combination(document))
    assert body["combination"] == built.summary().model_dump(mode="json")
    assert [entry["name"] for entry in body["scorecard"]["entries"]] == [
        entry.name for entry in built.card.entries
    ]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", body["subject"])


def test_an_agent_sees_the_combination_and_takes_away_an_assembly(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("ANVILATE_OUT", str(out))
    handle = _call("build_combination", {"combination": _document("bracket_on_plate")})["result"][
        "structuredContent"
    ]["subject"]
    picture = _call("render_viewport", {"subject": handle, "view": "overview"})["result"]
    assert [part["type"] for part in picture["content"]] == ["text", "image"]
    assert "structuredContent" not in picture
    assert picture["content"][1]["mimeType"] == "image/png"
    exported = _call("export_artifact", {"subject": handle, "format": "step"})["result"][
        "structuredContent"
    ]
    # Both parts are drawn and not checked, and nothing failed: a draft, marked unvalidated.
    assert exported["validated"] is False and "drawn and not checked" in exported["note"]
    written = sorted(path.name for path in out.iterdir())
    assert written == ["bracket-on-plate-assembly.png", "bracket-on-plate.step"]
    text = (out / "bracket-on-plate.step").read_text(encoding="utf-8")
    assert "UNVALIDATED" in text and text.count("NEXT_ASSEMBLY_USAGE_OCCURRENCE(") == 10


def test_a_combination_that_passes_exports_validated_and_says_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVILATE_OUT", str(tmp_path))
    handle = _call("build_combination", {"combination": _document("portal_frame")})["result"][
        "structuredContent"
    ]["subject"]
    exported = _call("export_artifact", {"subject": handle, "format": "step"})["result"][
        "structuredContent"
    ]
    assert "validated" not in exported and "note" not in exported
    assert "UNVALIDATED" not in Path(exported["file"]["path"]).read_text(encoding="utf-8")


def test_a_combination_with_a_failed_check_is_not_exported(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("ANVILATE_OUT", str(out))
    document = _document("bracket_on_plate")
    document["hardware"][0]["length"] = {"magnitude": 10.0, "unit": "mm"}
    handle = _call("build_combination", {"combination": document})["result"]["structuredContent"][
        "subject"
    ]
    error = _call("export_artifact", {"subject": handle, "format": "step"})["error"]
    assert error["code"] == -32000 and "bolted bolt length" in error["message"]
    assert "anvilate combine --unvalidated" in error["message"]
    assert not out.exists() or not list(out.iterdir())
    other = _call("export_artifact", {"subject": handle, "format": "dxf"})["error"]
    assert "a combination exports as step" in other["message"]


def test_a_combination_that_cannot_be_placed_is_a_bad_argument_not_a_crash():
    document = _document("lug_on_base_plate")
    document["mates"] = document["mates"][:1]
    document["welds"] = []
    error = _call("build_combination", {"combination": document})["error"]
    assert error["code"] == -32602
    assert error["message"].startswith("combination: the mates 'welded' leave 'lug' free to slide")
    assert _call("build_combination", {"combination": {"name": "x"}})["error"]["code"] == -32602


def test_a_part_handle_still_renders_and_exports_as_a_part(tmp_path, monkeypatch):
    """The combination branch is tried first; a part's handle must fall through it."""
    monkeypatch.setenv("ANVILATE_OUT", str(tmp_path))
    spec = yaml.safe_load((_REPO / "examples" / "transmission_shaft.spec.yaml").read_text("utf-8"))
    handle = _call("build_part", {"spec": spec})["result"]["structuredContent"]["subject"]
    assert _call("render_viewport", {"subject": handle, "view": "iso"})["result"]["content"]
    assert _call("export_artifact", {"subject": handle, "format": "step"})["result"]
    unknown = _call("render_viewport", {"subject": "sha256:" + "0" * 64, "view": "iso"})
    assert unknown["error"]["code"] == -32602


def test_the_command_prints_the_placement_the_card_and_the_parts_list(tmp_path):
    from cli_output import run_cli

    path = str(_EXAMPLES / "flange_pair.combination.yaml")
    step, picture = tmp_path / "pair.step", tmp_path / "pair.png"
    code, out, err = run_cli("combine", path, "--output", str(step), "--picture", str(picture))
    # Not evaluated, and refused without the flag: the flanges are drawn and not checked.
    assert code == 2 and "Pass --unvalidated" in err and not step.exists()
    assert picture.read_bytes().startswith(b"\x89PNG")
    assert "flange-pair: 26 bodies, 120 x 120 x 45.3 mm" in out
    assert " 4  6 x ISO4014-M8x40: bolt (envelope)" in out
    assert "pass           joint bolt length" in out
    code, out, _err = run_cli(
        "combine",
        path,
        "--output",
        str(step),
        "--unvalidated",
        "--picture",
        str(picture),
        "--force",
    )
    assert code == 2 and f"wrote {step} (UNVALIDATED)" in out and step.exists()
    code, _out, err = run_cli("combine", path, "--output", str(step))
    assert code == 3 and "pass --force to replace it" in err


def test_the_command_refuses_what_cannot_be_built(tmp_path):
    from cli_output import run_cli

    bad = tmp_path / "bad.yaml"
    bad.write_text("- just a list\n", encoding="utf-8")
    code, _out, err = run_cli("combine", str(bad))
    assert code == 3 and "not a combination document" in err
    code, _out, err = run_cli("combine", str(tmp_path / "missing.yaml"))
    assert code == 3
    frame = str(_EXAMPLES / "portal_frame.combination.yaml")
    code, out, _err = run_cli("combine", frame, "--output", str(tmp_path / "frame.step"))
    assert code == 0 and "(VALIDATED)" in out
    code, _out, err = run_cli(
        "combine", frame, "--output", str(tmp_path / "again.step"), "--unvalidated"
    )
    assert code == 3 and "Remove --unvalidated" in err
    code, _out, err = run_cli("combine", frame, "--picture", str(tmp_path / "frame.gif"))
    assert code == 3 and ".png or .svg" in err
