"""The release package: gated on the card, a draft marked, every file hashed in a manifest."""

from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from anvilate._models import parse_yaml  # noqa: E402
from anvilate.product import Product, parse_product  # noqa: E402
from anvilate.release import ReleaseRefused, export_package, verify_package  # noqa: E402
from test_components import _record  # noqa: E402
from test_product_cards import _box, _definition, _seat  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_STAGE = _ROOT / "examples" / "products" / "linear_stage.product.yaml"


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def test_a_placeholder_blocks_release_and_a_draft_is_written_marked(tmp_path):
    with pytest.raises(ReleaseRefused) as refused:
        export_package(_STAGE, tmp_path / "release", release=True)
    blockers = refused.value.blockers
    assert "linear-stage/base is a placeholder" in blockers
    assert any(b.startswith("linear-stage has the provisional part number PROV-") for b in blockers)
    assert not (tmp_path / "release").exists()
    manifest = export_package(_STAGE, tmp_path / "draft", release=False)
    assert manifest.kind == "draft" and manifest.blockers == blockers
    step = (tmp_path / "draft" / "step" / "linear-stage.step").read_text()
    assert "ANVILATE_EXPORT_STATUS=UNVALIDATED" in step and "is a placeholder" in step
    roles = {f.path: f.role for f in manifest.files}
    assert roles["bom.csv"] == "bom" and roles["buy.csv"] == "buy list"
    assert roles["step/linear-stage.step"] == "assembly step"


def test_the_indented_bom_carries_level_parent_and_quantity(tmp_path):
    export_package(_STAGE, tmp_path, release=False)
    rows = _rows(tmp_path / "bom.csv")
    assert list(rows[0]) == ["level", "find number", "parent part number", "part number",
                             "revision", "description", "quantity per parent",
                             "unit of measure", "material", "finish", "make/buy", "process",
                             "manufacturer", "manufacturer part number",
                             "supplier part numbers", "unit mass kg", "files"]  # fmt: skip
    rail = next(r for r in rows if r["description"] == "linear guide rail, 15 mm")
    assert (rail["level"], rail["find number"], rail["quantity per parent"]) == ("1", "2", "2")
    assert rail["make/buy"] == "buy" and rail["parent part number"].startswith("PROV-")
    plate = next(r for r in rows if r["description"] == "carriage plate")
    assert plate["material"] == "ASTM-A36" and plate["process"] == "cnc_milling"
    assert plate["files"].startswith("machined/PROV-") and plate["files"].endswith("_-.step")
    assert (tmp_path / "bom.xlsx").read_bytes()[:2] == b"PK"


def test_a_parameter_table_has_a_column_per_variant(tmp_path):
    manifest = export_package(_STAGE, tmp_path, release=False)
    assert manifest.variants == ("linear-stage-long",)
    (table,) = [f.path for f in manifest.files if f.role == "parameters"]
    rows = _rows(tmp_path / table)
    assert rows == [{"parameter": "rail_length", "unit": "mm", "linear-stage": "450",
                     "linear-stage-long": "520"}]  # fmt: skip


def test_a_purchased_motor_is_summed_across_every_drive(tmp_path):
    motor = _record("motor", {"rated_torque": {"magnitude": 1.26, "unit": "N*m"}})
    bought = {"id": "motor", "identity": {"description": "motor", "source": "buy",
                                          "part_number": "M-1"},
              "component": motor.model_dump(mode="json")}  # fmt: skip
    drive = parse_product({
        "name": "drive",
        "definitions": [_definition("plate", placeholder=_box(80, 60, 8, 0.6)), bought],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "motor", "item": "motor"}],
        "ground": "plate", "mates": _seat("motor", "plate"),
    })  # fmt: skip
    stage = parse_product({
        "name": "stage",
        "definitions": [_definition("base", placeholder=_box(900, 100, 10, 3.0)),
                        _definition("drive", product="drive"), copy.deepcopy(bought)],
        "instances": [{"name": "base", "item": "base"},
                      {"name": "drive", "item": "drive",
                       "pattern": {"kind": "linear", "count": 4, "direction": "x",
                                   "spacing": {"magnitude": 200, "unit": "mm"}}},
                      {"name": "spare", "item": "motor"}],
        "ground": "base",
        "mates": [*_seat("drive", "base"), *_seat("spare", "base")],
    })  # fmt: skip
    export_package(stage, tmp_path, release=False, library={"drive": drive})
    (line,) = _rows(tmp_path / "buy.csv")
    assert line["designation"] == "Acme motor-1" and line["quantity"] == "5"
    assert line["supplier part numbers"] == "Distributor D-1"
    assert "stage/drive[4]/motor" in line["used at"] and "stage/spare" in line["used at"]


