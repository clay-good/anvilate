"""The verification plan as a DVP&R: one row per item, what is not declared left blank.

The lifter's plan has a proof-load item standing behind its two BTH-1 checks and a
dimensional item behind its fit. The proof load row's acceptance criterion is the plan's
own: 1.25 x the 100 kN rated load, 125 kN.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date

import pytest

from anvilate.refusal import RefusalError
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity
from anvilate.verification import (
    DVPR_COLUMNS,
    DvprDeclaration,
    VerificationOutcome,
    dvpr_csv,
    dvpr_rows,
    dvpr_xlsx,
    plan_verification,
    record_outcome,
)

_BTH1 = "ASME BTH-1 §3-2/§3-3 (allowable stresses)"


def _entry(name: str, reference: str) -> ScorecardEntry:
    entry = ScorecardEntry.from_safety_factor(name, computed=2.0, required=1.0)
    return entry.model_copy(update={"reference": reference})


@pytest.fixture
def plan():
    card = Scorecard(entries=(_entry("beam bending", _BTH1), _entry("bail pin bearing", _BTH1),
                              _entry("pin fit", "ISO 286 H7/g6 clearance fit")))  # fmt: skip
    return plan_verification(card, parameters={"rated_load": Quantity.parse("100 kN"),
                                               "tolerance": Quantity.parse("0.05 mm")})  # fmt: skip


def _by_archetype(rows) -> dict:
    return {row[2]: dict(zip(DVPR_COLUMNS, row, strict=True)) for row in rows}


def test_each_item_is_a_row_naming_its_requirement_procedure_and_criterion(plan):
    rows = _by_archetype(dvpr_rows(plan, item_path="lifter/spreader beam"))
    proof = rows["Proof load test"]
    assert proof["requirement"] == "beam bending; bail pin bearing"
    assert proof["item path"] == "lifter/spreader beam"
    assert proof["procedure reference"].startswith("ASME B30.20")
    assert proof["acceptance criterion"].startswith("apply 125 kN")
    assert (
        "instrument: load measurement within 1% of the proof load" in proof["acceptance criterion"]
    )
    assert (proof["sample size"], proof["timing"], proof["owner"], proof["recorded result"]) == (
        "", "", "", "")  # fmt: skip


def test_what_the_engineer_declares_fills_its_columns_and_a_result_names_who_and_when(plan):
    name = next(i.name for i in plan.items if i.archetype.key == "proof-load")
    outcome = VerificationOutcome(
        passed=True, measured="held 125 kN for 1 min, no deformation",
        performed_on=date(2026, 11, 16), performed_by="J. Rivera", instrument="LC-0042",
    )  # fmt: skip
    done = record_outcome(plan, name=name, outcome=outcome)
    said = DvprDeclaration(sample_size=1, timing="before first use", owner="test lab")
    rows = _by_archetype(dvpr_rows(done, item_path="lifter", declared={name: said}))
    proof = rows["Proof load test"]
    assert (proof["sample size"], proof["timing"], proof["owner"]) == (
        "1", "before first use", "test lab")  # fmt: skip
    assert proof["recorded result"] == (
        "pass: held 125 kN for 1 min, no deformation (2026-11-16, J. Rivera, LC-0042)"
    )
    assert rows["Dimensional inspection"]["owner"] == ""


def test_the_csv_and_the_workbook_carry_the_same_rows(plan):
    rows = dvpr_rows(plan, item_path="lifter")
    read = list(csv.reader(io.StringIO(dvpr_csv(plan, item_path="lifter"))))
    assert tuple(read[0]) == DVPR_COLUMNS and [tuple(r) for r in read[1:]] == list(rows)
    with zipfile.ZipFile(io.BytesIO(dvpr_xlsx(plan, item_path="lifter"))) as book:
        sheet = book.read("xl/worksheets/sheet1.xml").decode()
        assert "DVP&amp;R" in book.read("xl/workbook.xml").decode()
    assert "Proof load test" in sheet and "acceptance criterion" in sheet


def test_a_cell_that_reads_as_a_formula_is_written_as_text(plan):
    name = plan.items[0].name
    text = dvpr_csv(plan, item_path="lifter",
                    declared={name: DvprDeclaration(timing="+2 weeks after build")})  # fmt: skip
    assert "'+2 weeks after build" in text


def test_a_declaration_for_an_item_the_plan_does_not_hold_is_refused(plan):
    with pytest.raises(RefusalError, match="not items of this plan"):
        dvpr_rows(plan, item_path="lifter", declared={"fatigue": DvprDeclaration(owner="x")})
    with pytest.raises(RefusalError, match="item_path"):
        dvpr_rows(plan, item_path=" ")
    with pytest.raises(RefusalError, match="VerificationPlan"):
        dvpr_rows("plan", item_path="lifter")  # type: ignore[arg-type]


def test_the_page_quotes_the_criterion_this_plan_writes(plan):
    import pathlib

    page = pathlib.Path(__file__).resolve().parents[1] / "docs" / "verification-planning.md"
    rows = _by_archetype(dvpr_rows(plan, item_path="lifter"))
    assert rows["Proof load test"]["acceptance criterion"].startswith(
        "apply 125 kN — 1.25 x the 100 kN rated load")  # fmt: skip
    assert "apply 125 kN, 1.25 x its 100 kN rated load" in " ".join(page.read_text().split())
