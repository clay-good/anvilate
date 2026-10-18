"""An existing assembly as a reference item: the spec's new guard on an existing machine.

The machine is the worked cart (frame, four casters, a deck plate), exported as STEP. Its
envelope spans z −120 to 26, the deck plate's top. A 100 × 100 × 10 guard seated on the
machine's top face, flush with its left and front, lands on the deck plate at x −300 to
−200, y −200 to −100, z 26 to 36: it touches the plate, so a 5 mm clearance fails; lifted by
a 10 mm offset it clears by 10 mm.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from anvilate.context import read_step_assembly  # noqa: E402
from anvilate.export.gate import ExportAuthorization  # noqa: E402
from anvilate.product import (  # noqa: E402
    ProductError,
    load_product,
    parse_product,
    place_product,
    write_product_step,  # noqa: E402
)
from anvilate.release import export_package  # noqa: E402
from anvilate.scorecard import CheckStatus  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]


def _machine(folder: Path) -> Path:
    cart, library = load_product(_ROOT / "examples" / "products" / "cart_frame.product.yaml")
    path = folder / "machine.step"
    draft = ExportAuthorization(validated=False, overridden=True, blocking=("a test fixture",))
    write_product_step(cart, path, authorization=draft, library=library)
    return path


def _guarded(offset: float = 0.0, clearance: float | None = 5.0) -> dict:
    reference = {"file": "machine.step"}
    if clearance is not None:
        reference["clearance"] = {"magnitude": clearance, "unit": "mm"}
    sit = {"id": "sit", "kind": "face_to_face", "place": {"part": "guard", "face": "bottom"},
           "on": {"part": "machine", "face": "top"}}  # fmt: skip
    if offset:
        sit["offset"] = {"magnitude": offset, "unit": "mm"}
    return {
        "name": "retrofit",
        "definitions": [
            {"id": "machine", "identity": {"description": "existing cart", "source": "reference"},
             "reference": reference},
            {"id": "guard", "identity": {"description": "guard", "source": "make",
                                         "part_number": "G-1", "revision": "A"},
             "placeholder": {"envelope": [{"magnitude": v, "unit": "mm"} for v in (100, 100, 10)],
                             "mass": {"magnitude": 0.4, "unit": "kg"}, "reason": "drafting"}},
        ],
        "instances": [{"name": "machine", "item": "machine"}, {"name": "guard", "item": "guard"}],
        "ground": "machine",
        "mates": [sit] + [
            {"id": f"guard-{face}", "kind": "edge_flush", "place": {"part": "guard", "face": face},
             "on": {"part": "machine", "face": face}} for face in ("left", "front")
        ],
    }  # fmt: skip


def test_the_tree_of_an_existing_assembly_is_read_with_placed_envelopes(tmp_path):
    assembly = read_step_assembly(_machine(tmp_path))
    assert assembly.unit_written == "mm" and assembly.duplicates == ()
    paths = [c.path for c in assembly.components]
    assert len(paths) == 6 and paths[0].startswith("cart-frame/") and "welded frame" in paths[0]
    deck = next(c for c in assembly.components if "deck plate" in c.path)
    assert deck.box_max_mm[2] == pytest.approx(26)


def test_duplicate_names_are_both_reported_with_distinct_paths(tmp_path):
    from build123d import Box, Compound, Location, export_step

    first, second = Box(10, 10, 10), Box(10, 10, 10).moved(Location((20, 0, 0)))
    first.label = second.label = "leg"
    table = Compound(children=[first, second])
    table.label = "table"
    export_step(table, str(tmp_path / "table.step"))
    assembly = read_step_assembly(tmp_path / "table.step")
    assert [c.path for c in assembly.components] == ["table/leg", "table/leg[2]"]
    assert assembly.duplicates == ("table/leg names 2 or more components",)


@pytest.mark.parametrize(("offset", "status"), [(0.0, CheckStatus.FAIL), (10.0, CheckStatus.PASS)])
def test_a_new_guard_is_held_clear_of_every_solid_in_the_machine(tmp_path, offset, status):
    _machine(tmp_path)
    placed = place_product(parse_product(_guarded(offset)), root=tmp_path)
    guard = next(b for b in placed.bodies if b.path == "retrofit/guard")
    assert guard.box_min_mm == pytest.approx((-300, -200, 26 + offset))
    entries = {e.name: e for e in placed.card.entries}
    gap = entries["machine clearance"]
    assert gap.status is status and "deck plate" in gap.detail
    assert f"within {offset:g} mm" in gap.detail
    assert "retrofit/machine" not in placed.mass_unknown


def test_a_clearance_nobody_declared_is_not_a_pass(tmp_path):
    _machine(tmp_path)
    placed = place_product(parse_product(_guarded(10.0, clearance=None)), root=tmp_path)
    gap = {e.name: e for e in placed.card.entries}["machine clearance"]
    assert (
        gap.status is CheckStatus.NOT_EVALUATED and "no least clearance is declared" in gap.detail
    )


def test_the_release_package_holds_the_guard_alone(tmp_path):
    _machine(tmp_path)
    document = tmp_path / "retrofit.product.yaml"
    import yaml

    document.write_text(yaml.safe_dump({"anvilate_product": "1.6.0", **_guarded(10.0)}))
    manifest = export_package(document, tmp_path / "out", release=False)
    assembly = (tmp_path / "out" / "step" / "retrofit.step").read_text()
    assert "G-1 guard" in assembly and "existing cart" not in assembly
    rows = list(csv.DictReader(io.StringIO((tmp_path / "out" / "bom.csv").read_text())))
    machine = next(r for r in rows if r["description"] == "existing cart")
    assert machine["make/buy"] == "reference" and machine["files"] == ""
    assert not any("existing cart" in b or "retrofit/machine" in b for b in manifest.blockers)


def test_a_reference_needs_a_folder_and_is_neither_made_nor_bought(tmp_path):
    with pytest.raises(ProductError, match="no folder was given to read it from"):
        place_product(parse_product(_guarded()))
    document = _guarded()
    document["definitions"][0]["identity"]["source"] = "buy"
    with pytest.raises(ProductError, match="a reference is neither made nor bought"):
        parse_product(document)
