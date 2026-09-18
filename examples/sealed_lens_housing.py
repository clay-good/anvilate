"""Worked example: a sealed lens housing, screened through its environment to a pointing budget.

A 100 mm f/4 singlet sits in a titanium-alloy cell inside a sealed housing that also carries
a 2 W display. The housing is assembled at 20 °C, soaks from −20 °C to +50 °C, and must ride
a 30 g, 11 ms half-sine shock. Each screen below answers one question about it:

- the display and its 3 K/W path to ambient warm the inside by 6 K, inside a 10 K allowance;
- the lens stays in focus at the hot extreme, 30 K of soak plus that 6 K of self-heating;
- the dry-nitrogen purge, specified to a −40 °C dew point, does not fog at −20 °C;
- the 60 µm radial gap around the cell stays open under the shock;
- and three line-of-sight terms — the cell's decenter under shock, the fold mirror's tilt,
  and the detector's lateral shift — are each held to their own allocation.

The pointing budget binds those three terms by name and combines them in quadrature, because
they come from independent causes, against a 40 µrad allocation. It passes at 36.2 µrad with
the detector governing. Declared worst-case, the same three terms would spend 55 µrad and
fail: the rule is the author's statement about the physics, and it decides the verdict.

Run it directly (``python examples/sealed_lens_housing.py``);
:func:`housing_card` and :func:`pointing_budget` are also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.optomechanics import (
    athermal_focus_scorecard,
    decenter_line_of_sight,
    dynamic_clearance_scorecard,
    enclosure_rise_scorecard,
    internal_condensation_scorecard,
    mirror_tilt_line_of_sight,
    mount_decenter,
)
from anvilate.budget import (
    Budget,
    BudgetResult,
    CombinationRule,
    Contributor,
    ContributorBasis,
    LimitBasis,
)
from anvilate.derivation import DerivationAbsence, Underived
from anvilate.scorecard import CheckStatus, Comparison, LimitSense, Scorecard, ScorecardEntry
from anvilate.units import Quantity

q = Quantity.parse
FOCAL_LENGTH = q("100 mm")
SHOCK_G = 30.0


def _pointing(name: str, shift: Quantity, allocation: float, basis: str) -> ScorecardEntry:
    comparison = Comparison(
        measured=Quantity(magnitude=shift.to("µrad").magnitude, unit="µrad"),
        limit=Quantity(magnitude=allocation, unit="µrad"),
        sense=LimitSense.AT_MOST,
        measured_label=name,
        limit_label="allocation",
        minimum_decimals=1,
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=comparison.sentence(),
        comparison=comparison,
        underived=Underived(kind=DerivationAbsence.LOOKUP, reason=basis),
    )


def housing_card() -> Scorecard:
    """Every screen the housing is held to, in the order a reviewer reads them."""
    rise = enclosure_rise_scorecard(
        "internal rise",
        dissipations={"display": q("2 W")},
        allowed_rise=q("10 K"),
        thermal_resistance=q("3 K/W"),
    )
    assert rise.comparison is not None
    hot_swing = Quantity(magnitude=30.0 + rise.comparison.measured.magnitude, unit="K")
    decenter = mount_decenter(mass=q("40 g"), acceleration=SHOCK_G, radial_stiffness=q("2e7 N/m"))
    return Scorecard(
        entries=(
            rise,
            athermal_focus_scorecard(
                "focus at the hot extreme",
                focal_length=FOCAL_LENGTH,
                f_number=4.0,
                wavelength=q("550 nm"),
                refractive_index=1.5168,
                dn_dt=q("1.6e-6 1/K"),
                glass_cte=q("7.1e-6 1/K"),
                housing_cte=q("8.6e-6 1/K"),
                housing_length=FOCAL_LENGTH,
                temperature_change=hot_swing,
            ),
            internal_condensation_scorecard(
                "fogging at the cold extreme",
                coldest_surface_temperature=q("253.15 K"),
                internal_dew_point=q("233.15 K"),
            ),
            dynamic_clearance_scorecard(
                "cell gap under shock",
                gap=q("60 µm"),
                natural_frequency=q("400 Hz"),
                peak_acceleration=SHOCK_G,
                pulse_duration=q("11 ms"),
            ),
            _pointing(
                "cell decenter",
                decenter_line_of_sight(decenter=decenter, focal_length=FOCAL_LENGTH),
                10.0,
                "the cell's decenter under the shock, over the focal length",
            ),
            _pointing(
                "fold mirror tilt",
                mirror_tilt_line_of_sight(tilt=Quantity(magnitude=2.0, unit="arcsec")),
                25.0,
                "twice the fold mirror's 2 arcsec mount tilt",
            ),
            _pointing(
                "detector shift",
                Quantity(magnitude=3.0 / 100e3 * 1e6, unit="µrad"),
                35.0,
                "a 3 µm lateral detector shift over the 100 mm focal length",
            ),
        )
    )


def pointing_budget(rule: CombinationRule = CombinationRule.RSS) -> BudgetResult:
    """The three line-of-sight terms, bound to their checks by name, against 40 µrad."""
    terms = ("cell decenter", "fold mirror tilt", "detector shift")
    declared = Budget(
        name="pointing",
        quantity="line-of-sight error",
        limit=Quantity(magnitude=40.0, unit="µrad"),
        limit_basis=LimitBasis.REQUIREMENT,
        limit_source="the housing's pointing allocation",
        rule=rule,
        contributors=tuple(
            Contributor(
                name=term,
                value=None,
                unresolved="bound to its check",
                source="the screen of the same name",
                basis=ContributorBasis.CALCULATED,
                check=term,
            )
            for term in terms
        ),
    )
    return declared.bind(housing_card()).evaluate()


def main() -> None:
    for entry in housing_card().entries:
        print(entry)
    print()
    print(pointing_budget().to_entry())
    worst = pointing_budget(CombinationRule.WORST_CASE).to_entry()
    print(f"  declared worst-case instead: {worst.detail}")


if __name__ == "__main__":
    main()
