"""Performance budgets: a declared rule, itemized terms, and a verdict on the combination."""

from __future__ import annotations

from math import sqrt

import pytest
from pydantic import ValidationError

from anvilate.budget import (
    Budget,
    CombinationRule,
    Contributor,
    ContributorBasis,
    LimitBasis,
)
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity


def _term(name: str, value: float | None, unit: str = "µrad", **fields: object) -> Contributor:
    declared: dict[str, object] = {
        "name": name,
        "value": None if value is None else Quantity(magnitude=value, unit=unit),
        "source": f"check {name}",
        "basis": ContributorBasis.CALCULATED,
    }
    declared.update(fields)
    return Contributor(**declared)  # type: ignore[arg-type]


def _budget(rule: CombinationRule | None, *terms: Contributor, limit: float = 100.0) -> Budget:
    return Budget(
        name="line of sight",
        quantity="pointing error",
        limit=Quantity(magnitude=limit, unit="µrad"),
        limit_basis=LimitBasis.REQUIREMENT,
        limit_source="SRD §4.2",
        rule=rule,
        contributors=terms,
    )


def _hybrid() -> Budget:
    return _budget(
        CombinationRule.HYBRID,
        _term("mount", 30.0, correlation_group="thermal"),
        _term("bench", 20.0, correlation_group="thermal"),
        _term("jitter", 40.0, basis=ContributorBasis.ESTIMATED),
        _term("alignment", 25.0, basis=ContributorBasis.MEASURED),
    )


def test_worst_case_and_rss_totals_and_margins() -> None:
    terms = (_term("a", 30.0), _term("b", 40.0))
    worst = _budget(CombinationRule.WORST_CASE, *terms).evaluate()
    rss = _budget(CombinationRule.RSS, *terms).evaluate()
    assert worst.total == pytest.approx(70.0, rel=1e-12)
    assert worst.margin == pytest.approx(30.0, rel=1e-12)
    assert rss.total == pytest.approx(50.0, rel=1e-12)
    assert rss.margin == pytest.approx(50.0, rel=1e-12)


def test_hybrid_sums_each_group_before_quadrature_and_shows_the_group_sums() -> None:
    result = _hybrid().evaluate()
    assert result.group_sums == (("thermal", pytest.approx(50.0, rel=1e-12)),)
    assert result.total == pytest.approx(sqrt(50.0**2 + 40.0**2 + 25.0**2), rel=1e-12)
    shares = [term.share for term in result.contributors]
    assert sum(shares) == pytest.approx(1.0, rel=1e-12)  # type: ignore[arg-type]


def test_rss_of_correlated_terms_is_refused_naming_the_group_and_the_hybrid_rule() -> None:
    with pytest.raises(ValidationError, match="'thermal'.*hybrid"):
        _budget(
            CombinationRule.RSS,
            _term("mount", 30.0, correlation_group="thermal"),
            _term("bench", 20.0, correlation_group="thermal"),
        )


def test_an_undeclared_rule_is_not_evaluated_rather_than_assumed() -> None:
    result = _budget(None, _term("a", 30.0)).evaluate()
    assert result.status is CheckStatus.NOT_EVALUATED
    assert result.total is None
    assert "no combination rule" in str(result.to_entry())


def test_one_unevaluated_contributor_makes_the_budget_not_evaluated_never_a_pass() -> None:
    result = _budget(
        CombinationRule.WORST_CASE,
        _term("mount", 1.0),
        _term("thermal drift", None, unresolved="material property missing"),
    ).evaluate()
    assert result.status is CheckStatus.NOT_EVALUATED
    assert result.total is None
    entry = result.to_entry()
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "thermal drift" in entry.detail and "material property missing" in entry.detail


def test_a_budget_of_passing_terms_can_fail_and_names_its_governing_contributor() -> None:
    # Every term is well inside the limit on its own; the combination is not.
    result = _budget(
        CombinationRule.WORST_CASE,
        _term("mount", 45.0),
        _term("bench", 35.0),
        _term("jitter", 30.0),
    ).evaluate()
    assert result.status is CheckStatus.FAIL
    assert result.governing == ("mount",)
    entry = result.to_entry()
    assert entry.status is CheckStatus.FAIL
    assert "governing: mount" in entry.detail
    passing = ScorecardEntry(name="mount check", status=CheckStatus.PASS, detail="inside")
    assert Scorecard(entries=(passing, entry)).status is CheckStatus.FAIL


