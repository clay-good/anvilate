"""Performance budgets: an allocated limit, itemized contributors, and a declared rule.

Every check on a card can pass while the part still fails: five alignment errors each inside
their own tolerance, summed, miss the line-of-sight requirement. No per-check screen can see
that, because the requirement belongs to the combination. A :class:`Budget` is that
requirement stated as data.

A budget names its quantity, its allocated limit and where the limit came from, its
contributors, and its :class:`CombinationRule` — which has **no default**, because
worst-case, root-sum-square and the hybrid rule give different answers and choosing one for
the author is choosing the verdict. :meth:`Budget.evaluate` returns a :class:`BudgetResult`:
the total and margin, each contributor's share, the governing contributor found by
re-evaluating the rule without each one (ties kept), and each contributor's headroom — the
value it could grow to, the others held, before the limit is spent.

What is refused at construction, because each is a number computed from a mistake:

- a contributor whose dimension differs from the limit's, named with both dimensions;
- root-sum-square over contributors sharing a correlation group, which understates them;
- two contributors bound to the same check, which counts one quantity twice;
- a negative value not declared compensating, and a compensating term under a quadrature
  rule, where its sign is squared away;
- an offset temperature unit, whose sums are not sums of the quantity.

What is NOT_EVALUATED rather than computed: a budget with no declared rule, and a budget with
any contributor that did not resolve. A missing term is never zero.

Screening only. Angles are dimensionless to the unit layer, so a milliradian budget cannot
tell an angle from a strain; the contributor's name and source are what distinguish them.
"""

from __future__ import annotations

from enum import StrEnum
from math import isclose, sqrt
from typing import Self

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, Provenance, StatableModel
from .derivation import DerivationAbsence, Underived
from .scorecard import CheckStatus, Comparison, LimitSense, Scorecard, ScorecardEntry
from .units import Quantity, spoken

__all__ = [
    "CombinationRule",
    "ContributorBasis",
    "LimitBasis",
    "Contributor",
    "Budget",
    "ContributorResult",
    "BudgetResult",
]


class CombinationRule(StrEnum):
    """How contributors combine. Declared by the author; there is no default."""

    WORST_CASE = "worst_case"
    RSS = "rss"
    HYBRID = "hybrid"


class ContributorBasis(StrEnum):
    """How a contributor's value is known — an estimate grows, a measurement does not."""

    MEASURED = "measured"
    CALCULATED = "calculated"
    ESTIMATED = "estimated"


class LimitBasis(StrEnum):
    """Where an allocated limit came from."""

    REQUIREMENT = "requirement"
    DERIVED = "derived_allocation"
    ASSUMPTION = "working_assumption"


