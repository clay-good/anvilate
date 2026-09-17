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
        assert "overruns the limit by 20" in (term.headroom_unavailable or "")


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