def test_governing_is_computed_under_the_rule_not_taken_from_the_largest_value() -> None:
    # Jitter is the largest single value; the correlated mount governs, because removing it
    # also shrinks the group it is summed with before quadrature.
    result = _hybrid().evaluate()
    assert max(result.contributors, key=lambda t: t.value).name == "jitter"
    assert result.governing == ("mount",)


def test_equal_recoveries_are_reported_as_a_tie() -> None:
    result = _budget(CombinationRule.RSS, _term("a", 30.0), _term("b", 30.0)).evaluate()
    assert result.governing == ("a", "b")
    assert "governing (tied): a and b" in result.to_entry().detail


@pytest.mark.parametrize("rule", [CombinationRule.WORST_CASE, CombinationRule.RSS])
def test_headroom_round_trips_against_the_forward_evaluation(rule: CombinationRule) -> None:
    terms = (_term("a", 30.0), _term("b", 40.0), _term("c", 10.0))
    result = _budget(rule, *terms).evaluate()
    for index, term in enumerate(result.contributors):
        assert term.headroom is not None
        grown = list(terms)
        grown[index] = _term(term.name, term.headroom)
        assert _budget(rule, *grown).evaluate().margin == pytest.approx(0.0, abs=1e-9)


def test_hybrid_headroom_round_trips_for_grouped_and_independent_terms() -> None:
    budget = _hybrid()
    for term in budget.evaluate().contributors:
        assert term.headroom is not None and term.headroom > term.value
        grown = tuple(
            original.model_copy(update={"value": Quantity(magnitude=term.headroom, unit="µrad")})
            if original.name == term.name
            else original
            for original in budget.contributors
        )
        regrown = budget.model_copy(update={"contributors": grown}).evaluate()
        assert regrown.margin == pytest.approx(0.0, abs=1e-9)


def test_a_spent_budget_reports_no_headroom_with_the_overrun() -> None:
    result = _budget(CombinationRule.WORST_CASE, _term("a", 80.0), _term("b", 40.0)).evaluate()
    for term in result.contributors:
        assert term.headroom is None
        assert (
            term.headroom_unavailable == "the budget is already spent: the total is over the limit"
        )
    assert result.margin == pytest.approx(-20.0, rel=1e-12)


def test_a_dimension_mismatch_is_refused_naming_the_contributor_and_both_dimensions() -> None:
    with pytest.raises(ValidationError, match="'shim'.*length"):
        _budget(CombinationRule.WORST_CASE, _term("a", 1.0), _term("shim", 0.1, unit="mm"))


def test_one_check_cannot_contribute_twice() -> None:
    with pytest.raises(ValidationError, match="'first' and 'second'.*'deflection'"):
        _budget(
            CombinationRule.WORST_CASE,
            _term("first", 1.0, check="deflection"),
            _term("second", 2.0, check="deflection"),
        )


def test_a_bare_negative_is_refused_and_a_declared_compensation_is_shown_both_ways() -> None:
    with pytest.raises(ValidationError, match="not declared compensating"):
        _term("athermal", -10.0)
    result = _budget(
        CombinationRule.WORST_CASE,
        _term("drift", 60.0),
        _term("athermal", -10.0, compensating=True),
    ).evaluate()
    assert result.total == pytest.approx(50.0, rel=1e-12)
    assert result.total_without_compensation == pytest.approx(60.0, rel=1e-12)
    with pytest.raises(ValidationError, match="squaring a term discards its sign"):
        _budget(CombinationRule.RSS, _term("drift", 60.0), _term("a", -1.0, compensating=True))


def test_the_estimated_share_is_the_estimated_terms_share_of_the_total() -> None:
    result = _hybrid().evaluate()
    total = 50.0**2 + 40.0**2 + 25.0**2
    assert result.estimated_share == pytest.approx(40.0**2 / total, rel=1e-12)


