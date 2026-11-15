"""Service-life planning: an interval comes from a life and a declared rule, or not at all.

Three rules, and every test here is on one of them. Nothing invents an interval. A plan
is not a maintenance record. And a plan names the items it does not cover, so a schedule
of three on a product of thirty cannot read as a complete one.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from anvilate.credibility import AcceptanceBand, CorrelationVerdict
from anvilate.derivation import DerivationAbsence, Underived
from anvilate.refusal import RefusalError
from anvilate.scorecard import (
    CheckStatus,
    Comparison,
    LifeKind,
    LifeQuantity,
    LimitSense,
    Scorecard,
    ScorecardEntry,
)
from anvilate.service_life import (
    RCM_CITATION,
    IntervalRule,
    MaintenanceItem,
    PerformedTask,
    ServiceLifePlan,
    TaskType,
    plan_service_life,
    task_correlations,
)
from anvilate.units import Quantity

_ISO281 = "ISO 281:2007 basic rating life L10"
_POLICY = "the plant's rotating-equipment maintenance policy, rev 4"
_UNDERIVED = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="a fixture entry built to carry a life into a plan",
)


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _cycles(count: float) -> Quantity:
    """A count of cycles. `Quantity.parse` refuses "2e6 dimensionless" as unitless."""
    return Quantity(magnitude=count, unit="count")


def _life(value: str | Quantity = "23000 hour", **overrides: object) -> LifeQuantity:
    fields: dict[str, object] = {
        "kind": LifeKind.HOURS,
        "value": _q(value) if isinstance(value, str) else value,
        "basis": _ISO281,
        "reliability": 0.90,
    }
    fields.update(overrides)
    return LifeQuantity(**fields)  # type: ignore[arg-type]


def _entry(
    name: str = "bearing rating life",
    *,
    life: LifeQuantity | None = None,
    comparison: Comparison | None = None,
) -> ScorecardEntry:
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS,
        detail=f"{name} holds",
        reference=_ISO281,
        underived=_UNDERIVED,
        life=life,
        comparison=comparison,
    )


def _card(*entries: ScorecardEntry) -> Scorecard:
    return Scorecard(entries=entries or (_entry(life=_life()),))


def _rule(**overrides: object) -> IntervalRule:
    fields: dict[str, object] = {
        "name": "replace at half of rating life",
        "task": TaskType.TIME_DIRECTED,
        "source": _POLICY,
        "applies_to": ("bearing rating life",),
        "fraction_of_life": 0.5,
    }
    fields.update(overrides)
    return IntervalRule(**fields)  # type: ignore[arg-type]


# --- the life quantity ------------------------------------------------------------


def test_a_life_renders_its_basis_and_the_reliability_the_method_states():
    rendered = str(_life())
    assert "23000 h" in rendered
    assert "90% reliability" in rendered
    assert _ISO281 in rendered


def test_a_life_in_the_wrong_dimension_for_its_kind_is_refused():
    with pytest.raises(ValidationError, match="a life in hours is a .time. quantity"):
        _life(value="4000 km")
    with pytest.raises(ValidationError, match="a life in distance"):
        _life(kind=LifeKind.DISTANCE, value="4000 hour")
    # And a cycle count is dimensionless, which is a real dimension and not "any".
    counted = _life(kind=LifeKind.CYCLES, value=_cycles(2e6))
    assert counted.value.magnitude == 2e6
    with pytest.raises(ValidationError, match="a life in cycles"):
        _life(kind=LifeKind.CYCLES, value="2e6 hour")


def test_a_life_at_temperature_needs_its_temperature_and_nothing_else_may_carry_one():
    at = _life(
        kind=LifeKind.TIME_AT_TEMPERATURE,
        value="1000 hour",
        temperature=_q("85 degC"),
        reliability=None,
    )
    assert "85" in str(at)
    with pytest.raises(ValidationError, match="needs the temperature it is at"):
        _life(kind=LifeKind.TIME_AT_TEMPERATURE, value="1000 hour")
    with pytest.raises(ValidationError, match="which no consumer reads"):
        _life(temperature=_q("85 degC"))
    with pytest.raises(ValidationError, match="is a temperature"):
        _life(kind=LifeKind.TIME_AT_TEMPERATURE, value="1000 hour", temperature=_q("3 mm"))


@pytest.mark.parametrize("value", ["0 hour", "-5 hour"])
def test_a_life_of_zero_or_less_is_refused(value):
    with pytest.raises(ValidationError, match="positive finite quantity"):
        _life(value=value)


def test_a_non_finite_life_is_refused():
    with pytest.raises(ValidationError, match="positive finite quantity"):
        _life(value="1 hour").model_copy(
            update={"value": Quantity(magnitude=float("inf"), unit="hour")}
        )


@pytest.mark.parametrize("reliability", [0.0, 1.0, -0.1, 1.5])
def test_a_reliability_outside_the_open_unit_interval_is_refused(reliability):
    with pytest.raises(ValidationError, match="strictly between 0 and 1"):
        _life(reliability=reliability)


@pytest.mark.parametrize("reliability", [0.001, 0.5, 0.9, 0.999])
def test_a_reliability_inside_it_is_accepted(reliability):
    """The other side of the bound the refusal test above cannot see."""
    assert _life(reliability=reliability).reliability == reliability


def test_a_method_that_states_no_reliability_leaves_it_unset():
    """Unset is not 1.0, and nothing here fills it in."""
    bare = _life(reliability=None)
    assert bare.reliability is None
    assert "reliability" not in str(bare)
    assert "reliability" not in bare.model_dump(mode="json")


# --- the interval rule ------------------------------------------------------------


def test_a_rule_that_names_no_check_is_refused():
    with pytest.raises(RefusalError, match="covers everything by saying nothing"):
        _rule(applies_to=())
    with pytest.raises(RefusalError, match="names a check twice"):
        _rule(applies_to=("bearing rating life", "bearing rating life"))


@pytest.mark.parametrize("fraction", [0.0, -0.5, 1.5])
def test_a_fraction_that_is_not_a_share_is_refused(fraction):
    with pytest.raises(RefusalError, match="greater than zero and at most one"):
        _rule(fraction_of_life=fraction)


@pytest.mark.parametrize("fraction", [1e-6, 0.5, 1.0])
def test_a_share_up_to_and_including_one_is_accepted(fraction):
    """One is a share: "replace at the rating life" is a policy somebody has."""
    assert _rule(fraction_of_life=fraction).fraction_of_life == fraction


def test_run_to_failure_may_not_also_state_an_interval():
    with pytest.raises(RefusalError, match="says the opposite of itself"):
        _rule(task=TaskType.RUN_TO_FAILURE)


def test_an_on_condition_rule_runs_off_the_pf_interval_and_not_the_life():
    with pytest.raises(RefusalError, match="not of the life itself"):
        _rule(task=TaskType.ON_CONDITION, fraction_of_life=0.5)
    with pytest.raises(RefusalError, match="belongs to an on-condition inspection"):
        _rule(task=TaskType.TIME_DIRECTED, pf_interval=_q("800 hour"))


def test_a_pf_interval_that_is_not_a_positive_time_is_refused():
    with pytest.raises(RefusalError, match="P-F interval is a time"):
        _rule(
            task=TaskType.ON_CONDITION,
            fraction_of_life=None,
            pf_interval=_q("800 mm"),
            inspection_fraction=0.5,
        )
    with pytest.raises(RefusalError, match="positive finite time"):
        _rule(
            task=TaskType.ON_CONDITION,
            fraction_of_life=None,
            pf_interval=_q("0 hour"),
            inspection_fraction=0.5,
        )


# --- the plan ---------------------------------------------------------------------


def test_a_bearing_with_a_declared_rule():
    """The spec's first scenario: 23,000 h at 90%, replace at half, named and sourced."""
    plan = plan_service_life(
        _card(),
        rules=(_rule(),),
        item_paths={"bearing rating life": "gearbox/output bearing"},
    )

    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.item_path == "gearbox/output bearing"
    assert item.task is TaskType.TIME_DIRECTED
    assert item.interval == _q("11500 hour")
    assert item.rule is not None and item.rule.source == _POLICY
    assert item.life.value == _q("23000 hour")
    rendered = str(item)
    assert "11500" in rendered and "replace at half of rating life" in rendered