def test_a_released_product_is_marked_validated_and_each_part_is_named_by_number(tmp_path):
    plate = parse_yaml((_ROOT / "examples" / "parts" / "mounting_plate.spec.yaml").read_text())
    part = {"id": "plate", "spec": plate,
            "identity": {"description": "plate", "source": "make", "part_number": "100-1",
                         "revision": "B"}}  # fmt: skip
    top = {**copy.deepcopy(part), "id": "top"}
    top["identity"] = {**part["identity"], "part_number": "100-2"}
    product = parse_product({
        "name": "pair", "identity": {"description": "pair", "source": "make",
                                     "part_number": "200-1", "revision": "A"},
        "definitions": [part, top],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "top", "item": "top"}],
        "ground": "plate", "mates": _seat("top", "plate"),
    })  # fmt: skip
    manifest = export_package(product, tmp_path, release=True)
    assert manifest.kind == "release" and manifest.blockers == () and manifest.revision == "A"
    paths = {f.path for f in manifest.files}
    assert {"machined/100-1_B.step", "machined/100-2_B.step", "step/pair.step"} <= paths
    assert (
        "ANVILATE_EXPORT_STATUS=VALIDATED" in (tmp_path / "machined" / "100-1_B.step").read_text()
    )


def test_a_file_edited_after_export_is_reported_by_path_and_both_hashes(tmp_path):
    manifest = export_package(_STAGE, tmp_path, release=False)
    assert verify_package(tmp_path) == ()
    listed = next(f for f in manifest.files if f.path == "bom.csv")
    (tmp_path / "bom.csv").write_text("edited\n", encoding="utf-8")
    (tmp_path / "buy.csv").unlink()
    problems = verify_package(tmp_path)
    assert f"bom.csv is altered: listed {listed.sha256}, found " in problems[0]
    assert problems[1] == "buy.csv is missing"
    assert json.loads((tmp_path / "manifest.json").read_text())["kind"] == "draft"


def test_anvilate_verify_reads_a_package_folder(tmp_path):
    from anvilate.cli import EXIT_FAILED, EXIT_OK
    from cli_output import run_cli

    export_package(_STAGE, tmp_path, release=False)
    code, out, _err = run_cli("verify", str(tmp_path))
    assert code == EXIT_OK and "every file matches the manifest" in out
    (tmp_path / "bom.csv").write_text("edited\n", encoding="utf-8")
    code, out, _err = run_cli("verify", str(tmp_path))
    assert code == EXIT_FAILED and "bom.csv is altered" in out
    code, out, _err = run_cli("verify", str(tmp_path), "--format", "json")
    document = json.loads(out)
    assert code == EXIT_FAILED and document["intact"] is False
    assert document["problems"][0].startswith("bom.csv is altered")


def test_the_docs_page_names_every_file_the_package_writes(tmp_path):
    import re

    manifest = export_package(_STAGE, tmp_path, release=False)
    page = (_ROOT / "docs" / "release-package.md").read_text()
    first_cells = re.findall(r"^\| (`[^|]+`) \|", page, re.M)
    named = {name for cell in first_cells for name in re.findall(r"`([^`]+)`", cell)}
    shapes = {"bom.csv", "bom.xlsx", "buy.csv", "manifest.json", "bom-<profile>.csv",
              "machined/<part number>_<revision>.step", ".html",
              "laser/<part number>_<revision>.dxf", "laser/cut-list.csv", "print/plate.3mf",
              "step/<part number>_<revision>.step", "step/<product>.step",
              "parameters/<part number>.csv"}  # fmt: skip
    assert named == shapes
    written = {f.path for f in manifest.files} | {"manifest.json"}
    assert {"bom.csv", "bom.xlsx", "buy.csv", "manifest.json"} <= written
    assert any(p.startswith("parameters/") for p in written)


