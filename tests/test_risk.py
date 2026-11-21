"""Risk records: the hazard chain ISO 14971 and ISO 12100 share, each control verified.

The spec's scenarios: a pinch-point hazard controlled by a guard whose clearance is a check
shows the guard's verdict as the control's verification; when that check fails, the
control is not verified and the failing entry is named.
"""

from __future__ import annotations

import csv
import io

import pytest

from anvilate.refusal import RefusalError
from anvilate.risk import RISK_COLUMNS, RiskControl, RiskRecord, assess_risks
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry


def _card(factor: float | None) -> Scorecard:
    guard = ScorecardEntry.from_safety_factor(
        "guard clearance", computed=factor, required=1.0,
        unavailable="the opening size is not declared",
    )  # fmt: skip
    return Scorecard(entries=(guard,))


def _pinch(*controls: RiskControl) -> RiskRecord:
    return RiskRecord(
        id="H-3", hazard="crushing between the platen and the frame",
        hazardous_situation="an operator reaches past the guard while the press closes",
        harm="crushed fingers", severity="serious", probability="occasional",
        controls=controls or (RiskControl(description="fixed guard", check="guard clearance"),),
    )  # fmt: skip


def test_a_pinch_point_guarded_shows_the_guards_verdict():
    row = assess_risks([_pinch()], scorecard=_card(1.4)).rows[0]
    (control,) = row.controls
    assert (control.check, control.status, control.verified) == (
        "guard clearance",
        CheckStatus.PASS,
        True,
    )
    assert control.statement == "verified by guard clearance (pass)"


def test_a_control_whose_check_fails_is_not_verified_and_names_the_entry():
    report = assess_risks([_pinch()], scorecard=_card(0.7))
    (control,) = report.rows[0].controls
    assert control.verified is False and control.statement.startswith(
        "NOT verified: guard clearance fails"
    )
    assert report.not_verified == (("H-3", "fixed guard"),)
    assert "1 control(s) not verified" in str(report)


def test_a_check_that_did_not_run_does_not_verify():
    (control,) = assess_risks([_pinch()], scorecard=_card(None)).rows[0].controls
    assert control.verified is False and "did not run" in control.statement
    assert "opening size" in control.statement


def test_a_deferred_check_does_not_verify():
    card = _card(1.4)
    deferred = card.entries[0].model_copy(update={"status": CheckStatus.OUT_OF_DEPTH})
    card = Scorecard(entries=(deferred,))
    (control,) = assess_risks([_pinch()], scorecard=card).rows[0].controls
    assert control.verified is False and "deferred" in control.statement


def test_a_control_verified_in_words_is_declared_not_checked():
    label = RiskControl(description="warning label at the platen",
                        verification="label legibility review LR-12")  # fmt: skip
    bare = RiskControl(description="operator training")
    row = assess_risks([_pinch(label, bare)], scorecard=_card(1.4)).rows[0]
    assert [(c.verified, c.statement) for c in row.controls] == [
        (None, "declared: label legibility review LR-12"),
        (None, "no verification declared"),
    ]
    assert row.not_verified == ()


def test_a_control_naming_a_check_the_card_lacks_is_refused():
    ghost = RiskControl(description="light curtain", check="light curtain distance")
    with pytest.raises(RefusalError, match="light curtain distance"):
        assess_risks([_pinch(ghost)], scorecard=_card(1.4))


def test_a_control_cannot_be_verified_two_ways():
    with pytest.raises(ValueError, match="both a check and a verification"):
        RiskControl(description="guard", check="guard clearance", verification="inspection")


def test_a_record_declared_twice_is_refused():
    with pytest.raises(RefusalError, match="declared twice"):
        assess_risks([_pinch(), _pinch()], scorecard=_card(1.4))


def test_the_csv_carries_one_row_per_control_and_a_record_with_none():
    bare = RiskRecord(id="H-4", hazard="=hot surface", hazardous_situation="touch",
                      harm="burn", severity="minor", probability="remote")  # fmt: skip
    text = assess_risks([_pinch(), bare], scorecard=_card(0.7)).to_csv()
    rows = list(csv.reader(io.StringIO(text)))
    assert tuple(rows[0]) == RISK_COLUMNS
    assert rows[1][6:] == ["fixed guard", rows[1][7], "NO"] and "fails" in rows[1][7]
    assert rows[2][1] == "'=hot surface" and rows[2][6:] == ["", "no risk control declared", ""]
    assert rows[1][4:6] == ["serious", "occasional"]  # carried as written, never computed


def test_the_report_is_its_rows():
    report = assess_risks([_pinch()], scorecard=_card(1.4))
    assert len(report) == 1 and list(report) == list(report.rows) and report.rows[0] in report