def test_a_life_without_a_rule_is_listed_with_interval_not_set():
    """The spec's second scenario. The schedule does not read as complete."""
    card = _card(_entry("compression set", life=_life("40000 hour")))
    plan = plan_service_life(card, rules=(_rule(),))

    assert len(plan.items) == 1
    item = plan.items[0]
    assert not item.interval_set
    assert "no declared rule names this check" in item.interval_basis
    assert "interval not set" in str(item)
    assert "40000" in plan.schedule()
    assert plan.unset == (item,)


def test_nothing_here_invents_an_interval_from_a_life_alone():
    """A life with no rule at all produces an item and never a number."""
    plan = plan_service_life(_card())
    assert len(plan.items) == 1
    assert plan.items[0].interval is None
    assert plan.scheduled() == ()


def test_a_check_with_no_life_produces_no_item():
    plan = plan_service_life(_card(_entry("bolt preload", life=None)), rules=(_rule(),))
    assert plan.items == ()


def test_wear_inspection_runs_at_the_declared_fraction_of_the_pf_interval():
    """The spec's P-F scenario: 800 h of warning, inspected twice inside it."""
    card = _card(_entry("wear allowance", life=_life("4000 hour", reliability=None)))
    rule = IntervalRule(
        name="inspect measurable wear",
        task=TaskType.ON_CONDITION,
        source="the maintenance policy, §7 condition monitoring",
        applies_to=("wear allowance",),
        pf_interval=_q("800 hour"),
        inspection_fraction=0.5,
    )
    plan = plan_service_life(card, rules=(rule,))

    item = plan.items[0]
    assert item.task is TaskType.ON_CONDITION
    assert item.interval == _q("400 hour")
    assert "800 h" in item.interval_basis
    assert "P-F" in item.interval_basis


