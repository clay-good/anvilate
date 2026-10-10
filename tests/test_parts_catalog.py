"""The catalog page is the registry's own: generated, never typed (expand-drawable-parts 6.1).

A count or a parts list in prose expires the moment a pattern lands. The page is written by
`tools/parts-catalog/build.py` from `drawable_catalog()`, and these hold it there: the text
on disk is what the script writes, every pattern has its picture and its worked example,
and nothing on the page is a pattern the registry lacks.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from anvilate.patterns import drawable_catalog, patterns

_REPO = Path(__file__).resolve().parents[1]


def _builder():
    spec = importlib.util.spec_from_file_location(
        "parts_catalog_build", _REPO / "tools" / "parts-catalog" / "build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_page_on_disk_is_what_the_registry_generates():
    build = _builder()
    assert build.PAGE.read_text(encoding="utf-8") == build.page()
    assert build.main(["--check"]) == 0


def test_every_pattern_is_on_the_page_with_its_picture_and_nothing_else_is():
    page = (_REPO / "docs" / "parts-catalog.md").read_text(encoding="utf-8")
    headed = re.findall(r"^### `(\w+)`$", page, flags=re.MULTILINE)
    assert len(headed) >= 26 and headed == sorted(patterns())
    pictured = {path.stem for path in (_REPO / "docs" / "parts").glob("*.png")}
    assert pictured == set(patterns())
    for name in headed:
        assert f"](parts/{name}.png)" in page
        assert (_REPO / "docs" / "parts" / f"{name}.png").read_bytes().startswith(b"\x89PNG")


def test_every_pattern_names_a_worked_example_that_is_its_own():
    import yaml

    for entry in drawable_catalog():
        document = yaml.safe_load(
            (_REPO / "examples" / entry["example"]).read_text(encoding="utf-8")
        )
        assert document["element_type"] == entry["element_type"], entry["example"]
        stated = set(document["element_params"])
        required = {p["name"] for p in entry["parameters"] if p["required"]}
        assert required <= stated, (entry["element_type"], sorted(required - stated))


def test_the_catalog_says_what_is_checked_and_what_is_an_envelope():
    from anvilate.packs import parts

    by_type = {entry["element_type"]: entry for entry in drawable_catalog()}
    drawn_only = {name.removeprefix("screen_") for name in parts.__all__ if "screen_" in name}
    drawn_only.remove("clevis")  # screened under the load on its pin
    assert {name for name, entry in by_type.items() if not entry["screened"]} == drawn_only
    assert {name for name, entry in by_type.items() if entry["envelope"]} == {
        "helical_compression_spring",
        "pipe_run",
        "rolling_bearing",
        "spur_gear_mesh",
        "t_slot_extrusion",
    }
    page = (_REPO / "docs" / "parts-catalog.md").read_text(encoding="utf-8")
    assert page.count("**drawn, not checked**") == len(drawn_only) + 1  # and the legend
    takes = {p["name"]: p["takes"] for p in by_type["sheet_metal_bracket"]["parameters"]}
    assert takes["shape"] == "L | U | Z" and takes["thickness"] == "quantity"
    assert {p["takes"] for p in by_type["mounting_plate"]["parameters"]} >= {"list of Hole"}


def test_a_stale_page_is_reported(tmp_path, monkeypatch, capsys):
    build = _builder()
    stale = tmp_path / "parts-catalog.md"
    stale.write_text(build.page().replace("mounting_plate", "mounting_plat"), encoding="utf-8")
    monkeypatch.setattr(build, "PAGE", stale)
    monkeypatch.setattr(build, "REPO", tmp_path)
    assert build.main(["--check"]) == 1
    assert "is stale" in capsys.readouterr().out


def test_the_pictures_are_the_examples_drawn():
    pytest.importorskip("build123d")
    drawn = _builder().pictures()
    assert set(drawn) == set(patterns())
    assert all(png.startswith(b"\x89PNG") and len(png) > 2000 for png in drawn.values())


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


def test_an_agent_can_ask_what_it_can_declare_and_what_draws():
    from anvilate.screening import element_registry

    catalog = _call("describe_part", {})["result"]["structuredContent"]["catalog"]
    listed = {part["element_type"]: part for part in catalog["parts"]}
    assert set(listed) == set(element_registry()) and len(listed) >= 44
    assert {name for name, part in listed.items() if part["drawable"]} == set(patterns())
    assert listed["gusset_plate"] == {
        "element_type": "gusset_plate",
        "summary": listed["gusset_plate"]["summary"],
        "drawable": False,
        "screened": True,
    }
    assert not listed["spacer"]["screened"] and listed["base_plate"]["screened"]
    # A listing is lines: the fields and examples come one element at a time.
    assert all(
        set(part) == {"element_type", "summary", "drawable", "screened"} for part in listed.values()
    )


def test_every_element_is_described_with_an_example_that_is_a_valid_spec():
    """The example is what an agent copies, so each one is parsed, screened and, where the
    element draws, built: an example that refuses is a wrong answer handed out in advance."""
    pytest.importorskip("build123d")
    from anvilate.geometry import build_spec
    from anvilate.patterns import describe_part, describe_parts
    from anvilate.screening import screen_spec
    from anvilate.spec import parse_spec

    for line in describe_parts():
        (part,) = describe_part(line.element_type)
        assert part.example is not None, line.element_type
        fields = {parameter.name for parameter in part.parameters}
        assert set(part.example["element_params"]) <= fields, line.element_type
        required = {parameter.name for parameter in part.parameters if parameter.required}
        assert required <= set(part.example["element_params"]), line.element_type
        spec = parse_spec(dict(part.example))
        assert screen_spec(spec).entries, line.element_type
        if part.drawable:
            assert build_spec(spec).is_valid, line.element_type


def test_a_description_names_the_fields_of_every_type_a_parameter_takes():
    part = _call("describe_part", {"element_type": "mounting_plate"})["result"][
        "structuredContent"
    ]["catalog"]["parts"][0]
    assert part["outputs"] == ["views", "step", "3mf", "dxf"]
    takes = {parameter["name"]: parameter["takes"] for parameter in part["parameters"]}
    assert takes["holes"] == "list of Hole" and takes["hole_patterns"] == "list of HolePattern"
    assert set(part["types"]) == {"Hole", "HolePattern", "Slot"}
    hole = {parameter["name"]: parameter for parameter in part["types"]["Hole"]}
    assert hole["kind"]["takes"] == "through | counterbore | countersink"
    assert hole["diameter"] == {"name": "diameter", "required": True, "takes": "quantity"}
    assert part["example"]["element_type"] == "mounting_plate"


def test_a_name_one_guess_away_is_told_the_spelling():
    error = _call("describe_part", {"element_type": "mount_plate"})["error"]
    assert error["code"] == -32602
    assert "closest: mounting_plate" in error["message"]
    error = _call("describe_part", {"element_type": "zzzz"})["error"]
    assert "no element is named 'zzzz'" in error["message"] and "closest" not in error["message"]


def test_the_catalog_lookup_is_not_a_pipeline_operation_and_needs_no_subject():
    from anvilate.mcp import CATALOG_OPERATIONS, REQUIRED_OPERATIONS, stateless_gaps, tool_catalog

    (tool,) = [tool for tool in tool_catalog() if tool.name in CATALOG_OPERATIONS]
    assert tool.name == "describe_part" and tool.name not in REQUIRED_OPERATIONS
    assert tool.subject is None and tool.reads_shipped_catalog and tool.is_stateless
    assert not tool.emits_artifacts and not tool.gates
    assert stateless_gaps() == ()
    # Twice, with a build between: nothing an earlier call did changes the answer.
    first = _call("describe_part", {"element_type": "spacer"})["result"]["structuredContent"]
    _call("run_validation", {"spec": first["catalog"]["parts"][0]["example"]})
    assert (
        _call("describe_part", {"element_type": "spacer"})["result"]["structuredContent"] == first
    )


def test_the_command_line_prints_the_same_catalog():
    from cli_output import run_cli

    code, out, _err = run_cli("parts")
    assert code == 0
    assert f"{len(describe_all())} elements, {len(patterns())} drawn" in out
    assert "spacer" in out and "(drawn, not checked)" in out
    code, out, _err = run_cli("parts", "plate_flange")
    assert code == 0
    assert "bolt_circle_diameter     required  quantity" in out
    assert "element_type: plate_flange" in out and "drawn, not checked" in out
    code, _out, err = run_cli("parts", "plate_flang")
    assert code == 3 and "closest: plate_flange" in err


def describe_all():
    from anvilate.patterns import describe_parts

    return describe_parts()


def test_the_catalog_model_is_a_collection_of_its_parts():
    from anvilate.patterns import describe_part, describe_parts

    catalog = describe_parts()
    assert len(catalog) == len(catalog.parts) and catalog[0].element_type == "angle_bracket"
    assert catalog.parts[0] in catalog
    (one,) = describe_part("tube")
    assert type(catalog).model_validate_json(catalog.model_dump_json()) == catalog
    assert one.outputs == ("views", "step", "3mf") and "types" not in one.model_dump()


def test_the_example_is_a_copy_a_caller_may_edit():
    from anvilate.patterns import example_spec

    first = example_spec("spacer")
    first["element_params"]["length"]["magnitude"] = 99.0
    assert example_spec("spacer")["element_params"]["length"]["magnitude"] == 10.0
    assert example_spec("base_plate")["material"] == {"ref": "ASTM-A36"}
