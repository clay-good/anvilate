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
from anvilate.product import parse_product  # noqa: E402
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
    assert plate["files"].startswith("step/PROV-") and plate["files"].endswith("_-.step")
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
    assert {"step/100-1_B.step", "step/100-2_B.step", "step/pair.step"} <= paths
    assert "ANVILATE_EXPORT_STATUS=VALIDATED" in (tmp_path / "step" / "100-1_B.step").read_text()


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
    shapes = {"bom.csv", "bom.xlsx", "buy.csv", "manifest.json",
              "step/<part number>_<revision>.step", "step/<product>.step",
              "parameters/<part number>.csv"}  # fmt: skip
    assert named == shapes
    written = {f.path for f in manifest.files} | {"manifest.json"}
    assert {"bom.csv", "bom.xlsx", "buy.csv", "manifest.json"} <= written
    assert any(p.startswith("parameters/") for p in written)