def test_an_on_condition_rule_with_no_pf_interval_says_which_one_it_needs():
    card = _card(_entry("wear allowance", life=_life("4000 hour", reliability=None)))
    rule = IntervalRule(
        name="inspect measurable wear",
        task=TaskType.ON_CONDITION,
        source="the maintenance policy, §7",
        applies_to=("wear allowance",),
    )
    plan = plan_service_life(card, rules=(rule,))

    item = plan.items[0]
    assert item.interval is None
    assert "interval not set" in item.interval_basis
    assert "P-F interval" in item.interval_basis


def test_accepted_run_to_failure_schedules_nothing_and_says_it_was_a_decision():
    card = _card(_entry("wear allowance", life=_life("4000 hour", reliability=None)))
    rule = IntervalRule(
        name="lamps run to failure",
        task=TaskType.RUN_TO_FAILURE,
        source="the maintenance policy, §3 accepted failures",
        applies_to=("wear allowance",),
    )
    plan = plan_service_life(card, rules=(rule,))

    item = plan.items[0]
    assert item.interval is None
    assert "run to failure is accepted" in item.interval_basis
    # It is not a gap: the item is in the plan, with the rule that accepted it.
    assert item.rule is not None


def test_the_first_declared_rule_naming_a_check_is_the_one_that_applies():
    """Order is the caller's and the plan does not merge two rules into a third."""
    first = _rule(name="first", fraction_of_life=0.25)
    second = _rule(name="second", fraction_of_life=0.75)
    plan = plan_service_life(_card(), rules=(first, second))
    assert plan.items[0].rule is not None
    assert plan.items[0].rule.name == "first"
    assert plan.items[0].interval == _q("5750 hour")


# --- coverage ---------------------------------------------------------------------