def test_an_assumed_limit_is_labeled_on_the_entry() -> None:
    budget = _budget(CombinationRule.RSS, _term("a", 1.0)).model_copy(
        update={"limit_basis": LimitBasis.ASSUMPTION}
    )
    assert "working assumption" in budget.evaluate().to_entry().detail


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"value": None}, "exactly one"),
        ({"unresolved": "why"}, "exactly one"),
        ({"compensating": True}, "positive value"),
        ({"unit": "degC"}, "offset temperature"),
    ],
)
def test_malformed_contributors_are_refused(fields: dict[str, object], match: str) -> None:
    unit = str(fields.pop("unit", "µrad"))
    value = fields.pop("value", 5.0)
    with pytest.raises(ValidationError, match=match):
        _term("t", value, unit=unit, **fields)  # type: ignore[arg-type]


def test_a_budget_round_trips_and_its_entry_compares_total_to_limit() -> None:
    budget = _hybrid()
    assert Budget.model_validate_json(budget.model_dump_json()) == budget
    entry = budget.evaluate().to_entry()
    assert entry.comparison is not None and entry.comparison.passes()
    assert "pointing error total 68.739 µrad vs allocated 100.000 µrad" in (
        entry.comparison.sentence()
    )


def test_the_docs_page_prints_what_the_budget_computes() -> None:
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "performance-budgets.md").read_text()
    block = page.split("```python\n", 1)[1].split("```", 1)[0]
    scope: dict[str, object] = {}
    exec(block, scope)
    result = scope["result"]
    assert f"# {result.total:.2f} µrad" in block  # type: ignore[attr-defined]
    assert result.governing == ("mount",)  # type: ignore[attr-defined]
    assert f"# {result.estimated_share:.3f} " in block  # type: ignore[attr-defined]
    mount = result.contributors[0]  # type: ignore[attr-defined]
    assert f"could grow to {mount.headroom:.2f} µrad" in page


def test_the_rendered_result_itemizes_every_term_and_says_why_headroom_is_missing() -> None:
    lines = str(_hybrid().evaluate()).splitlines()
    assert lines[0].startswith("pointing error by hybrid: total 68.74 µrad")
    assert "  thermal: sum 50 µrad" in lines
    assert "  mount: 30 µrad, 31.7% of total, headroom 68.18 µrad" in lines
    assert len(lines) == 1 + 1 + 4

    spent = str(_budget(CombinationRule.WORST_CASE, _term("a", 80.0), _term("b", 40.0)).evaluate())
    assert "  a: 80 µrad, 66.7% of total, no headroom: the budget is already spent" in spent

    unresolved = _budget(CombinationRule.RSS, _term("a", None, unresolved="not measured"))
    assert str(unresolved.evaluate()) == (
        "budget line of sight: not evaluated — contributor 'a' has no value: not measured"
    )


def _checked(name: str, measured: float | None, *, unit: str = "µrad") -> ScorecardEntry:
    from anvilate.scorecard import Comparison, LimitSense

    if measured is None:
        return ScorecardEntry(name=name, status=CheckStatus.NOT_EVALUATED, detail="no modulus")
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS,
        detail="inside its own limit",
        comparison=Comparison(
            measured=Quantity(magnitude=measured, unit=unit),
            limit=Quantity(magnitude=60.0, unit=unit),
            sense=LimitSense.AT_MOST,
            measured_label="error",
            limit_label="limit",
        ),
    )


def _bound_budget() -> Budget:
    return _budget(
        CombinationRule.WORST_CASE,
        _term("mount", None, check="mount tilt", unresolved="bound at screening"),
        _term("bench", None, check="bench tilt", unresolved="bound at screening"),
        _term("alignment", 10.0),
    )


