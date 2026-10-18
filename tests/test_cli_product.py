"""``anvilate check`` on a product document: the summary tree, one node, and the verdict.

The stage and its drive module are the card tests' failure deep in the tree: inside each
drive a motor and a bracket meet, so each drive owns a clash and the stage fails by
reference to both.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")

from anvilate.cli import EXIT_BAD_REQUEST, EXIT_FAILED, EXIT_NOT_EVALUATED  # noqa: E402
from cli_output import run_cli  # noqa: E402
from test_product_cards import _box as _holder  # noqa: E402
from test_product_cards import _definition, _drive, _seat  # noqa: E402


def _write(folder: Path, clash: bool = True) -> Path:
    drive = {"anvilate_product": "1.0.0", **_drive(clash)}
    stage = {
        "anvilate_product": "1.0.0",
        "name": "stage",
        "definitions": [_definition("base", placeholder=_holder(400, 100, 10, 3.0)),
                        _definition("drive", product="drive")],
        "instances": [{"name": "base", "item": "base"},
                      {"name": "drive", "item": "drive",
                       "pattern": {"kind": "linear", "count": 2, "direction": "x",
                                   "spacing": {"magnitude": 200, "unit": "mm"}}}],
        "ground": "base",
        "mates": _seat("drive", "base"),
    }  # fmt: skip
    (folder / "drive.product.yaml").write_text(yaml.safe_dump(drive), encoding="utf-8")
    path = folder / "stage.product.yaml"
    path.write_text(yaml.safe_dump(stage), encoding="utf-8")
    return path


def test_check_prints_the_summary_tree_and_fails_with_the_product(tmp_path):
    code, out, _err = run_cli("check", str(_write(tmp_path)))
    assert code == EXIT_FAILED
    lines = out.splitlines()
    assert lines[0].startswith("stage: fail")
    assert any(
        line.strip().startswith("stage [PROV-") and "fail" in line
        and "by reference to stage/drive[1], stage/drive[2]" in line
        for line in lines
    )  # fmt: skip
    drive = next(line for line in lines if line.strip().startswith("stage/drive[2] ["))
    assert "1 finding — interference:" in drive and "stage/drive[2]/bracket" in drive
    assert f"anvilate check {tmp_path / 'stage.product.yaml'} --node PATH" in lines[-1]


def test_check_reads_one_nodes_full_card(tmp_path):
    code, out, _err = run_cli("check", str(_write(tmp_path)), "--node", "stage/drive[1]")
    assert code == EXIT_FAILED
    assert out.splitlines()[0] == "stage/drive[1]: fail"
    assert "  - interference fail: 1 pair overlap" in out
    assert "stage/drive[1]/motor: not_evaluated" in out


def test_the_json_is_the_tree_the_text_prints(tmp_path):
    code, out, _err = run_cli("check", str(_write(tmp_path)), "--format", "json")
    document = json.loads(out)
    assert code == EXIT_FAILED and document["status"] == "fail"
    nodes = {node["path"]: node for node in document["product"]["nodes"]}
    assert nodes["stage/drive[2]"]["findings"] == 1
    assert nodes["stage/base"]["status"] == "not_evaluated"
    node = json.loads(run_cli("check", str(_write(tmp_path)), "--node", "stage/base",
                              "--format", "json")[1])  # fmt: skip
    assert node["node"]["path"] == "stage/base" and node["status"] == "not_evaluated"


def test_a_product_of_placeholders_is_not_evaluated_not_passed(tmp_path):
    code, out, _err = run_cli("check", str(_write(tmp_path, clash=False)))
    assert code == EXIT_NOT_EVALUATED and out.startswith("stage: not_evaluated")


def test_a_node_that_is_not_there_or_on_a_spec_is_a_bad_request(tmp_path):
    path = _write(tmp_path)
    code, _out, err = run_cli("check", str(path), "--node", "stage/drive[3]")
    assert code == EXIT_BAD_REQUEST and "no node 'stage/drive[3]' under 'stage'" in err
    spec = Path(__file__).resolve().parents[1] / "examples" / "parts" / "mounting_plate.spec.yaml"
    code, _out, err = run_cli("check", str(spec), "--node", "x")
    assert code == EXIT_BAD_REQUEST and "--node reads a node of a product document" in err


def test_a_sub_product_missing_from_the_folder_is_a_bad_request(tmp_path):
    path = _write(tmp_path)
    (tmp_path / "drive.product.yaml").unlink()
    code, _out, err = run_cli("check", str(path))
    assert code == EXIT_BAD_REQUEST and "the library does not hold" in err