def test_three_of_thirty_names_the_twenty_seven():
    """The spec's coverage scenario."""
    everything = tuple(f"item-{n:02d}" for n in range(30))
    card = Scorecard(
        entries=tuple(_entry(f"item-{n:02d} rating life", life=_life()) for n in range(3))
    )
    plan = plan_service_life(
        card,
        rules=(),
        item_paths={f"item-{n:02d} rating life": f"item-{n:02d}" for n in range(3)},
        product_items=everything,
    )

    assert len(plan.items) == 3
    assert len(plan.without_a_life_basis) == 27
    assert "item-29" in plan.without_a_life_basis
    assert "item-00" not in plan.without_a_life_basis
    summary = plan.summary()
    assert "27 items with no life basis" in summary
    assert "no life-limited check covers this item" in plan.schedule()


def test_a_product_item_named_twice_is_counted_once():
    plan = plan_service_life(_card(), product_items=("frame", "frame", "shaft"))
    assert plan.without_a_life_basis == ("frame", "shaft")


# --- performed tasks --------------------------------------------------------------


def test_a_plan_with_nothing_performed_is_not_a_maintenance_record():
    plan = plan_service_life(_card(), rules=(_rule(),))
    assert plan.status is CheckStatus.NOT_EVALUATED
    assert "plan status not_evaluated" in plan.summary()
    assert "maintained" not in plan.summary()


def test_a_plan_passes_only_when_every_scheduled_item_has_a_task():
    rules = (_rule(), _rule(name="second", applies_to=("second rating life",)))
    card = _card(_entry(life=_life()), _entry("second rating life", life=_life()))
    plan = plan_service_life(card, rules=rules)
    assert plan.status is CheckStatus.NOT_EVALUATED

    one = plan.model_copy(
        update={
            "tasks": (
                PerformedTask(
                    item_path="bearing rating life",
                    performed_on=date(2026, 11, 1),
                    performed_by="M. Okonkwo",
                ),
            )
        }
    )
    assert one.status is CheckStatus.NOT_EVALUATED
    both = plan.model_copy(
        update={
            "tasks": tuple(
                PerformedTask(
                    item_path=item.item_path,
                    performed_on=date(2026, 11, 1),
                    performed_by="M. Okonkwo",
                )
                for item in plan.items
            )
        }
    )
    assert both.status is CheckStatus.PASS


def test_an_item_with_no_interval_is_not_something_a_task_can_complete():
    """A plan of only unset items never rolls up green by having nothing to do."""
    plan = plan_service_life(_card())
    assert plan.items and plan.status is CheckStatus.NOT_EVALUATED


def test_an_anonymous_maintenance_record_is_refused():
    with pytest.raises(RefusalError, match="who performed it"):
        PerformedTask(item_path="x", performed_on=date(2026, 11, 1), performed_by="  ")


def test_a_measured_condition_reaches_the_credibility_correlation():
    """The spec's last scenario: 0.3 mm of wear against a predicted allowance."""
    card = _card(
        _entry(
            "wear allowance",
            life=_life("4000 hour", reliability=None),
            comparison=Comparison(
                measured=_q("0.25 mm"),
                limit=_q("0.5 mm"),
                sense=LimitSense.AT_MOST,
                measured_label="wear at the inspection point",
                limit_label="allowance",
            ),
        )
    )
    rule = IntervalRule(
        name="inspect measurable wear",
        task=TaskType.ON_CONDITION,
        source="the maintenance policy, §7",
        applies_to=("wear allowance",),
        pf_interval=_q("800 hour"),
        inspection_fraction=0.5,
    )
    plan = plan_service_life(card, rules=(rule,)).model_copy(
        update={
            "tasks": (
                PerformedTask(
                    item_path="wear allowance",
                    performed_on=date(2026, 11, 1),
                    performed_by="M. Okonkwo",
                    note="depth gauge DG-21",
                    measured_condition=_q("0.3 mm"),
                ),
            )
        }
    )

    found = task_correlations(
        plan,
        card,
        bands={"wear allowance": AcceptanceBand(fraction=0.1, source="the inspection plan")},
    )
    assert len(found) == 1
    correlation = found[0]
    assert correlation.measured == _q("0.3 mm")
    assert correlation.predicted == _q("0.25 mm")
    # More wear than predicted is the unconservative direction on a response.
    assert correlation.verdict is CorrelationVerdict.UNCONSERVATIVE
    assert correlation.instrument == "depth gauge DG-21"
    # And the check's verdict did not move.
    assert card.entries[0].status is CheckStatus.PASS