def test_a_budget_follows_the_screens_it_is_bound_to() -> None:
    budget = _bound_budget()
    before = budget.bind(
        Scorecard(entries=(_checked("mount tilt", 40.0), _checked("bench tilt", 30.0)))
    )
    after = budget.bind(
        Scorecard(entries=(_checked("mount tilt", 55.0), _checked("bench tilt", 30.0)))
    )
    assert before.evaluate().total == pytest.approx(80.0, rel=1e-12)
    assert before.evaluate().status is CheckStatus.PASS
    # Every screen still passes its own limit of 60; the combination no longer does.
    assert after.evaluate().total == pytest.approx(95.0, rel=1e-12)
    assert after.evaluate().status is CheckStatus.PASS
    worse = budget.bind(
        Scorecard(entries=(_checked("mount tilt", 59.0), _checked("bench tilt", 45.0)))
    )
    assert worse.evaluate().status is CheckStatus.FAIL


@pytest.mark.parametrize(
    ("entries", "reason"),
    [
        ((_checked("bench tilt", 30.0),), "check 'mount tilt' is not on the scorecard"),
        (
            (_checked("mount tilt", None), _checked("bench tilt", 30.0)),
            "check 'mount tilt' was not evaluated: no modulus",
        ),
        (
            (_checked("mount tilt", 1.0), _checked("mount tilt", 2.0), _checked("bench tilt", 3.0)),
            "the scorecard carries 2 checks named 'mount tilt'",
        ),
        (
            (
                ScorecardEntry(name="mount tilt", status=CheckStatus.PASS, detail="ok"),
                _checked("bench tilt", 30.0),
            ),
            "check 'mount tilt' carries no measured quantity to bind",
        ),
    ],
)
def test_a_broken_binding_makes_the_budget_not_evaluated_naming_it(entries, reason) -> None:
    # A value declared beside the binding is not kept: a stale number is worse than none.
    stale = _bound_budget().model_copy(
        update={
            "contributors": (
                _term("mount", 12.0, check="mount tilt"),
                *_bound_budget().contributors[1:],
            )
        }
    )
    result = stale.bind(Scorecard(entries=entries)).evaluate()
    assert result.status is CheckStatus.NOT_EVALUATED
    assert reason in (result.reason or "")


def test_a_bound_check_of_the_wrong_dimension_is_refused() -> None:
    card = Scorecard(entries=(_checked("mount tilt", 4.0, unit="mm"), _checked("bench tilt", 3.0)))
    with pytest.raises(ValidationError, match="'mount'.*length"):
        _bound_budget().bind(card)


_DECLARED_BUDGET = """budgets:
  - name: hook travel
    quantity: vertical deflection
    limit: {magnitude: 3.0, unit: mm}
    limit_basis: requirement
    limit_source: "lift plan LP-9"
    rule: worst_case
    contributors:
      - {name: sling stretch, value: {magnitude: 1.4, unit: mm}, source: "vendor data",
         basis: estimated}
      - {name: padeye bending, value: {magnitude: 0.9, unit: mm}, source: "T1 screen",
         basis: calculated}
      - {name: beam sag, value: {magnitude: 1.2, unit: mm}, source: "site survey",
         basis: measured}
"""


def _padeye_with(declaration: str):
    from pathlib import Path

    from anvilate.spec import load_spec_yaml

    text = (Path(__file__).parents[1] / "examples" / "padeye.spec.yaml").read_text()
    (anchor,) = [line for line in text.splitlines() if line.startswith("constraints:")]
    return load_spec_yaml(text.replace(anchor + "\n", declaration + anchor + "\n"))


def test_a_declared_budget_fails_a_card_whose_every_other_check_passes() -> None:
    from anvilate.screening import screen_spec

    spec = _padeye_with(_DECLARED_BUDGET)
    card = screen_spec(spec)
    (entry,) = [e for e in card.entries if e.name == "budget hook travel"]
    # The defect class: each check is inside its own limit and the combination is not.
    assert all(e.status is CheckStatus.PASS for e in card.entries if e is not entry)
    assert entry.status is CheckStatus.FAIL
    assert "total 3.5 mm against 3 mm" in entry.detail
    assert "governing: sling stretch" in entry.detail
    assert card.status is CheckStatus.FAIL
    assert card.governing() is entry


