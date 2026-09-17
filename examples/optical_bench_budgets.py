"""Worked example: two budgets on one part, and the one that fails.

An optical bench plate carries a mass allocation and a pointing-error allocation. Each
individual screen behind them passes; the question a budget answers is what they come to
together, and the two budgets answer it differently.

The mass budget is a worst-case sum: 2.10 kg of plate, mounts, fasteners and a cable clamp
against a 2.50 kg allocation, so it passes with 0.40 kg in hand and the plate itself is the
term to attack.

The pointing budget combines in the hybrid rule, because two of its four terms are thermal
and move together: they are summed to 50 µrad before the groups are combined in quadrature,
giving 68.7 µrad against a 65 µrad allocation. It fails — with every contributing check
inside its own limit. Under plain root-sum-square the same four numbers give 59.4 µrad and
the budget would have passed, which is the reason the rule is declared and never assumed.

The governing term is the mount, not the 40 µrad jitter that is the largest single number:
removing the mount also shrinks the thermal group it is summed into. A spent budget reports
no headroom at all, honestly, rather than a negative allowance a reader might take for
slack — the mass budget, which has room, reports 1.75 kg of headroom on its plate.

Run it directly (``python examples/optical_bench_budgets.py``).
"""

from __future__ import annotations

from anvilate.budget import Budget, CombinationRule, Contributor, ContributorBasis, LimitBasis
from anvilate.units import Quantity


def _term(name: str, value: float, unit: str, basis: ContributorBasis, source: str, **fields):
    return Contributor(
        name=name,
        value=Quantity(magnitude=value, unit=unit),
        source=source,
        basis=basis,
        **fields,
    )


def mass_budget() -> Budget:
    """A worst-case sum: masses add, and there is no scatter to take credit for."""
    return Budget(
        name="bench mass",
        quantity="assembly mass",
        limit=Quantity(magnitude=2.5, unit="kg"),
        limit_basis=LimitBasis.REQUIREMENT,
        limit_source="payload ICD §3.1",
        rule=CombinationRule.WORST_CASE,
        contributors=(
            _term("plate", 1.35, "kg", ContributorBasis.CALCULATED, "solid mass from geometry"),
            _term("mounts", 0.42, "kg", ContributorBasis.MEASURED, "weighed, lot 2026-08"),
            _term("fasteners", 0.18, "kg", ContributorBasis.CALCULATED, "ISO 4762 table"),
            _term("cable clamp", 0.15, "kg", ContributorBasis.ESTIMATED, "vendor drawing"),
        ),
    )


def pointing_budget(rule: CombinationRule = CombinationRule.HYBRID) -> Budget:
    """The same four terms; the rule is what decides whether they fit.

    ``mount`` and ``bench`` are both thermal and move together, so they are declared in one
    correlation group. Under ``rss`` that group would be refused, which is the point.
    """
    return Budget(
        name="pointing error",
        quantity="line-of-sight error",
        limit=Quantity(magnitude=65.0, unit="µrad"),
        limit_basis=LimitBasis.REQUIREMENT,
        limit_source="SRD §4.2",
        rule=rule,
        contributors=(
            _term(
                "mount",
                30.0,
                "µrad",
                ContributorBasis.CALCULATED,
                "thermal tilt screen",
                correlation_group="thermal soak",
            ),
            _term(
                "bench",
                20.0,
                "µrad",
                ContributorBasis.CALCULATED,
                "thermal tilt screen",
                correlation_group="thermal soak",
            ),
            _term("jitter", 40.0, "µrad", ContributorBasis.ESTIMATED, "vibration allocation"),
            _term("alignment", 25.0, "µrad", ContributorBasis.MEASURED, "as-built survey"),
        ),
    )


def uncorrelated_pointing_total() -> float:
    """What plain root-sum-square would have called the same four terms, in µrad.

    Built without the correlation groups, because declaring them and asking for ``rss`` is
    refused: quadrature understates terms that move together.
    """
    plain = tuple(
        term.model_copy(update={"correlation_group": None})
        for term in pointing_budget().contributors
    )
    naive = Budget(
        name="pointing error, correlations ignored",
        quantity="line-of-sight error",
        limit=pointing_budget().limit,
        limit_basis=LimitBasis.REQUIREMENT,
        limit_source="SRD §4.2",
        rule=CombinationRule.RSS,
        contributors=plain,
    )
    total = naive.evaluate().total
    assert total is not None
    return total


def budget_figures() -> dict[str, float]:
    """Every figure this example's prose quotes, computed."""
    mass = mass_budget().evaluate()
    pointing = pointing_budget().evaluate()
    plate = next(term for term in mass.contributors if term.name == "plate")
    thermal = dict(pointing.group_sums)["thermal soak"]
    assert mass.total is not None and mass.margin is not None and pointing.total is not None
    return {
        "mass_total_kg": mass.total,
        "mass_margin_kg": mass.margin,
        "mass_limit_kg": mass_budget().limit.magnitude,
        "plate_headroom_kg": plate.headroom or 0.0,
        "pointing_total_urad": pointing.total,
        "pointing_limit_urad": pointing_budget().limit.magnitude,
        "thermal_group_urad": thermal,
        "jitter_urad": max(term.value for term in pointing.contributors),
        "uncorrelated_urad": uncorrelated_pointing_total(),
    }


def main() -> None:
    for budget in (mass_budget(), pointing_budget()):
        print(budget.evaluate())
        print()
    print(f"the same pointing terms uncorrelated: {uncorrelated_pointing_total():.1f} µrad")


if __name__ == "__main__":
    main()