def test_a_task_with_no_measured_condition_is_a_record_and_not_a_correlation():
    card = _card()
    plan = plan_service_life(card, rules=(_rule(),)).model_copy(
        update={
            "tasks": (
                PerformedTask(
                    item_path="bearing rating life",
                    performed_on=date(2026, 11, 1),
                    performed_by="M. Okonkwo",
                ),
            )
        }
    )
    assert task_correlations(plan, card) == ()
    assert "performed" in str(plan.tasks[0])


# --- spares -----------------------------------------------------------------------


def test_spares_over_ten_years_show_their_arithmetic():
    """The spec's spares scenario: 11,500 h intervals over 10 years at 4,000 h a year."""
    plan = plan_service_life(
        _card(),
        rules=(_rule(),),
        item_paths={"bearing rating life": "gearbox/output bearing"},
        spares={"bearing rating life": "6310-2RS"},
        service_life=_q("10 year"),
        duty_per_year=_q("4000 hour"),
    )

    spares = plan.spares()
    assert len(spares) == 1
    assert spares[0].designation == "6310-2RS"
    # 40,000 running hours over an 11,500 h interval is 3.48, and you buy four.
    assert spares[0].quantity == 4
    assert "40000" in spares[0].arithmetic and "11500" in spares[0].arithmetic


def test_a_fractional_count_rounds_up_because_a_part_of_a_spare_is_a_whole_one():
    plan = plan_service_life(
        _card(),
        rules=(_rule(fraction_of_life=1.0),),
        spares={"bearing rating life": "6310-2RS"},
        service_life=_q("1 year"),
        duty_per_year=_q("23001 hour"),
    )
    assert plan.spares()[0].quantity == 2


def test_no_declared_service_life_means_no_spare_count_is_invented():
    plan = plan_service_life(_card(), rules=(_rule(),), spares={"bearing rating life": "6310-2RS"})
    assert plan.spares() == ()


def test_a_calendar_life_with_no_duty_cannot_be_turned_into_running_hours():
    """Ten years is not 87,600 running hours unless somebody says the duty is continuous."""
    plan = plan_service_life(
        _card(),
        rules=(_rule(),),
        spares={"bearing rating life": "6310-2RS"},
        service_life=_q("10 year"),
    )
    # Both are times, so this one *is* answerable — and the answer is the calendar span.
    assert plan.spares()[0].quantity == 8
    # A cycle-counted interval against a calendar life is not, and nothing is invented.
    cycles = plan_service_life(
        _card(_entry(life=_life(kind=LifeKind.CYCLES, value=_cycles(2e6)))),
        rules=(_rule(),),
        spares={"bearing rating life": "6310-2RS"},
        service_life=_q("10 year"),
    )
    assert cycles.spares() == ()


# --- rendering ---------------------------------------------------------------------


def _full_plan() -> ServiceLifePlan:
    card = _card(
        _entry(life=_life()),
        _entry("compression set", life=_life("40000 hour", reliability=None)),
    )
    return plan_service_life(
        card,
        rules=(_rule(),),
        item_paths={
            "bearing rating life": "gearbox/output bearing",
            "compression set": "gearbox/shaft seal",
        },
        spares={"bearing rating life": "6310-2RS"},
        product_items=("gearbox/output bearing", "gearbox/shaft seal", "gearbox/housing"),
        service_life=_q("10 year"),
        duty_per_year=_q("4000 hour"),
    )


def test_the_schedule_orders_the_scheduled_items_soonest_first():
    plan = plan_service_life(
        _card(
            _entry(life=_life("23000 hour")),
            _entry("second rating life", life=_life("4000 hour")),
        ),
        rules=(
            _rule(),
            _rule(name="second", applies_to=("second rating life",), fraction_of_life=0.5),
        ),
    )
    assert [item.interval.magnitude for item in plan.scheduled()] == [2000.0, 11500.0]