def test_a_declared_budget_round_trips_through_the_document() -> None:
    from anvilate.spec import parse_spec

    spec = _padeye_with(_DECLARED_BUDGET)
    assert parse_spec(spec.model_dump(mode="json")) == spec
    assert spec.anvilate_spec == "1.10.0"
    assert _padeye_with("").budgets == ()


def test_a_budget_bound_to_a_check_that_measured_nothing_is_named_never_dropped() -> None:
    from anvilate.screening import screen_spec

    bound = _DECLARED_BUDGET.replace(
        'source: "T1 screen",\n         basis: calculated}',
        'source: "T1 screen", basis: calculated, check: "padeye net tension"}',
    )
    (entry,) = [e for e in screen_spec(_padeye_with(bound)).entries if e.name.startswith("budget")]
    # The safety-factor check states two factors and no measured quantity, so there is
    # nothing to bind — said plainly, rather than the budget quietly leaving the card.
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "carries no measured quantity to bind" in entry.detail


def test_a_budget_refused_by_its_own_binding_is_an_entry_not_a_traceback() -> None:
    from anvilate.screening import _budget_entries

    bound = _DECLARED_BUDGET.replace(
        'source: "T1 screen",\n         basis: calculated}',
        'source: "T1 screen", basis: calculated, check: "tilt"}',
    )
    spec = _padeye_with(bound)
    # The bound check measured an angle where the budget is allocated in millimetres.
    (entry,) = _budget_entries(spec, [_checked("tilt", 30.0)])
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "could not be evaluated" in entry.detail and "padeye bending" in entry.detail


def _with_growth(*allowances) -> Budget:
    return _hybrid().model_copy(update={"growth": allowances})


def test_a_growth_allowance_is_applied_and_recorded_as_a_ledger_entry() -> None:
    from anvilate.budget import GrowthAllowance
    from anvilate.margin import MarginKind

    budget = _with_growth(
        GrowthAllowance(
            basis=ContributorBasis.ESTIMATED, factor=1.25, authority="company practice DP-104"
        )
    )
    result = budget.evaluate()
    plain = _hybrid().evaluate()
    # The estimated jitter grows by 25%; nothing else moves.
    jitter = next(t for t in result.contributors if t.name == "jitter")
    assert jitter.value == pytest.approx(40.0 * 1.25, rel=1e-12)
    assert result.total > plain.total
    # And the allowance is visible as conservatism rather than absorbed into the value.
    (entry,) = result.ledger().entries
    assert entry.kind is MarginKind.CONTINGENCY
    assert entry.value == pytest.approx(1.25, rel=1e-12)
    assert entry.label == "estimated growth allowance on jitter"
    assert entry.origin == "budget line of sight: jitter"
    assert entry.authority == "company practice DP-104"
    assert result.ledger().stack("pointing error").cumulative == pytest.approx(1.25, rel=1e-12)
    # Growing the estimate is what makes it govern: it was mount before.
    assert result.governing == ("jitter",)


def test_a_budget_with_no_allowance_records_no_entry() -> None:
    assert _hybrid().evaluate().ledger().entries == ()
    from anvilate.budget import GrowthAllowance

    unit = _with_growth(
        GrowthAllowance(basis=ContributorBasis.MEASURED, factor=1.0, authority="none needed")
    )
    assert unit.evaluate().margins == ()
    assert unit.evaluate().total == pytest.approx(_hybrid().evaluate().total, rel=1e-12)


def test_two_allowances_on_one_basis_are_refused() -> None:
    from anvilate.budget import GrowthAllowance

    with pytest.raises(ValidationError, match="two growth allowances for one basis"):
        _with_growth(
            GrowthAllowance(basis=ContributorBasis.ESTIMATED, factor=1.1, authority="DP-104"),
            GrowthAllowance(basis=ContributorBasis.ESTIMATED, factor=1.2, authority="DP-104"),
        )


@pytest.mark.parametrize("factor", [0.9, 0.0, -1.0, float("nan"), float("inf")])
def test_an_allowance_that_is_not_one_is_refused(factor: float) -> None:
    from anvilate.budget import GrowthAllowance

    with pytest.raises(ValidationError, match="at least 1"):
        GrowthAllowance(basis=ContributorBasis.ESTIMATED, factor=factor, authority="DP-104")


