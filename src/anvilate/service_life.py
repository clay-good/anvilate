"""Service-life planning: the maintenance each life-limited check implies.

A design that passes is not a design that lasts without attention. The bearing check
reports a rating life of 23,000 hours. The duty-cycle check reports damage per year. The
wear screen reports an allowance consumed at a rate. Each of those numbers is a date, and
until now each sat on its own card entry while somebody retyped it into a schedule by
hand — or nobody did, and the product shipped with no plan.

:mod:`anvilate.verification` already inverts a check into the physical test it implies,
and is careful that a plan is not evidence. The same inversion applies *after* the product
is in service. This module is that one, and it keeps the same three rules:

1. **Nothing here invents an interval.** An interval comes from a life the check computed
   and an :class:`IntervalRule` the document declared, with the rule's source. A life with
   no applicable rule is an item reading "interval not set" — never a quietly shorter
   schedule, and never a default fraction this library picked.
2. **A plan is not a maintenance record.** An item carries no result until a
   :class:`PerformedTask` is recorded against it, and the plan reports ``NOT_EVALUATED``
   until every item has one.
3. **Coverage is reported, including the items nothing gave a life.** A plan with three
   items on a product of thirty is visibly incomplete, because the twenty-seven are named.

The task vocabulary is NASA's *Reliability-Centered Maintenance Guide for Facilities and
Collateral Equipment* (2008): time-directed, on-condition, failure-finding, and accepted
run-to-failure, with the P-F interval practice that an on-condition inspection must run
more often than the time between a detectable potential failure and the functional one.
Nothing of a commercial RCM standard is reproduced; the task names are the guide's.

Out of scope, by the change that added this: any default interval, life factor or
reliability target; work-order, CMMS or ERP integration (files only); reliability
prediction from handbooks or fleet statistics; and lubrication selection.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from math import ceil, isfinite

from pydantic import ConfigDict, Field, computed_field, model_validator

from ._models import Named, Provenance, StatableModel, each_one
from .credibility import AcceptanceBand, Correlation, PredictionSense
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, LifeKind, LifeQuantity, Scorecard
from .units import Quantity

__all__ = [
    "RCM_CITATION",
    "LifeKind",
    "LifeQuantity",
    "TaskType",
    "IntervalRule",
    "MaintenanceItem",
    "PerformedTask",
    "SpareLine",
    "ServiceLifePlan",
    "plan_service_life",
    "task_correlations",
]

#: Where the four task types and the P-F interval practice come from. A NASA publication,
#: used for its vocabulary; the intervals themselves are always the user's, with a source.
RCM_CITATION = (
    "NASA Reliability-Centered Maintenance Guide for Facilities and Collateral "
    "Equipment (2008), task types and the P-F interval"
)

_RULE_SOURCE = "the organization's maintenance policy, with the document that states it"


def _refuse(message: str, *, subject: str, source: str) -> RefusalError:
    return RefusalError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class TaskType(StrEnum):
    """The four maintenance tasks the NASA RCM guide names."""

    TIME_DIRECTED = "time_directed"
    ON_CONDITION = "on_condition"
    FAILURE_FINDING = "failure_finding"
    RUN_TO_FAILURE = "run_to_failure"


class IntervalRule(StatableModel):
    """How the organization turns a computed life into an interval, and who says so.

    A rule is declared, never defaulted. ``fraction_of_life`` is the share of the computed
    life at which a time-directed or failure-finding task runs. An on-condition task
    instead runs at ``inspection_fraction`` of the declared ``pf_interval`` — the time
    between a detectable potential failure and the functional one — because inspecting
    less often than that is inspecting after the fact.

    ``applies_to`` names the checks this rule covers. A rule that names nothing covers
    nothing: a rule silently applying to every check is the default this module refuses.
    """

    model_config = ConfigDict(frozen=True)

    name: Named
    task: TaskType
    source: Provenance
    applies_to: tuple[Named, ...]
    fraction_of_life: float | None = Field(default=None, exclude_if=lambda value: value is None)
    pf_interval: Quantity | None = Field(default=None, exclude_if=lambda value: value is None)
    inspection_fraction: float | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def _well_formed(self) -> IntervalRule:
        if not self.applies_to:
            raise _refuse(
                f"rule '{self.name}' names no check it applies to; a rule that covers "
                f"everything by saying nothing is the default this module exists to refuse",
                subject="applies_to",
                source=_RULE_SOURCE,
            )
        if len(set(self.applies_to)) != len(self.applies_to):
            raise _refuse(
                f"rule '{self.name}' names a check twice in {list(self.applies_to)}",
                subject="applies_to",
                source=_RULE_SOURCE,
            )
        for fraction, name in (
            (self.fraction_of_life, "fraction_of_life"),
            (self.inspection_fraction, "inspection_fraction"),
        ):
            if fraction is not None and not 0.0 < fraction <= 1.0:
                raise _refuse(
                    f"{name} is a share of a life or an interval, greater than zero and at "
                    f"most one; got {fraction}. A share above one schedules the task after "
                    f"the thing it was meant to prevent",
                    subject=name,
                    source=_RULE_SOURCE,
                )
        if self.pf_interval is not None:
            if str(self.pf_interval.pint.dimensionality) != "[time]":
                raise _refuse(
                    f"a P-F interval is a time; got {self.pf_interval.dimensionality}",
                    subject="pf_interval",
                    source=_RULE_SOURCE,
                )
            if not isfinite(self.pf_interval.magnitude) or self.pf_interval.magnitude <= 0.0:
                raise _refuse(
                    f"a P-F interval is a positive finite time; got {self.pf_interval}",
                    subject="pf_interval",
                    source=_RULE_SOURCE,
                )
        if self.task is TaskType.RUN_TO_FAILURE and (
            self.fraction_of_life is not None
            or self.pf_interval is not None
            or self.inspection_fraction is not None
        ):
            raise _refuse(
                f"rule '{self.name}' accepts run-to-failure and also states an interval; "
                f"accepting a failure is the decision not to schedule anything, and a "
                f"schedule carrying both says the opposite of itself",
                subject="task",
                source=_RULE_SOURCE,
            )
        if self.task is TaskType.ON_CONDITION and self.fraction_of_life is not None:
            raise _refuse(
                f"rule '{self.name}' is on-condition and states a fraction of life; an "
                f"on-condition task runs at a fraction of the P-F interval, which is the "
                f"warning the inspection has to fit inside, not of the life itself",
                subject="fraction_of_life",
                source=_RULE_SOURCE,
            )
        if self.task in {TaskType.TIME_DIRECTED, TaskType.FAILURE_FINDING} and (
            self.pf_interval is not None or self.inspection_fraction is not None
        ):
            raise _refuse(
                f"rule '{self.name}' is {self.task.value} and states a P-F interval; the "
                f"P-F interval belongs to an on-condition inspection",
                subject="pf_interval",
                source=_RULE_SOURCE,
            )
        return self

    def covers(self, check: str) -> bool:
        """Whether this rule names that check."""
        return check in self.applies_to

    def interval_for(self, life: LifeQuantity) -> tuple[Quantity | None, str]:
        """The interval this rule produces from a life, and why it is or is not set."""
        if self.task is TaskType.RUN_TO_FAILURE:
            return None, "run to failure is accepted; no task is scheduled"
        if self.task is TaskType.ON_CONDITION:
            if self.pf_interval is None or self.inspection_fraction is None:
                missing = "a P-F interval" if self.pf_interval is None else "an inspection"
                missing += "" if self.pf_interval is None else " fraction of it"
                return None, f"interval not set: the on-condition rule needs {missing}"
            return (
                Quantity(
                    magnitude=self.pf_interval.magnitude * self.inspection_fraction,
                    unit=self.pf_interval.unit,
                ),
                f"{self.inspection_fraction:g} of the declared {self.pf_interval} P-F interval",
            )
        if self.fraction_of_life is None:
            return None, "interval not set: the rule states no fraction of life"
        return (
            Quantity(magnitude=life.value.magnitude * self.fraction_of_life, unit=life.value.unit),
            f"{self.fraction_of_life:g} of the computed {life.value}",
        )

    def __str__(self) -> str:
        return f"{self.name} [{self.task.value}] ({self.source})"


class PerformedTask(StatableModel):
    """A maintenance task somebody did: when, who, and what they measured.

    ``measured_condition`` is the number an inspection read — 0.3 mm of wear at 420 hours
    — and it is what makes a performed task a referent for
    :mod:`anvilate.credibility`. A task with no number is still a record; it is simply not
    a correlation point, and nothing here pretends otherwise.
    """

    model_config = ConfigDict(frozen=True)

    item_path: Named
    performed_on: date
    performed_by: str
    note: str = ""
    measured_condition: Quantity | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _traceable(self) -> PerformedTask:
        if not self.performed_by.strip():
            raise _refuse(
                "a performed task needs who performed it; an anonymous maintenance record "
                "is closer to a claim than to a record",
                subject="performed_by",
                source="the maintenance record the task was taken from",
            )
        return self

    def __str__(self) -> str:
        measured = (
            f", measured {self.measured_condition}" if self.measured_condition is not None else ""
        )
        return (
            f"{self.item_path} performed {self.performed_on.isoformat()} by "
            f"{self.performed_by}{measured}"
        )


class MaintenanceItem(StatableModel):
    """One scheduled task: what, on which item, from which check and which rule.

    ``interval`` is ``None`` when no declared rule produced one, and ``interval_basis``
    then says what is missing. That pair is the whole honesty of this module: a schedule
    where an item is present with no interval is visibly incomplete, and one where the
    item was dropped is not.
    """

    model_config = ConfigDict(frozen=True)

    item_path: Named
    check: Named
    life: LifeQuantity
    task: TaskType
    interval: Quantity | None = Field(default=None, exclude_if=lambda value: value is None)
    interval_basis: str = ""
    rule: IntervalRule | None = Field(default=None, exclude_if=lambda value: value is None)
    spare: str | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def _says_why_when_unset(self) -> MaintenanceItem:
        if not self.interval_basis.strip():
            raise _refuse(
                f"the item for '{self.check}' states no basis for its interval; a number "
                f"with no basis is one a reader cannot argue with, and a missing interval "
                f"with no reason is one nobody can act on",
                subject="interval_basis",
                source="the rule that produced the interval, or the rule that is missing",
            )
        return self

    @property
    def interval_set(self) -> bool:
        """Whether a declared rule produced an interval for this item."""
        return self.interval is not None

    def __str__(self) -> str:
        when = f"every {self.interval}" if self.interval is not None else "interval not set"
        rule = f" per {self.rule.name}" if self.rule is not None else ""
        return (
            f"{self.item_path}: {self.task.value.replace('_', ' ')} {when}{rule} — "
            f"{self.check} gives {self.life}; {self.interval_basis}"
        )


class SpareLine(StatableModel):
    """One spare the plan implies over the declared service life, with its arithmetic."""

    model_config = ConfigDict(frozen=True)

    designation: Named
    quantity: int
    used_at: Named
    arithmetic: str

    def __str__(self) -> str:
        return f"{self.designation} x{self.quantity} at {self.used_at} ({self.arithmetic})"


class ServiceLifePlan(StatableModel):
    """A product's maintenance schedule, its spares, and what it does not cover.

    ``without_a_life_basis`` names every item of the product no life-limited check reached.
    It is the same rule :mod:`anvilate.verification` keeps one layer out: a plan that
    listed only what it covers reads identically whether it covers three items of thirty
    or thirty of thirty.
    """

    model_config = ConfigDict(frozen=True)

    items: tuple[MaintenanceItem, ...]
    without_a_life_basis: tuple[Named, ...] = ()
    service_life: Quantity | None = Field(default=None, exclude_if=lambda value: value is None)
    duty_per_year: Quantity | None = Field(default=None, exclude_if=lambda value: value is None)
    tasks: tuple[PerformedTask, ...] = ()
    citation: Provenance = RCM_CITATION

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        """``NOT_EVALUATED`` until every scheduled item has a recorded task.

        A plan is not a maintenance record. This never reports that a product has been
        maintained because somebody wrote a schedule for it — only on a full set of
        recorded tasks, and only over the items that have an interval at all.
        """
        scheduled = tuple(item for item in self.items if item.interval_set)
        if not scheduled:
            return CheckStatus.NOT_EVALUATED
        performed = {task.item_path for task in self.tasks}
        if all(item.item_path in performed for item in scheduled):
            return CheckStatus.PASS
        return CheckStatus.NOT_EVALUATED

    @property
    def unset(self) -> tuple[MaintenanceItem, ...]:
        """The items a life reached and no declared rule gave an interval."""
        return tuple(item for item in self.items if not item.interval_set)

    def scheduled(self) -> tuple[MaintenanceItem, ...]:
        """The items with an interval, soonest first; ties keep the plan's own order."""
        with_interval = [item for item in self.items if item.interval is not None]
        return tuple(
            sorted(
                with_interval,
                key=lambda item: _hours_or_inf(item.interval),
            )
        )

    def spares(self) -> tuple[SpareLine, ...]:
        """The replaceable items the plan implies over the declared service life.

        Empty without a declared service life: the count is service life divided by
        interval, and neither half of that is this library's to assume. A fractional count
        rounds **up**, because two-and-a-bit replacements over ten years is three spares.
        """
        if self.service_life is None:
            return ()
        lines: list[SpareLine] = []
        for item in self.items:
            if item.spare is None or item.interval is None:
                continue
            horizon = self._life_in(item.interval)
            if horizon is None:
                continue
            per_interval = item.interval.magnitude
            if per_interval <= 0:
                continue
            count = ceil(horizon / per_interval)
            if count <= 0:
                continue
            lines.append(
                SpareLine(
                    designation=item.spare,
                    quantity=count,
                    used_at=item.item_path,
                    arithmetic=(
                        f"{horizon:.6g} {item.interval.unit} of service / "
                        f"{per_interval:.6g} {item.interval.unit} interval, rounded up"
                    ),
                )
            )
        return tuple(lines)

    def _life_in(self, interval: Quantity) -> float | None:
        """The declared service life in the interval's own unit, or ``None`` if it cannot be.

        A service life is a calendar time and an interval may be running hours, so the
        declared duty per year is what connects them. Without it, a calendar life cannot
        be turned into running hours and no spare count is invented.
        """
        if self.service_life is None:
            return None
        if self.service_life.pint.dimensionality == interval.pint.dimensionality:
            if self.duty_per_year is None:
                return self.service_life.to(interval.unit).magnitude
            # Both are times and a duty is declared: the life is calendar time, so the
            # running time is the duty applied to it rather than the calendar span.
            years = self.service_life.to("year").magnitude
            return (
                Quantity(
                    magnitude=years * self.duty_per_year.magnitude, unit=self.duty_per_year.unit
                )
                .to(interval.unit)
                .magnitude
            )
        if self.duty_per_year is None:
            return None
        years = self.service_life.to("year").magnitude
        running = Quantity(
            magnitude=years * self.duty_per_year.magnitude, unit=self.duty_per_year.unit
        )
        if running.pint.dimensionality != interval.pint.dimensionality:
            return None
        return running.to(interval.unit).magnitude

    def summary(self) -> str:
        """One line for a report pane. Never says the product has been maintained."""
        scheduled = len(self.items) - len(self.unset)
        return (
            f"{scheduled} scheduled items, {len(self.unset)} with no interval set, "
            f"{len(self.without_a_life_basis)} items with no life basis, "
            f"{len(self.tasks)} tasks performed — plan status {self.status.value}"
        )

    def schedule(self) -> str:
        """The schedule as text: scheduled items soonest first, then everything it misses."""
        lines = ["item                           task            interval"]
        for item in self.scheduled():
            lines.append(f"{item.item_path:<30} {item.task.value:<15} {item.interval}")
        for item in self.unset:
            # The life, and then why there is no interval. The spec's own words are "the
            # plan lists the seal with its life and 'interval not set'": a row saying only
            # that nothing is scheduled tells a reader nothing about what wears out.
            lines.append(
                f"{item.item_path:<30} {item.task.value:<15} "
                f"{item.life.value} — {item.interval_basis}"
            )
        for name in self.without_a_life_basis:
            lines.append(f"{name:<30} {'—':<15} no life-limited check covers this item")
        return "\n".join(lines)

    def to_csv(self) -> str:
        """The schedule as CSV: a header row, then every item in schedule order."""
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(_SCHEDULE_COLUMNS)
        for item in (*self.scheduled(), *self.unset):
            writer.writerow(
                [
                    _csv_safe(column, cell)
                    for column, cell in zip(_SCHEDULE_COLUMNS, _cells(item), strict=True)
                ]
            )
        return out.getvalue()

    def to_xlsx(self) -> bytes:
        """The schedule and the spares as an XLSX workbook, written with the stdlib."""
        from .margin_of_safety import _workbook

        schedule = [list(_SCHEDULE_COLUMNS)]
        schedule.extend(list(_cells(item)) for item in (*self.scheduled(), *self.unset))
        spares = [["designation", "quantity", "used at", "arithmetic"]]
        spares.extend(
            [line.designation, str(line.quantity), line.used_at, line.arithmetic]
            for line in self.spares()
        )
        uncovered = [["item with no life basis"], *([name] for name in self.without_a_life_basis)]
        return _workbook(
            (
                ("Schedule", schedule, {4}),
                ("Spares", spares, {1}),
                ("Uncovered", uncovered, set()),
            )
        )

    def section(self) -> str:
        """The plan as a Markdown report section, scheduled first and the gaps named."""
        lines = [
            "## Service-life plan",
            "",
            f"{self.summary()} Task types: {self.citation}. Every interval comes from a "
            "life a check computed and a rule this document declared; nothing here is a "
            "default.",
            "",
            "| Item | Task | Interval | Driving check | Life | Rule |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for item in (*self.scheduled(), *self.unset):
            cells = _cells(item)
            lines.append("| " + " | ".join(_md(cell) for cell in cells[:6]) + " |")
        if self.without_a_life_basis:
            lines.extend(
                [
                    "",
                    f"### {len(self.without_a_life_basis)} items with no life basis",
                    "",
                    ", ".join(_md(name) for name in self.without_a_life_basis),
                ]
            )
        spares = self.spares()
        if spares:
            lines.extend(
                [
                    "",
                    "### Spares over the declared service life",
                    "",
                    "| Designation | Quantity | Used at | Arithmetic |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for line in spares:
                lines.append(
                    f"| {_md(line.designation)} | {line.quantity} | {_md(line.used_at)} | "
                    f"{_md(line.arithmetic)} |"
                )
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.summary()


_SCHEDULE_COLUMNS = (
    "item",
    "task",
    "interval",
    "driving check",
    "life",
    "rule",
    "rule source",
    "interval basis",
    "spare",
)
#: Columns a spreadsheet should read as text even when they start like a formula.
_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(column: str, cell: str) -> str:
    if column == "interval" or not cell.startswith(_FORMULA_LEADS):
        return cell
    return "'" + cell


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _cells(item: MaintenanceItem) -> tuple[str, ...]:
    return (
        item.item_path,
        item.task.value.replace("_", " "),
        str(item.interval) if item.interval is not None else "not set",
        item.check,
        str(item.life.value),
        item.rule.name if item.rule is not None else "",
        item.rule.source if item.rule is not None else "",
        item.interval_basis,
        item.spare or "",
    )


def _hours_or_inf(interval: Quantity | None) -> float:
    if interval is None:
        return float("inf")
    try:
        return interval.to("hour").magnitude
    except Exception:  # a cycle or a distance interval sorts after every time
        return float("inf")


def plan_service_life(
    scorecard: Scorecard,
    *,
    rules: Sequence[IntervalRule] = (),
    item_paths: Mapping[str, str] | None = None,
    spares: Mapping[str, str] | None = None,
    product_items: Sequence[str] = (),
    service_life: Quantity | None = None,
    duty_per_year: Quantity | None = None,
    tasks: Sequence[PerformedTask] = (),
) -> ServiceLifePlan:
    """Derive the maintenance plan a scorecard's life-limited checks imply.

    Every entry carrying a :class:`LifeQuantity` becomes one :class:`MaintenanceItem`. The
    first declared rule naming that check sets the task type and the interval; a check no
    rule names becomes an item reading "interval not set", because a schedule shorter than
    the set of things that wear out is not a schedule.

    ``item_paths`` maps a check name to the product item it is about; a check with no
    mapping is its own path, which is what a single-part plan wants. ``product_items``
    is every item of the product, so the ones no life-limited check covers can be named.
    ``spares`` maps a check to the part number its replacement consumes.
    """
    rules = each_one(rules, IntervalRule, named="rules")
    tasks = each_one(tasks, PerformedTask, named="tasks")
    item_paths = dict(item_paths or {})
    spares = dict(spares or {})

    items: list[MaintenanceItem] = []
    covered: set[str] = set()
    for entry in scorecard.entries:
        if entry.life is None:
            continue
        path = item_paths.get(entry.name, entry.name)
        covered.add(path)
        rule = next((candidate for candidate in rules if candidate.covers(entry.name)), None)
        if rule is None:
            items.append(
                MaintenanceItem(
                    item_path=path,
                    check=entry.name,
                    life=entry.life,
                    task=TaskType.TIME_DIRECTED,
                    interval_basis=(
                        "interval not set: no declared rule names this check, and no "
                        "interval is assumed for one"
                    ),
                    spare=spares.get(entry.name),
                )
            )
            continue
        interval, basis = rule.interval_for(entry.life)
        items.append(
            MaintenanceItem(
                item_path=path,
                check=entry.name,
                life=entry.life,
                task=rule.task,
                interval=interval,
                interval_basis=basis,
                rule=rule,
                spare=spares.get(entry.name),
            )
        )
    uncovered = tuple(name for name in dict.fromkeys(product_items) if name not in covered)
    return ServiceLifePlan(
        items=tuple(items),
        without_a_life_basis=uncovered,
        service_life=service_life,
        duty_per_year=duty_per_year,
        tasks=tasks,
    )


def task_correlations(
    plan: ServiceLifePlan,
    scorecard: Scorecard,
    *,
    bands: Mapping[str, AcceptanceBand] | None = None,
    senses: Mapping[str, PredictionSense] | None = None,
) -> tuple[Correlation, ...]:
    """Every performed task that measured a condition, as a model-credibility correlation.

    An inspection that read 0.3 mm of wear is a measurement of the quantity the wear check
    predicted, and the same comparison the proof-test loop makes applies: the ratio, the
    difference, and the declared band. A task with no measured condition produces nothing,
    and no verdict moves either way.

    The predicted value is the driving check's own comparison — the number the check
    computed — so a check that compares nothing cannot be correlated by number and is
    skipped rather than correlated against a parsed detail line.
    """
    bands = dict(bands or {})
    senses = dict(senses or {})
    by_name = {entry.name: entry for entry in scorecard.entries}
    by_path: dict[str, MaintenanceItem] = {item.item_path: item for item in plan.items}
    found: list[Correlation] = []
    for task in plan.tasks:
        if task.measured_condition is None:
            continue
        item = by_path.get(task.item_path)
        if item is None:
            continue
        entry = by_name.get(item.check)
        if entry is None or entry.comparison is None:
            continue
        predicted = entry.comparison.measured
        if predicted.pint.dimensionality != task.measured_condition.pint.dimensionality:
            continue
        found.append(
            Correlation(
                check=item.check,
                item=task.item_path,
                predicted=predicted,
                measured=task.measured_condition,
                # A condition read off a part in service is a *response* — wear depth,
                # corrosion loss, set — so measuring more than predicted is the
                # unconservative direction. A capacity measured in service is rare and
                # the caller says so.
                sense=senses.get(item.check, PredictionSense.RESPONSE),
                performed_on=task.performed_on,
                performed_by=task.performed_by,
                instrument=task.note or "the maintenance record",
                band=bands.get(item.check),
                check_passed=entry.status is CheckStatus.PASS,
            )
        )
    return tuple(found)
