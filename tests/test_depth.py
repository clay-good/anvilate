"""Declared screening depth: a deferral is its own status, counted and never a pass."""

from __future__ import annotations

import pytest

from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.screening import screen_spec
from anvilate.spec import ScreeningDepth, load_spec_yaml

_DRAWN = """
anvilate_spec: "1.3.0"
name: drawn_plate
description: A plate with a drawing's worth of declarations on it.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: cnc_milling, tolerance_class: medium}
acceptance: {tiers: [T1_analytical, T2_dfm]}
constraints: {min_safety_factor: {value: 2.0, origin: user_stated}}
element_type: cover_plate
element_params:
  name: cover
  length: {magnitude: 300.0, unit: mm}
  width: {magnitude: 200.0, unit: mm}
  thickness: {magnitude: 10.0, unit: mm}
  material: ASTM-A36
  pressure: {magnitude: 0.2, unit: MPa}
dimensions:
  - tag: bore
    nominal: {magnitude: 25.0, unit: mm}
    tolerance: {type: symmetric, plus_minus: {magnitude: 0.05, unit: mm}}
  - tag: seat
    nominal: {magnitude: 12.0, unit: mm}
    tolerance: {type: symmetric, plus_minus: {magnitude: 0.03, unit: mm}}
chains:
  - name: seat_to_bore
    links: [{dimension: bore, direction: 1}, {dimension: seat, direction: -1}]
    required_min: {magnitude: 12.8, unit: mm}
    required_max: {magnitude: 13.2, unit: mm}
geometric_tolerances:
  - characteristic: position
    tolerance: {magnitude: 0.2, unit: mm}
    feature: bore
    datums: [A, B]
    diametral: true
"""


def _spec(depth: str | None = None):
    text = _DRAWN
    if depth is not None:
        text = text.replace(
            "acceptance: {tiers: [T1_analytical, T2_dfm]}",
            f"acceptance: {{tiers: [T1_analytical, T2_dfm], depth: {depth}}}",
        )
    return load_spec_yaml(text)


def test_a_document_that_declares_no_depth_is_screened_as_before() -> None:
    # The default cannot re-read a document already written: detailed is what this library
    # did before depth existed.
    assert _spec().acceptance.depth is ScreeningDepth.DETAILED
    card = screen_spec(_spec())
    assert card.out_of_depth() == ()
    assert card.completeness()[1] == 0
    families = {entry.name.split(":")[0] for entry in card.entries}
    assert "tolerance achievability" in families
    assert "stack-up" in families or any(e.name.startswith("stack-up") for e in card.entries)
    assert "geometric tolerance" in families


def test_a_concept_screen_defers_the_drawings_work_and_counts_it() -> None:
    card = screen_spec(_spec("concept"))
    deferred = {entry.name for entry in card.out_of_depth()}
    assert deferred == {"tolerance achievability", "stack-up", "geometric tolerance"}
    # Each deferral names what would have driven it and how to ask for it.
    for entry in card.out_of_depth():
        assert "acceptance.depth is concept" in entry.detail
        assert "acceptance.depth: detailed" in entry.detail
    # And the deferred checks did not run: no per-dimension entries survive.
    assert not [e for e in card.entries if e.name.startswith("tolerance achievability:")]
    assert card.completeness()[1] == 3


def test_a_deferral_is_not_a_pass_and_not_a_failure() -> None:
    card = screen_spec(_spec("concept"))
    # Nothing blocks, so the card is not failing; it is not claiming completeness either.
    assert card.status is CheckStatus.OUT_OF_DEPTH
    assert card.passed  # a deferral does not block
    assert not card.failures()
    assert card.not_evaluated() == ()


def test_the_two_counts_are_stated_separately_and_never_collapsed() -> None:
    card = Scorecard(
        entries=(
            ScorecardEntry(name="ran", status=CheckStatus.PASS, detail="fine"),
            ScorecardEntry(name="could not", status=CheckStatus.NOT_EVALUATED, detail="no data"),
            ScorecardEntry(name="deferred", status=CheckStatus.OUT_OF_DEPTH, detail="later"),
        )
    )
    assert card.completeness() == (1, 1)
    # A card carrying both reports the blocking one as its verdict.
    assert card.status is CheckStatus.NOT_EVALUATED
    assert not card.passed
    assert card.not_evaluated()[0].name == "could not"
    assert card.out_of_depth()[0].name == "deferred"


def test_a_complete_card_states_both_zeros() -> None:
    card = Scorecard(entries=(ScorecardEntry(name="ran", status=CheckStatus.PASS, detail="fine"),))
    assert card.completeness() == (0, 0)
    assert card.status is CheckStatus.PASS


def test_a_deferred_check_did_not_run() -> None:
    deferred = ScorecardEntry(name="deferred", status=CheckStatus.OUT_OF_DEPTH, detail="later")
    assert not deferred.evaluated
    assert not deferred.passed
    assert not deferred.over_margin