def test_an_allowance_needs_an_authority() -> None:
    from anvilate.budget import GrowthAllowance

    with pytest.raises(ValidationError, match="must state"):
        GrowthAllowance(basis=ContributorBasis.ESTIMATED, factor=1.1, authority="  ")


def _subsystem() -> Budget:
    return Budget(
        name="optics module",
        quantity="module error",
        limit=Quantity(magnitude=45.0, unit="µrad"),
        limit_basis=LimitBasis.DERIVED,
        limit_source="allocated from the system budget",
        rule=CombinationRule.RSS,
        contributors=(_term("lens tilt", 24.0), _term("detector", 18.0)),
    )


def _system(sub: Budget | None = None) -> Budget:
    return _budget(
        CombinationRule.WORST_CASE,
        _term("subsystem", None, sub_budget=sub or _subsystem()),
        _term("structure", 40.0),
    )


def test_a_sub_budget_keeps_its_own_rule_and_enters_as_one_value() -> None:
    result = _system().evaluate()
    inner = sqrt(24.0**2 + 18.0**2)  # the subsystem's own quadrature
    assert result.total == pytest.approx(inner + 40.0, rel=1e-12)  # summed in the parent
    rendered = str(result)
    assert "subsystem: 30 µrad" in rendered
    assert "sub-budget by rss" in rendered
    assert "by worst case" in rendered.splitlines()[0]


def test_a_sub_budget_that_could_not_be_evaluated_stops_the_parent_naming_it() -> None:
    blocked = _subsystem().model_copy(update={"rule": None})
    result = _system(blocked).evaluate()
    assert result.status is CheckStatus.NOT_EVALUATED
    assert "sub-budget 'optics module', which was not evaluated" in (result.reason or "")
    assert "no combination rule" in (result.reason or "")


def test_a_budget_that_reaches_itself_is_refused_naming_the_chain() -> None:
    inner = _subsystem().model_copy(update={"name": "line of sight"})
    with pytest.raises(ValidationError, match="reaches itself.*line of sight -> line of sight"):
        _system(inner)


def test_nesting_deeper_than_the_bound_is_refused() -> None:
    from anvilate.budget import _MAX_NESTING

    budget = _subsystem().model_copy(update={"name": "level 0"})
    for level in range(1, _MAX_NESTING):
        budget = Budget(
            name=f"level {level}",
            quantity="module error",
            limit=Quantity(magnitude=45.0, unit="µrad"),
            limit_basis=LimitBasis.DERIVED,
            limit_source="allocated from its parent",
            rule=CombinationRule.RSS,
            contributors=(_term("child", None, sub_budget=budget),),
        )
    assert budget.evaluate().total is not None  # exactly at the bound
    with pytest.raises(ValidationError, match=f"nests {_MAX_NESTING + 1} deep"):
        Budget(
            name="one too deep",
            quantity="module error",
            limit=Quantity(magnitude=45.0, unit="µrad"),
            limit_basis=LimitBasis.DERIVED,
            limit_source="allocated from its parent",
            rule=CombinationRule.RSS,
            contributors=(_term("child", None, sub_budget=budget),),
        )


def test_a_sub_budget_of_the_wrong_dimension_is_refused_before_it_is_evaluated() -> None:
    millimetres = _subsystem().model_copy(
        update={
            "limit": Quantity(magnitude=3.0, unit="mm"),
            "contributors": (_term("a", 1.0, "mm"),),
        }
    )
    with pytest.raises(ValidationError, match=r"'subsystem' is \[length\]"):
        _system(millimetres)


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"value": 1.0, "sub_budget": True}, "exactly one"),
        ({"compensating": True, "sub_budget": True}, "cannot hand back allocation"),
    ],
)
def test_a_malformed_sub_budget_term_is_refused(fields: dict, match: str) -> None:
    value = fields.pop("value", None)
    if fields.pop("sub_budget", False):
        fields["sub_budget"] = _subsystem()
    with pytest.raises(ValidationError, match=match):
        _term("subsystem", value, **fields)
