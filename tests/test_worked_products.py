"""The worked products: each one builds, checks and exports, in CI.

They are templates an agent copies and changes, so each must place without a clash, leave
no layout parameter unread, check through the CLI, and write a STEP assembly that reads
back with one component per body. Every one rests on placeholders for what is bought or
not yet detailed, so each is not evaluated, and exports only marked unvalidated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("build123d")

from anvilate._models import parse_yaml  # noqa: E402
from anvilate.cli import EXIT_NOT_EVALUATED  # noqa: E402
from anvilate.export.gate import ExportRefused, authorize_export  # noqa: E402
from anvilate.product import (  # noqa: E402
    parse_product,
    place_product,
    resolve_variant,
    write_product_step,
)
from anvilate.scorecard import CheckStatus  # noqa: E402
from cli_output import run_cli  # noqa: E402

_PRODUCTS = Path(__file__).resolve().parents[1] / "examples" / "products"
_NAMES = sorted(path.name for path in _PRODUCTS.glob("*.product.yaml"))


def test_the_four_the_spec_names_are_shipped():
    assert _NAMES == [
        "cart_frame.product.yaml",
        "enclosure.product.yaml",
        "gear_reducer.product.yaml",
        "linear_stage.product.yaml",
    ]


@pytest.mark.parametrize("name", _NAMES)
def test_a_worked_product_places_cleanly_and_reads_every_parameter(name):
    product = parse_product(parse_yaml((_PRODUCTS / name).read_text(encoding="utf-8")))
    placed = place_product(product)
    assert placed.interference.status is CheckStatus.PASS, placed.interference.detail
    assert placed.unused_parameters == ()
    assert placed.card.status is CheckStatus.NOT_EVALUATED  # it rests on placeholders
    assert placed.mass_rests_on and placed.center_of_mass_mm is not None


@pytest.mark.parametrize("name", _NAMES)
def test_a_worked_product_checks_at_the_shell(name):
    code, out, _err = run_cli("check", str(_PRODUCTS / name))
    assert code == EXIT_NOT_EVALUATED and ": not_evaluated" in out.splitlines()[0]


@pytest.mark.parametrize("name", _NAMES)
def test_a_worked_product_exports_one_component_per_body(name, tmp_path):
    product = parse_product(parse_yaml((_PRODUCTS / name).read_text(encoding="utf-8")))
    placed = place_product(product)
    with pytest.raises(ExportRefused):
        authorize_export(placed.card.flattened())  # placeholders are never released
    authorization = authorize_export(placed.card.flattened(), override=True)
    path = write_product_step(product, tmp_path / "product.step", authorization=authorization)
    text = path.read_text(encoding="utf-8")
    assert "ANVILATE_EXPORT_STATUS=UNVALIDATED" in text
    # one named product per item, however often it is placed, plus the assembly; the
    # writer reads the file back and refuses one whose components are not one per body
    items = {instance.item for instance in product.instances}
    assert text.count("PRODUCT('") == len(items) + 1


def test_the_long_stage_variant_still_clears_its_motor():
    stage = parse_product(parse_yaml((_PRODUCTS / "linear_stage.product.yaml").read_text()))
    placed = place_product(resolve_variant(stage, "long"))
    rail = next(b for b in placed.bodies if b.path.endswith("rail[1]"))
    assert rail.box_max_mm[0] == pytest.approx(-300 + 520)
    assert placed.interference.status is CheckStatus.PASS


def test_combine_writes_a_products_assembly_marked_unvalidated(tmp_path):
    out = tmp_path / "stage.step"
    name = str(_PRODUCTS / "linear_stage.product.yaml")
    code, _out, err = run_cli("combine", name, "--output", str(out))
    assert "Pass --unvalidated" in err and not out.exists()
    code, stdout, _err = run_cli("combine", name, "--output", str(out), "--unvalidated")
    assert code == EXIT_NOT_EVALUATED and out.exists()
    assert f"wrote {out} (UNVALIDATED)" in stdout