def test_a_deferral_never_governs_over_a_real_finding() -> None:
    deferred = ScorecardEntry(name="deferred", status=CheckStatus.OUT_OF_DEPTH, detail="later")
    for worse in (CheckStatus.NOT_EVALUATED, CheckStatus.FAIL, CheckStatus.OVER_MARGIN):
        card = Scorecard(
            entries=(
                deferred,
                ScorecardEntry(name="the finding", status=worse, detail="look here"),
            )
        )
        governing = card.governing()
        assert governing is not None and governing.name == "the finding"
    # And it does govern over a clean pass, because it is news about the card.
    card = Scorecard(
        entries=(ScorecardEntry(name="ran", status=CheckStatus.PASS, detail="fine"), deferred)
    )
    governing = card.governing()
    assert governing is not None and governing.name == "deferred"


def test_raising_the_depth_names_what_it_runs_and_what_it_then_needs() -> None:
    from anvilate.needs import needs_report

    concept, detailed = screen_spec(_spec("concept")), screen_spec(_spec())
    ran = {e.name for e in detailed.entries} - {e.name for e in concept.entries}
    assert ran, "raising the depth ran no new checks"
    # The price of going deeper, in the report's own terms: what the deeper screens need.
    deeper_needs = {i.need.declaration for i in needs_report(detailed).items}
    shallow_needs = {i.need.declaration for i in needs_report(concept).items}
    assert deeper_needs >= shallow_needs


@pytest.mark.parametrize("status", list(CheckStatus))
def test_every_status_has_an_exit_code_a_rank_and_a_label(status: CheckStatus) -> None:
    from anvilate.cli import EXIT_CODES
    from anvilate.export.qif import _CHARACTERISTIC_STATUS, _INSPECTION_STATUS
    from anvilate.report.document import _STATUS_LABEL
    from anvilate.scorecard import _STATUS_RANK

    for table in (
        EXIT_CODES,
        _STATUS_RANK,
        _STATUS_LABEL,
        _CHARACTERISTIC_STATUS,
        _INSPECTION_STATUS,
    ):
        assert status in table, f"{status.value} has no entry in {table}"


# --- raising the depth: what it runs, and what it then needs ---------------------------


def test_raising_the_depth_reports_the_checks_it_runs() -> None:
    from anvilate.needs import deepening
    from anvilate.spec import ScreeningDepth

    change = deepening(_spec("concept"), ScreeningDepth.DETAILED)
    assert change.from_depth == "concept" and change.to_depth == "detailed"
    # The return: the checks that now produce a verdict, named.
    assert set(change.newly_run) == {
        "tolerance achievability: bore",
        "tolerance achievability: seat",
        "stack-up: seat_to_bore",
    }
    rendered = str(change)
    assert "concept -> detailed: runs 3 more check(s)" in rendered
    for name in change.newly_run:
        assert f"runs: {name}" in rendered


def test_raising_the_depth_reports_what_it_newly_needs() -> None:
    from anvilate.needs import deepening
    from anvilate.spec import ScreeningDepth

    # A chain that links a dimension the document never declared: invisible at concept
    # depth, where chains are deferred, and a need as soon as the depth is raised.
    text = _DRAWN.replace("{dimension: seat, direction: -1}", "{dimension: shim, direction: -1}")
    concept = load_spec_yaml(
        text.replace(
            "acceptance: {tiers: [T1_analytical, T2_dfm]}",
            "acceptance: {tiers: [T1_analytical, T2_dfm], depth: concept}",
        )
    )
    change = deepening(concept, ScreeningDepth.DETAILED)
    assert [item.need.declaration for item in change.newly_required] == ["dimensions"]
    assert "needs: dimensions" in str(change)
    # The price is stated beside the return, not instead of it.
    assert change.newly_run and "runs 2 more check(s), needs 1 more declaration(s)" in str(change)


@pytest.mark.parametrize("to_depth", ["concept", "detailed"])
def test_a_raise_that_is_not_one_is_refused(to_depth: str) -> None:
    from anvilate.needs import deepening
    from anvilate.spec import ScreeningDepth

    with pytest.raises(ValueError, match="is not deeper than it"):
        deepening(_spec(), ScreeningDepth(to_depth))  # the document is already detailed


def test_the_depths_are_ordered_shallowest_first_and_not_alphabetically() -> None:
    from anvilate.screening import DEPTH_ORDER
    from anvilate.spec import ScreeningDepth

    assert DEPTH_ORDER == (ScreeningDepth.CONCEPT, ScreeningDepth.DETAILED)
    assert set(DEPTH_ORDER) == set(ScreeningDepth), "a depth outside the order cannot be compared"
    # Alphabetically 'concept' < 'detailed' agrees here, so the order is pinned by what each
    # depth screens instead: the deeper one is a superset of the shallower one's families.
    from anvilate.screening import _DEEPER_THAN_CONCEPT

    deferred = {entry.name for entry in screen_spec(_spec("concept")).out_of_depth()}
    assert deferred <= set(_DEEPER_THAN_CONCEPT)
    assert not screen_spec(_spec()).out_of_depth()