def _pair(hole_x: float = 0.0, revision: str = "B"):
    plate = parse_yaml((_ROOT / "examples" / "parts" / "mounting_plate.spec.yaml").read_text())
    plate["element_params"]["holes"][0]["x"] = {"magnitude": hole_x, "unit": "mm"}
    part = {"id": "plate", "spec": plate,
            "identity": {"description": "plate", "source": "make", "part_number": "100-1",
                         "revision": revision}}  # fmt: skip
    top = {
        **copy.deepcopy(part),
        "id": "top",
        "spec": parse_yaml((_ROOT / "examples" / "parts" / "mounting_plate.spec.yaml").read_text()),
    }
    top["identity"] = {**part["identity"], "part_number": "100-2", "revision": "B"}
    return parse_product({
        "name": "pair", "identity": {"description": "pair", "source": "make",
                                     "part_number": "200-1", "revision": "A"},
        "definitions": [part, top],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "top", "item": "top"}],
        "ground": "plate", "mates": _seat("top", "plate"),
    })  # fmt: skip


def test_a_silent_change_cannot_be_released_under_its_old_revision(tmp_path):
    baseline = export_package(_pair(), tmp_path / "rev-a", release=True)
    plate = next(item for item in baseline.items if item.item == "plate")
    assert plate.revision == "B" and "machined/100-1_B.step" in plate.files
    with pytest.raises(ReleaseRefused) as refused:
        export_package(_pair(hole_x=5.0), tmp_path / "rev-b", release=True, baseline=baseline)
    (blocker,) = refused.value.blockers
    assert blocker == ("plate (100-1) changed under revision B: "
                       "element_params.holes[0].x.magnitude 0.0 → 5.0")  # fmt: skip
    revised = export_package(_pair(hole_x=5.0, revision="C"), tmp_path / "rev-c", release=True,
                             baseline=baseline)  # fmt: skip
    assert revised.kind == "release" and "machined/100-1_C.step" in {f.path for f in revised.files}


def test_unchanged_content_regenerates_identical_files(tmp_path):
    first = export_package(_pair(), tmp_path / "one", release=True)
    second = export_package(_pair(), tmp_path / "two", release=True, baseline=first)
    assert [(f.path, f.sha256) for f in first.files] == [(f.path, f.sha256) for f in second.files]
    assert (tmp_path / "one" / "manifest.json").read_bytes() == (
        tmp_path / "two" / "manifest.json"
    ).read_bytes()


def test_a_product_is_compared_with_its_last_release(tmp_path):
    from anvilate.changes import compare_products, compare_to_release

    baseline = export_package(_pair(), tmp_path, release=True)
    record = compare_to_release(_pair(hole_x=5.0), baseline)
    items = {item.item: item for item in record.items}
    plate = items["plate"]
    assert plate.status == "changed" and plate.changes[0].startswith("element_params.holes[0].x")
    assert plate.evidence == ("content changed under part number 100-1 revision B, as released",)
    assert "machined/100-1_B.step" in plate.affected_files and "bom.csv" in plate.affected_files
    assert items["top"].status == "unchanged" and record.mass_before_kg is None
    assert "the release records none to compare" in record.to_markdown()
    classified = compare_products(_pair(), _pair(hole_x=5.0), baseline=baseline)
    assert "machined/100-1_B.step" in {i.item: i for i in classified.items}["plate"].affected_files


