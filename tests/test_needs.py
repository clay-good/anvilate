"""The needs report: what the build needs next, ordered by leverage and never by severity."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.needs import LEVERAGE_IS_NOT_IMPORTANCE, NeedsReport, needs_report
from anvilate.scorecard import CheckStatus, Need, Scorecard, ScorecardEntry, ValueSource


def _need(declaration: str, /, **fields: object) -> Need:
    declared: dict[str, object] = {
        "declaration": declaration,
        "takes": f"the value {declaration} states",
        "sources": (ValueSource.USER,),
    }
    declared.update(fields)
    return Need(**declared)  # type: ignore[arg-type]


def _blocked(name: str, *needs: Need) -> ScorecardEntry:
    return ScorecardEntry(
        name=name,
        status=CheckStatus.NOT_EVALUATED,
        detail="could not run",
        needs=needs,
    )


def test_eleven_blocked_checks_behind_four_declarations_are_four_items() -> None:
    # The defect class this report exists to remove: a wall of red with no next move.
    damping = _need("environment.damping")
    orientation = _need("element_params.orientation")
    factor = _need("constraints.min_safety_factor")
    fill = _need("element_params.fill_condition")
    entries = [
        _blocked("check 1", damping, orientation),
        _blocked("check 2", damping),
        _blocked("check 3", damping),
        _blocked("check 4", damping),
        _blocked("check 5", damping),
        _blocked("check 6", orientation),
        _blocked("check 7", orientation),
        _blocked("check 8", factor),
        _blocked("check 9", factor),
        _blocked("check 10", fill),
        _blocked("check 11", fill),
    ]
    report = needs_report(Scorecard(entries=tuple(entries)))
    assert len(report) == 4
    assert [item.need.declaration for item in report.items] == [
        "environment.damping",
        "element_params.orientation",
        "constraints.min_safety_factor",
        "element_params.fill_condition",
    ]
    assert [item.leverage for item in report.items] == [5, 3, 2, 2]
    # The entries each item would resolve are named, not counted.
    damping_item = report.items[0]
    assert damping_item.unblocks == ("check 1", "check 2", "check 3", "check 4", "check 5")


def test_the_order_follows_the_counts_and_says_it_is_not_importance() -> None:
    report = needs_report(
        Scorecard(
            entries=(
                _blocked("secondary a", _need("b.secondary")),
                _blocked("secondary b", _need("b.secondary")),
                _blocked("the governing check", _need("a.critical")),
            )
        )
    )
    # Leverage, not severity: the item behind the governing check is second.
    assert [item.need.declaration for item in report.items] == ["b.secondary", "a.critical"]
    rendered = str(report)
    assert LEVERAGE_IS_NOT_IMPORTANCE in rendered
    assert "unblocks 2: secondary a, secondary b" in rendered
    assert "unblocks 1: the governing check" in rendered


def test_equal_leverage_is_reported_as_a_tie() -> None:
    report = needs_report(
        Scorecard(
            entries=(
                _blocked("one", _need("a.first")),
                _blocked("two", _need("b.second")),
                _blocked("three", _need("c.third"), _need("d.fourth")),
            )
        )
    )
    (group,) = report.tied()
    assert len(group) == 4  # every item unblocks exactly one check
    assert str(report).count("(tied)") == 4

    mixed = needs_report(
        Scorecard(entries=(_blocked("one", _need("a")), _blocked("two", _need("a"), _need("b"))))
    )
    assert [len(group) for group in mixed.tied()] == [1, 1]
    assert "(tied)" not in str(mixed)


def test_a_passing_card_with_a_gap_still_reports_it() -> None:
    card = Scorecard(
        entries=(
            ScorecardEntry(name="ran", status=CheckStatus.PASS, detail="fine"),
            _blocked("did not run", _need("constraints.min_safety_factor")),
        )
    )
    assert card.status is CheckStatus.NOT_EVALUATED  # the card is honest either way
    report = needs_report(card)
    assert len(report) == 1
    assert report.items[0].unblocks == ("did not run",)


def test_a_card_with_nothing_missing_says_so() -> None:
    card = Scorecard(entries=(ScorecardEntry(name="ran", status=CheckStatus.PASS, detail="fine"),))
    report = needs_report(card)
    assert len(report) == 0
    assert str(report) == "needs: every declaration the screens reached for was supplied"
    assert str(NeedsReport()) == str(report)


@pytest.mark.parametrize("status", [CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.OVER_MARGIN])
def test_a_check_that_ran_cannot_name_a_need(status: CheckStatus) -> None:
    # Otherwise the report sends a reader to supply a value that would change nothing.
    with pytest.raises(ValidationError, match="a check that ran had what it needed"):
        ScorecardEntry(
            name="ran",
            status=status,
            detail="fine",
            safety_factor=2.0,
            required_safety_factor=1.5,
            needs=(_need("constraints.min_safety_factor"),),
        )


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"sources": ()}, "at least 1 item"),
        ({"sources": (ValueSource.USER, ValueSource.USER)}, "names a source twice"),
        ({"units": ("mm",)}, "and no dimension"),
        ({"takes": "  "}, "must state"),
        ({"declaration": ""}, "must state"),
    ],
)
def test_a_malformed_need_is_refused(fields: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _need("constraints.min_safety_factor", **fields)


def test_a_need_renders_its_units_and_where_a_value_comes_from() -> None:
    need = _need(
        "constraints.min_safety_factor",
        dimension="dimensionless",
        units=("", "1"),
        sources=(ValueSource.STANDARD, ValueSource.USER),
    )
    assert "from standard, user statement" in str(need)
    length = _need("element_params.thickness", dimension="[length]", units=("mm", "in"))
    assert "in mm or in" in str(length)


def test_the_screens_own_refusals_carry_their_needs() -> None:
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    bare = load_spec_yaml(
        """
anvilate_spec: "1.3.0"
name: bare
description: A part with almost nothing declared.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: cnc_milling}
acceptance: {tiers: [T1_analytical, T2_dfm]}
"""
    )
    report = needs_report(screen_spec(bare))
    assert [item.need.declaration for item in report.items] == [
        "element_type",
        "element_params",
        "dimensions",
    ]
    # Every item names a real field of the document, so the next action is one edit.
    from anvilate.spec.ir import DesignSpec

    for item in report.items:
        root = item.need.declaration.split(".")[0].split("[")[0]
        assert root in DesignSpec.model_fields

    declared = load_spec_yaml(
        """
anvilate_spec: "1.3.0"
name: lug
description: A lifting lug with its element declared and no safety factor.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
element_type: lifting_lug
element_params:
  name: padeye
  material: ASTM-A36
  width: {magnitude: 120.0, unit: mm}
  hole_diameter: {magnitude: 40.0, unit: mm}
  thickness: {magnitude: 20.0, unit: mm}
  load: {magnitude: 60.0, unit: kN}
"""
    )
    # Declaring the element moves the gap on: now it is the factor the screen is judged by.
    factor = needs_report(screen_spec(declared))
    assert [item.need.declaration for item in factor.items] == ["constraints.min_safety_factor"]