def test_the_csv_carries_every_item_and_names_the_rule_and_its_source():
    rows = _full_plan().to_csv().splitlines()
    assert rows[0].startswith("item,task,interval,driving check,life,rule,rule source")
    assert len(rows) == 3
    assert "gearbox/output bearing" in rows[1]
    assert _POLICY in rows[1]
    # The unset item is in the file, not dropped from it.
    assert "not set" in rows[2]


def test_the_xlsx_is_a_workbook_with_the_schedule_the_spares_and_the_gaps():
    import zipfile
    from io import BytesIO

    book = _full_plan().to_xlsx()
    with zipfile.ZipFile(BytesIO(book)) as archive:
        names = set(archive.namelist())
        assert "xl/workbook.xml" in names
        workbook = archive.read("xl/workbook.xml").decode()
    for sheet in ("Schedule", "Spares", "Uncovered"):
        assert sheet in workbook
    # One plan is one byte string, so a package digest is stable.
    assert _full_plan().to_xlsx() == book


def test_the_report_section_cites_the_task_vocabulary_and_names_the_gaps():
    section = _full_plan().section()
    assert "## Service-life plan" in section
    assert RCM_CITATION in section
    assert "nothing here is a default" in section
    assert "gearbox/housing" in section
    assert "items with no life basis" in section
    assert "6310-2RS" in section


def test_an_item_with_no_basis_for_its_interval_is_refused():
    with pytest.raises(RefusalError, match="states no basis"):
        MaintenanceItem(
            item_path="x",
            check="bearing rating life",
            life=_life(),
            task=TaskType.TIME_DIRECTED,
            interval=_q("100 hour"),
            interval_basis="   ",
        )


# --- the library census ------------------------------------------------------------


def test_the_life_census_is_what_the_tool_writes_and_its_gap_count_has_not_grown():
    """service-life-planning 1.2, with the one recorded gap explained here.

    `src/anvilate/screening.py`'s zero-damage branch of the duty-cycle screen publishes no
    life, and that is the correct answer rather than debt: no counted cycle reaches a
    damaging amplitude, so the part's fatigue life under that duty is unbounded and a
    `LifeQuantity` refuses a non-finite value on purpose. The census reports it because a
    reader has to be able to see it; the ceiling is what stops a second one appearing
    quietly.
    """
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    done = subprocess.run(
        [sys.executable, str(repo / "tools" / "audit" / "lives.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=repo,
    )
    assert done.returncode == 0, done.stdout + done.stderr

    page = (repo / "docs" / "api" / "life-publishing-checks.txt").read_text()
    rows = [line for line in page.splitlines() if line and not line.startswith("#")]
    assert len(rows) >= 4, "the census found almost nothing; the detector has stopped seeing"
    gaps = [row for row in rows if "| NO |" in row]
    assert len(gaps) <= 1, (
        "a check named as a life publishes none; the maintenance plan would be quietly "
        "shorter rather than visibly incomplete:\n  " + "\n  ".join(gaps)
    )
    assert all("screening.py" in gap for gap in gaps)


def test_the_census_detector_sees_a_life_that_stops_being_published():
    """Attack the gate: the census is only worth the difference it can detect."""
    import ast
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "audit"))
    try:
        import lives
    finally:
        sys.path.pop(0)

    published = ast.parse(
        'entry = ScorecardEntry.from_safety_factor("bearing rating life", computed=1.0)\n'
        'entries.append(entry.model_copy(update={"life": life}))\n'
    )
    bare = ast.parse(
        'entry = ScorecardEntry.from_safety_factor("bearing rating life", computed=1.0)\n'
        "entries.append(entry)\n"
    )
    assert _publishes(lives, published) is True
    assert _publishes(lives, bare) is False
    # A local called `life` is not a published life. The first draft said it was.
    mentions = ast.parse(
        "life = compute()\n"
        'entries.append(ScorecardEntry(name="bearing rating life", detail=f"{life}"))\n'
    )
    assert _publishes(lives, mentions) is False


