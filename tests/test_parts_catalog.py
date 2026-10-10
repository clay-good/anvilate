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
    assert len(headed) >= 18 and headed == sorted(patterns())
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
    assert {name for name, entry in by_type.items() if not entry["screened"]} == drawn_only
    assert {name for name, entry in by_type.items() if entry["envelope"]} == {"t_slot_extrusion"}
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
