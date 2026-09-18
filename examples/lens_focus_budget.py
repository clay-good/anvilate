"""Worked example: every focus screen passes, and the focus budget does not.

An f/4 singlet at 550 nm has ±17.6 µm of depth of focus to spend. Three things spend it, and
each is screened on its own and passes:

- the thermal defocus across 40 K in a 6.1 ppm/K housing, 8.4 µm, inside the depth of focus;
- the detector seat's flatness, 9 µm against the 12 µm its drawing allows;
- the lens seat's axial runout, 8 µm against its 10 µm.

The budget binds each term to the check that produced it, by name, so the total follows the
screens rather than a copy of their numbers. Declared worst-case — these are one-sided axial
errors that can all land the same way — they come to 25.4 µm against 17.6 µm. The budget
fails with every contributing check green, which is the defect no per-check screen can see.
Under root-sum-square the same three terms total 14.7 µm and the budget would pass; that is
why the rule is declared and never assumed.

Run it directly (``python examples/lens_focus_budget.py``);
:func:`focus_budget` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.optomechanics import athermal_focus_scorecard, depth_of_focus
from anvilate.budget import (
    Budget,
    BudgetResult,
    CombinationRule,
    Contributor,
    ContributorBasis,
    LimitBasis,
)
from anvilate.derivation import DerivationAbsence, Underived
from anvilate.scorecard import (
    CheckStatus,
    Comparison,
    LimitSense,
    Scorecard,
    ScorecardEntry,
)
from anvilate.units import Quantity

q = Quantity.parse


def _allowance_check(name: str, measured: float, allowed: float, source: str) -> ScorecardEntry:
    comparison = Comparison(
        measured=Quantity(magnitude=measured, unit="µm"),
        limit=Quantity(magnitude=allowed, unit="µm"),
        sense=LimitSense.AT_MOST,
        measured_label=name,
        limit_label="drawing allowance",
        minimum_decimals=1,
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=comparison.sentence(),
        comparison=comparison,
        underived=Underived(kind=DerivationAbsence.LOOKUP, reason=source),
    )


def focus_card() -> Scorecard:
    """The three screens, each judged against its own allowance."""
    return Scorecard(
        entries=(
            athermal_focus_scorecard(
                "thermal defocus",
                focal_length=q("100 mm"),
                f_number=4.0,
                wavelength=q("550 nm"),
                refractive_index=1.5168,
                dn_dt=q("1.6e-6 1/K"),
                glass_cte=q("7.1e-6 1/K"),
                housing_cte=q("6.1e-6 1/K"),
                housing_length=q("100 mm"),
                temperature_change=q("40 K"),
            ),
            _allowance_check(
                "detector seat flatness", 9.0, 12.0, "measured flatness against the drawing"
            ),
            _allowance_check(
                "lens seat runout", 8.0, 10.0, "measured axial runout against the drawing"
            ),
        )
    )


def focus_budget(rule: CombinationRule = CombinationRule.WORST_CASE) -> Budget:
    """The depth of focus as an allocation, spent by the three checks, bound by name."""
    terms = (
        ("thermal defocus", ContributorBasis.CALCULATED, "athermal focus screen"),
        ("detector seat flatness", ContributorBasis.MEASURED, "CMM report"),
        ("lens seat runout", ContributorBasis.MEASURED, "dial indicator, as built"),
    )
    declared = Budget(
        name="focus",
        quantity="axial focus error",
        limit=depth_of_focus(wavelength=q("550 nm"), f_number=4.0),
        limit_basis=LimitBasis.REQUIREMENT,
        limit_source="±2·λ·N² at 550 nm and f/4, the Rayleigh quarter-wave depth of focus",
        rule=rule,
        contributors=tuple(
            Contributor(
                name=name,
                value=None,
                unresolved="bound to its check below",
                source=source,
                basis=basis,
                check=name,
            )
            for name, basis, source in terms
        ),
    )
    return declared.bind(focus_card())


def budget_results() -> dict[str, BudgetResult]:
    """The same three terms under the declared rule and under root-sum-square."""
    return {
        "worst case": focus_budget().evaluate(),
        "rss": focus_budget(CombinationRule.RSS).evaluate(),
    }


def main() -> None:
    for entry in focus_card().entries:
        print(entry)
    print()
    results = budget_results()
    print(results["worst case"].to_entry())
    print(f"  under root-sum-square instead: {results['rss'].to_entry().detail}")


if __name__ == "__main__":
    main()