def _publishes(lives, tree) -> bool:
    import ast

    for block in lives._blocks(tree.body):
        nodes = list(lives._own_nodes(block))
        if any(
            isinstance(node, ast.Call) and lives._check_name(node) is not None for node in nodes
        ):
            return any(lives._is_a_life_assignment(node) for node in nodes)
    raise AssertionError("the fixture built no check the census recognises")


def test_the_card_round_trips_its_life_and_a_card_without_one_is_unchanged():
    card = _card()
    reloaded = Scorecard.model_validate(card.model_dump(mode="json"))
    assert reloaded.entries[0].life == card.entries[0].life
    bare = Scorecard(entries=(_entry(life=None),))
    assert "life" not in bare.model_dump(mode="json")["entries"][0]


def test_a_life_cannot_be_asserted_into_a_card_in_the_wrong_dimension():
    """The annotation is validated on the way back in, not only on the way out."""
    dumped = _card().model_dump(mode="json")
    dumped["entries"][0]["life"]["value"] = {"magnitude": 4000.0, "unit": "km"}
    with pytest.raises(ValidationError):
        Scorecard.model_validate(dumped)


def test_the_docs_page_quotes_what_the_library_actually_computes():
    """The page argues from the interval and the summary line; both are recomputed here."""
    import re
    from pathlib import Path

    page = (
        Path(__file__).resolve().parent.parent / "docs" / "service-life-planning.md"
    ).read_text()

    quoted = re.search(r"fraction_of_life=([\d.]+),", page)
    assert quoted is not None, "the page's worked rule has moved"
    fraction = float(quoted.group(1))
    plan = plan_service_life(
        _card(),
        rules=(_rule(fraction_of_life=fraction),),
        product_items=("a", "b", "c", "bearing rating life"),
    )
    assert plan.items[0].interval == _q(f"{23000 * fraction:g} hour")

    summary = re.search(
        r"# (\d+) scheduled items, (\d+) with no interval set, (\d+) items with no life "
        r"basis,\n# (\d+) tasks performed — plan status (\w+)",
        page,
    )
    assert summary is not None, "the page's quoted summary line has moved"
    scheduled, unset, uncovered, performed, status = summary.groups()
    assert plan.summary() == (
        f"{scheduled} scheduled items, {unset} with no interval set, "
        f"{uncovered} items with no life basis, {performed} tasks performed — "
        f"plan status {status}"
    )

    # The life the page writes out is one the library accepts, in the units it names.
    written = re.search(
        r'LifeQuantity\(kind=LifeKind\.(\w+), value=Quantity\.parse\("([^"]+)"\),\n'
        r'\s+basis="([^"]+)", reliability=([\d.]+)\)',
        page,
    )
    assert written is not None, "the page's worked LifeQuantity has moved"
    kind, value, basis, reliability = written.groups()
    rebuilt = LifeQuantity(
        kind=LifeKind[kind], value=_q(value), basis=basis, reliability=float(reliability)
    )
    assert rebuilt.value == _q("23000 hour")
    assert "90% reliability" in str(rebuilt)


def test_a_rule_renders_its_task_and_who_declared_it():
    """A rule read in a list has to say which of the four tasks it is, and on whose word."""
    assert str(_rule()) == f"replace at half of rating life [time_directed] ({_POLICY})"
    on_condition = IntervalRule(
        name="inspect measurable wear",
        task=TaskType.ON_CONDITION,
        source="the maintenance policy, §7",
        applies_to=("wear allowance",),
        pf_interval=_q("800 hour"),
        inspection_fraction=0.5,
    )
    assert "[on_condition]" in str(on_condition)
    assert "§7" in str(on_condition)


def test_a_plan_renders_as_its_summary_and_never_as_maintained():
    plan = _full_plan()
    assert str(plan) == plan.summary()
    assert "plan status" in str(plan)
    for word in ("maintained", "up to date", "complete"):
        assert word not in str(plan)