def _routed_product() -> Product:
    def spec(path: str, process: str) -> dict:
        document = parse_yaml((_ROOT / path).read_text())
        document["manufacturing"] = {"process": process}
        return document

    def part(id_: str, document: dict, number: str) -> dict:
        return {"id": id_, "spec": document,
                "identity": {"description": id_, "source": "make", "part_number": number,
                             "revision": "A"}}  # fmt: skip

    return parse_product({
        "name": "routed",
        "definitions": [part("base", spec("examples/base_plate.spec.yaml", "sheet_metal"), "300-1"),
                        part("spacer", spec("examples/parts/spacer.spec.yaml", "fdm"), "300-2"),
                        part("bracket", spec("examples/parts/sheet_metal_bracket.spec.yaml",
                                             "sheet_metal"), "300-3")],
        "instances": [{"name": "base", "item": "base"},
                      {"name": "spacer", "item": "spacer",
                       "pattern": {"kind": "linear", "count": 2, "direction": "x",
                                   "spacing": {"magnitude": 40, "unit": "mm"}}},
                      {"name": "bracket", "item": "bracket"}],
        "ground": "base",
        "mates": [*_seat("spacer", "base"), *_seat("bracket", "base")],
    })  # fmt: skip


def test_made_parts_are_routed_by_their_process(tmp_path):
    import zipfile

    manifest = export_package(_routed_product(), tmp_path, release=False)
    roles = {f.path: f.role for f in manifest.files}
    assert roles["laser/300-1_A.dxf"] == "profile dxf"
    assert roles["laser/cut-list.csv"] == "cut list"
    assert roles["print/plate.3mf"] == "print plate"
    cut = {row["part number"]: row for row in _rows(tmp_path / "laser" / "cut-list.csv")}
    assert (cut["300-1"]["quantity"], cut["300-1"]["file"]) == ("1", "laser/300-1_A.dxf")
    assert cut["300-1"]["thickness mm"] == "25" and cut["300-3"]["thickness mm"] == "2"
    with zipfile.ZipFile(tmp_path / "print" / "plate.3mf") as plate:
        model = plate.read("3D/3dmodel.model").decode()
    assert model.count("<object ") == 1 and model.count('<item objectid="1"') == 2
    assert roles["laser/300-3_A.dxf"] == "profile dxf" and manifest.unrouted == ()


def test_a_part_its_process_format_cannot_express_is_named_not_dropped(tmp_path):
    product = _routed_product()
    # an angle bracket declared laser-cut has no flat profile: its STEP goes out, and it is named
    angle = parse_yaml((_ROOT / "examples" / "parts" / "angle_bracket.spec.yaml").read_text())
    angle["manufacturing"] = {"process": "sheet_metal"}
    document = product.model_dump(mode="json")
    document["definitions"][2]["spec"] = angle
    manifest = export_package(parse_product(document), tmp_path, release=False)
    assert {f.path: f.role for f in manifest.files}["step/300-3_A.step"] == "part step"
    assert manifest.unrouted[0].startswith("300-3: no profile DXF for its angle_bracket/1 pattern")


def test_a_column_profile_writes_dotted_levels_and_its_own_spellings(tmp_path):
    from anvilate.release import ColumnProfile

    profile = ColumnProfile.model_validate({
        "name": "erp", "level": "dotted", "make_buy": {"make": "M", "buy": "B"},
        "columns": [{"field": "level", "header": "LVL"},
                    {"field": "part number", "header": "ITEM"},
                    {"field": "make/buy", "header": "SRC"},
                    {"field": "quantity per parent", "header": "QTY"}],
    })  # fmt: skip
    export_package(_STAGE, tmp_path, release=False, profiles=[profile])
    profiled = _rows(tmp_path / "bom-erp.csv")
    assert list(profiled[0]) == ["LVL", "ITEM", "SRC", "QTY"]
    assert [(r["LVL"], r["SRC"]) for r in profiled] == [
        ("1", "M"),
        ("2", "B"),
        ("3", "M"),
        ("4", "B"),
    ]
    assert _rows(tmp_path / "bom.csv")[1]["make/buy"] == "buy"  # the default BOM is unchanged


def test_a_profile_naming_a_field_the_bom_does_not_carry_is_refused():
    from anvilate.release import ColumnProfile

    with pytest.raises(ValueError, match="asks for 'colour', which the BOM does not carry"):
        ColumnProfile.model_validate({"name": "x", "columns": [{"field": "colour", "header": "C"}]})
