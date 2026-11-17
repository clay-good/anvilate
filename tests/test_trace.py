"""Traceability: each requirement to the checks, tests and evidence that address it.

The spec's scenario: a requirement for a 10-year life with no fatigue check and no test
traced to it is marked uncovered. And the other half: a check nobody asked for is
listed as untraced.
"""

from __future__ import annotations

import csv
import io
from datetime import date

import pytest

from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.trace import TRACE_COLUMNS, Requirement, trace_requirements
from anvilate.units import Quantity
from anvilate.verification import VerificationOutcome, plan_verification, record_outcome

_BTH1 = "ASME BTH-1 §3-2/§3-3 (allowable stresses)"


def _entry(name: str, reference: str, factor: float = 2.0) -> ScorecardEntry:
    entry = ScorecardEntry.from_safety_factor(name, computed=factor, required=1.0)
    return entry.model_copy(update={"reference": reference})


@pytest.fixture
def card() -> Scorecard:
    return Scorecard(entries=(_entry("beam bending", _BTH1), _entry("bail pin bearing", _BTH1, 0.8),
                              _entry("paint thickness", "ISO 12944-5")))  # fmt: skip


@pytest.fixture
def plan(card):
    return plan_verification(card, parameters={"rated_load": Quantity.parse("100 kN")})


def _requirements() -> list[Requirement]:
    return [
        Requirement(id="R-1", text="lift 100 kN with a margin", source="customer spec §3.1",
                    addressed_by=("beam bending",)),
        Requirement(id="R-2", text="10-year service life", source="customer spec §5.2"),
        Requirement(id="R-3", text="pin does not yield", source="customer spec §3.4",
                    addressed_by=("bail pin bearing",)),
    ]  # fmt: skip


def test_a_requirement_nothing_addresses_is_uncovered(card, plan):
    report = trace_requirements(_requirements(), scorecard=card, plan=plan)
    life = report.rows[1]
    assert (life.requirement, life.coverage) == ("R-2", "uncovered")
    assert life.status is CheckStatus.NOT_EVALUATED and life.checks == () == life.verification_items
    assert report.uncovered == ("R-2",)


def test_a_check_no_requirement_names_is_untraced(card, plan):
    report = trace_requirements(_requirements(), scorecard=card, plan=plan)
    assert report.untraced_checks == ("paint thickness",)
    rows = list(csv.reader(io.StringIO(report.to_csv())))
    assert tuple(rows[0]) == TRACE_COLUMNS
    assert rows[-1] == ["", "", "", "untraced", "", "paint thickness", "", ""]


def test_a_check_brings_its_test_and_a_test_brings_its_recorded_outcome(card, plan):
    lift = trace_requirements(_requirements(), scorecard=card, plan=plan).rows[0]
    proof = plan.items[0].name
    assert lift.checks == ("beam bending",) and lift.verification_items == (proof,)
    assert lift.evidence == ()  # a planned test is not evidence
    done = record_outcome(plan, name=proof, outcome=VerificationOutcome(
        passed=True, measured="held 125 kN", performed_on=date(2026, 11, 16),
        performed_by="J. Rivera", instrument="LC-0042"))  # fmt: skip
    lift = trace_requirements(_requirements(), scorecard=card, plan=done).rows[0]
    assert lift.evidence == (f"{proof}: pass",)


def test_coverage_is_not_a_verdict_a_covered_requirement_can_fail(card, plan):
    pin = trace_requirements(_requirements(), scorecard=card, plan=plan).rows[2]
    assert pin.coverage == "covered" and pin.status is CheckStatus.FAIL
    assert "R-3 [covered, fail]" in str(pin)


def test_a_name_that_is_neither_a_check_nor_a_test_is_refused(card, plan):
    stray = Requirement(id="R-9", text="no fatigue", source="spec", addressed_by=("fatigue",))
    with pytest.raises(RefusalError, match=r"R-9 names \['fatigue'\], which are neither"):
        trace_requirements([stray], scorecard=card, plan=plan)
    twice = [*_requirements(), _requirements()[0]]
    with pytest.raises(RefusalError, match="declared twice"):
        trace_requirements(twice, scorecard=card)
    with pytest.raises(RefusalError, match="scorecard"):
        trace_requirements(_requirements(), scorecard="card")  # type: ignore[arg-type]


def test_the_report_reads_as_what_it_found(card, plan):
    report = trace_requirements(_requirements(), scorecard=card, plan=plan)
    assert str(report) == ("3 requirement(s) traced; uncovered: R-2; untraced checks: "
                           "paint thickness")  # fmt: skip


def test_the_page_example_says_what_the_trace_returns(card, plan):
    import pathlib

    page = pathlib.Path(__file__).resolve().parents[1] / "docs" / "quality-artifacts.md"
    text = page.read_text()
    report = trace_requirements(_requirements()[:2], scorecard=card, plan=plan)
    assert f"report.uncovered        # {report.uncovered!r}" in text
    assert 'Requirement(id="R-2", text="10-year service life"' in text