class Contributor(StatableModel):
    """One term in a budget.

    ``value`` is ``None`` when the term's source produced nothing — its check did not run, its
    measurement was not supplied — and ``unresolved`` then says why. ``check`` is the id of
    the scorecard check the value came from, when it came from one; it is the identity double
    counting is detected on. ``compensating`` declares a deliberate term of opposite sign.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    value: Quantity | None
    source: Provenance
    basis: ContributorBasis
    check: Named | None = None
    correlation_group: Named | None = None
    compensating: bool = False
    unresolved: Provenance | None = None

    @model_validator(mode="after")
    def _a_term(self) -> Self:
        if (self.value is None) == (self.unresolved is None):
            raise ValueError(
                f"contributor '{self.name}' states a value or the reason it has none, exactly "
                "one: a missing value with no reason reads as an oversight, and a reason beside "
                "a value contradicts it"
            )
        if self.value is None:
            return self
        if not self.value.pint._is_multiplicative:
            raise ValueError(
                f"contributor '{self.name}' is in {self.value.unit}, an offset temperature "
                "scale; a budget adds its terms, so state a temperature difference "
                "(delta_degC, K) instead"
            )
        if self.value.magnitude < 0 and not self.compensating:
            raise ValueError(
                f"contributor '{self.name}' is negative ({self.value}) and not declared "
                "compensating; a term that reduces the total is declared as one, so the budget "
                "can report the total with and without it"
            )
        if self.compensating and self.value.magnitude > 0:
            raise ValueError(
                f"contributor '{self.name}' is declared compensating with a positive value "
                f"({self.value}); a compensating term reduces the total and is negative"
            )
        return self


class Budget(StatableModel):
    """An allocated limit on one quantity, and the terms that spend it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    quantity: Named
    limit: Quantity
    limit_basis: LimitBasis
    limit_source: Provenance
    rule: CombinationRule | None
    contributors: tuple[Contributor, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not self.limit.pint._is_multiplicative:
            raise ValueError(
                f"budget '{self.name}' is allocated in {self.limit.unit}, an offset "
                "temperature scale; allocate a temperature difference (delta_degC, K) instead"
            )
        if self.limit.magnitude <= 0:
            raise ValueError(f"budget '{self.name}' allocates {self.limit}; a limit is positive")
        expected = self.limit.pint.dimensionality
        for term in self.contributors:
            if term.value is not None and term.value.pint.dimensionality != expected:
                raise ValueError(
                    f"budget '{self.name}' is allocated in {self.limit.dimensionality} and "
                    f"contributor '{term.name}' is {term.value.dimensionality}; a total "
                    "across two dimensions is not a quantity"
                )
        bound: dict[str, str] = {}
        for term in self.contributors:
            if term.check is None:
                continue
            if term.check in bound:
                raise ValueError(
                    f"budget '{self.name}' binds contributors '{bound[term.check]}' and "
                    f"'{term.name}' to the same check '{term.check}'; one quantity counted "
                    "twice under two names"
                )
            bound[term.check] = term.name
        names = [term.name for term in self.contributors]
        if len(set(names)) != len(names):
            raise ValueError(f"budget '{self.name}' names a contributor twice: {names}")
        if self.rule in (CombinationRule.RSS, CombinationRule.HYBRID):
            compensating = [t.name for t in self.contributors if t.compensating]
            if compensating:
                raise ValueError(
                    f"budget '{self.name}' combines in quadrature and declares compensating "
                    f"{compensating}; squaring a term discards its sign, so compensation only "
                    "nets under worst_case"
                )
        if self.rule is CombinationRule.RSS:
            for group, members in _groups(self.contributors).items():
                if len(members) > 1:
                    raise ValueError(
                        f"budget '{self.name}' combines by rss and contributors "
                        f"{[m.name for m in members]} share correlation group '{group}'; "
                        "quadrature understates correlated terms — declare the hybrid rule, "
                        "which sums each group before combining"
                    )
        return self

    def bind(self, card: Scorecard) -> Budget:
        """This budget with every check-bound contributor's value read from ``card``.

        A contributor naming a ``check`` takes that entry's measured quantity, so the total
        follows the screens that produced it and cannot carry a superseded value. A check that
        is not on the card, is on it twice, did not run, or measured nothing leaves the
        contributor unresolved with that reason — and the budget not evaluated — rather than
        keeping whatever value it was declared with. Contributors with no ``check`` are kept.
        """
        bound = []
        for term in self.contributors:
            if term.check is None:
                bound.append(term)
                continue
            value, unresolved = _read_check(card, term.check)
            if value is not None:
                magnitude = abs(value.magnitude)
                value = Quantity(
                    magnitude=-magnitude if term.compensating else magnitude, unit=value.unit
                )
            bound.append(
                Contributor.model_validate({**dict(term), "value": value, "unresolved": unresolved})
            )
        return Budget.model_validate({**dict(self), "contributors": tuple(bound)})

    def evaluate(self) -> BudgetResult:
        """The total, the margin, and what each contributor is responsible for."""
        unit = self.limit.unit
        limit = self.limit.magnitude
        if self.rule is None:
            return BudgetResult(
                budget=self,
                status=CheckStatus.NOT_EVALUATED,
                reason=(
                    "no combination rule is declared; worst case, root-sum-square and hybrid "
                    "give different totals, and none is assumed"
                ),
            )
        waiting = [term for term in self.contributors if term.value is None]
        if waiting:
            return BudgetResult(
                budget=self,
                status=CheckStatus.NOT_EVALUATED,
                reason="; ".join(
                    f"contributor '{term.name}' has no value: {term.unresolved}" for term in waiting
                ),
            )
        values = {t.name: t.value.to(unit).magnitude for t in self.contributors if t.value}
        rule = self.rule
        total = _combine(rule, self.contributors, values)
        uncompensated = _combine(
            rule, self.contributors, {n: (v if v > 0 else 0.0) for n, v in values.items()}
        )

        recoveries = {
            term.name: total - _combine(rule, self.contributors, {**values, term.name: 0.0})
            for term in self.contributors
        }
        best = max(recoveries.values())
        governing = (
            tuple(n for n, r in recoveries.items() if isclose(r, best, rel_tol=1e-9))
            if best > 0
            else ()
        )

        terms = []
        for term in self.contributors:
            headroom, why = _headroom(rule, self.contributors, values, term, total, limit)
            terms.append(
                ContributorResult(
                    name=term.name,
                    value=values[term.name],
                    share=_share(rule, self.contributors, values, term, total),
                    headroom=headroom,
                    headroom_unavailable=why,
                )
            )
        group_sums = tuple(
            (group, sum(values[m.name] for m in members))
            for group, members in _groups(self.contributors).items()
        )
        return BudgetResult(
            budget=self,
            status=CheckStatus.PASS if abs(total) <= limit else CheckStatus.FAIL,
            total=total,
            total_without_compensation=uncompensated,
            margin=limit - abs(total),
            group_sums=group_sums if rule is CombinationRule.HYBRID else (),
            contributors=tuple(terms),
            governing=governing,
        )


def _read_check(card: Scorecard, check: str) -> tuple[Quantity | None, str | None]:
    matches = [entry for entry in card.entries if entry.name == check]
    if not matches:
        return None, f"check '{check}' is not on the scorecard"
    if len(matches) > 1:
        return None, f"the scorecard carries {len(matches)} checks named '{check}'"
    (entry,) = matches
    if entry.status is CheckStatus.NOT_EVALUATED:
        return None, f"check '{check}' was not evaluated: {entry.detail}"
    if entry.comparison is None:
        return None, f"check '{check}' carries no measured quantity to bind"
    return entry.comparison.measured, None


def _groups(contributors: tuple[Contributor, ...]) -> dict[str, list[Contributor]]:
    groups: dict[str, list[Contributor]] = {}
    for term in contributors:
        if term.correlation_group is not None:
            groups.setdefault(term.correlation_group, []).append(term)
    return groups


def _combine(
    rule: CombinationRule, contributors: tuple[Contributor, ...], values: dict[str, float]
) -> float:
    if rule is CombinationRule.WORST_CASE:
        return sum(values[t.name] for t in contributors)
    if rule is CombinationRule.RSS:
        return sqrt(sum(values[t.name] ** 2 for t in contributors))
    if rule is CombinationRule.HYBRID:
        grouped = sum(
            sum(values[m.name] for m in members) ** 2 for members in _groups(contributors).values()
        )
        independent = sum(values[t.name] ** 2 for t in contributors if t.correlation_group is None)
        return sqrt(grouped + independent)
    raise AssertionError(f"unhandled combination rule {rule!r}")


def _share(
    rule: CombinationRule,
    contributors: tuple[Contributor, ...],
    values: dict[str, float],
    term: Contributor,
    total: float,
) -> float | None:
    """The term's fraction of the total under the rule; the shares sum to one.

    Worst case shares linearly; quadrature shares the SQUARE of the total, and a correlated
    term takes its fraction of its group's square in proportion to its value.
    """
    if total == 0:
        return None
    value = values[term.name]
    if rule is CombinationRule.WORST_CASE:
        return value / total
    if rule is CombinationRule.RSS or term.correlation_group is None:
        return value**2 / total**2
    group = sum(values[m.name] for m in _groups(contributors)[term.correlation_group])
    return (group**2 / total**2) * (value / group) if group else 0.0


def _headroom(
    rule: CombinationRule,
    contributors: tuple[Contributor, ...],
    values: dict[str, float],
    term: Contributor,
    total: float,
    limit: float,
) -> tuple[float | None, str | None]:
    """The value this term could reach, the others held, with the limit exactly spent."""
    if abs(total) > limit:
        return (
            None,
            f"the budget is already spent: the total overruns the limit by "
            f"{abs(total) - limit:.4g}",
        )
    if term.compensating:
        return None, "a compensating term spends no budget; its loss is the total without it"
    value = values[term.name]
    if rule is CombinationRule.WORST_CASE:
        return limit - (total - value), None
    if rule is CombinationRule.RSS or term.correlation_group is None:
        return sqrt(limit**2 - (total**2 - value**2)), None
    group = sum(values[m.name] for m in _groups(contributors)[term.correlation_group])
    return sqrt(limit**2 - (total**2 - group**2)) - (group - value), None


class ContributorResult(StatableModel):
    """One term evaluated: its value in the limit's unit, share, and headroom."""

    model_config = ConfigDict(frozen=True)

    name: Named
    value: float
    share: float | None
    headroom: float | None
    headroom_unavailable: str | None = None


class BudgetResult(StatableModel):
    """A budget evaluated, or the reason it could not be. Numbers are in the limit's unit."""

    model_config = ConfigDict(frozen=True)

    budget: Budget
    status: CheckStatus
    reason: str | None = None
    total: float | None = None
    total_without_compensation: float | None = None
    margin: float | None = None
    group_sums: tuple[tuple[str, float], ...] = ()
    contributors: tuple[ContributorResult, ...] = ()
    governing: tuple[str, ...] = ()

    @property
    def estimated_share(self) -> float | None:
        """The fraction of the total resting on estimated values."""
        if self.status is CheckStatus.NOT_EVALUATED:
            return None
        estimated = {
            t.name for t in self.budget.contributors if t.basis is ContributorBasis.ESTIMATED
        }
        shares = [c.share for c in self.contributors if c.name in estimated]
        if any(share is None for share in shares):
            return None
        return sum(share for share in shares if share is not None)

    def to_entry(self) -> ScorecardEntry:
        """The budget as a scorecard entry: total against limit, governing term named."""
        budget = self.budget
        name = f"budget {budget.name}"
        assumed = (
            " (limit is a working assumption)"
            if budget.limit_basis is LimitBasis.ASSUMPTION
            else ""
        )
        if self.status is CheckStatus.NOT_EVALUATED:
            return ScorecardEntry(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail=f"{budget.quantity}: {self.reason}{assumed}",
            )
        assert self.total is not None and budget.rule is not None
        unit = budget.limit.unit
        governing = " and ".join(self.governing) if self.governing else "none"
        tie = " (tied)" if len(self.governing) > 1 else ""
        return ScorecardEntry(
            name=name,
            status=self.status,
            detail=(
                f"{budget.quantity} by {spoken(budget.rule, joined_by=' ')}: "
                f"total {self.total:.4g} {unit} "
                f"against {budget.limit}{assumed}; governing{tie}: {governing}"
            ),
            reference=budget.limit_source,
            underived=Underived(
                kind=DerivationAbsence.NUMERIC_RESULT,
                reason=(
                    "the arithmetic is the combination rule over every contributor — a sum, "
                    "a root-sum-square, or group sums in quadrature — and a single substituted "
                    "line over a list of arbitrary length is not one a reader can check; the "
                    "result itemizes each term, its share and its headroom instead"
                ),
            ),
            comparison=Comparison(
                measured=Quantity(magnitude=self.total, unit=unit),
                limit=budget.limit,
                sense=LimitSense.AT_MOST,
                measured_label=f"{budget.quantity} total",
                limit_label="allocated",
            ),
        )

    def __str__(self) -> str:
        budget = self.budget
        if self.status is CheckStatus.NOT_EVALUATED:
            return f"budget {budget.name}: not evaluated — {self.reason}"
        unit = budget.limit.unit
        lines = [str(self.to_entry().detail)]
        lines += [f"  {group}: sum {total:.4g} {unit}" for group, total in self.group_sums]
        for term in self.contributors:
            share = "—" if term.share is None else f"{term.share:.1%}"
            room = (
                f"headroom {term.headroom:.4g} {unit}"
                if term.headroom is not None
                else f"no headroom: {term.headroom_unavailable}"
            )
            lines.append(f"  {term.name}: {term.value:.4g} {unit}, {share} of total, {room}")
        return "\n".join(lines)
