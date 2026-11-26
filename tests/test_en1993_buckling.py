"""EN 1993-1-1 §6.3 member buckling, against the JRC report's three worked results.

An HEB 340 column on curve c, and an IPE 400 beam worked twice on curve b at two very
different slendernesses. The pair of beam cases is the useful part: one point on a curve can
be hit by a wrong curve with a compensating error, two on the same curve cannot.

The report rounds at every step of λ̄ → Φ → χ, and one of its three answers is only
reachable by reproducing both of its roundings. That is asserted explicitly rather than
smoothed over with a loose tolerance.
"""

from __future__ import annotations

from math import sqrt

import pytest

from anvilate.analysis.column import euler_buckling_load
from anvilate.analysis.en1993_buckling import (
    EuropeanBucklingCurve,
    buckling_may_be_neglected,
    buckling_reduction_factor,
    curve_imperfection_factor,
    flexural_buckling_resistance,
    lateral_torsional_buckling_resistance,
    lateral_torsional_curve,
    lateral_torsional_reduction_rolled,
    lateral_torsional_slenderness,
    non_dimensional_slenderness,
    reference_slenderness,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

_S355 = Q("355 MPa")
_M1 = 1.0  # the report's γ_M1 throughout
#: The IPE 400 of both worked beam cases.
_IPE_400_MODULUS = Q("1307e3 mm^3")


def _kn(force: Quantity) -> float:
    return force.to("kN").magnitude


def _knm(moment: Quantity) -> float:
    return moment.to("kN*m").magnitude


# --- the curves themselves ----------------------------------------------------------------


def test_the_five_imperfection_factors_are_the_sources_own():
    """0,13 / 0,21 / 0,34 / 0,49 / 0,76 for a₀, a, b, c and d, in that order."""
    assert [curve_imperfection_factor(curve) for curve in EuropeanBucklingCurve] == [
        0.13,
        0.21,
        0.34,
        0.49,
        0.76,
    ]


def test_a_curve_that_is_not_one_of_the_five_is_refused():
    with pytest.raises(RefusalError, match="EuropeanBucklingCurve"):
        curve_imperfection_factor("b")  # type: ignore[arg-type]


def test_the_curves_are_ordered_and_the_spread_between_them_is_large():
    """a₀ keeps the most and d the least, at every slenderness past the plateau.

    The ordering is the only structural claim the five curves make, and it is what a wrong
    imperfection factor breaks without changing the shape of anything.
    """
    for slenderness in (0.5, 1.0, 1.5, 2.0):
        reductions = [
            buckling_reduction_factor(slenderness=slenderness, curve=curve)
            for curve in EuropeanBucklingCurve
        ]
        assert reductions == sorted(reductions, reverse=True), slenderness
    at_one = {
        curve: buckling_reduction_factor(slenderness=1.0, curve=curve)
        for curve in EuropeanBucklingCurve
    }
    assert at_one[EuropeanBucklingCurve.A0] == pytest.approx(0.7253, abs=0.0001)
    assert at_one[EuropeanBucklingCurve.D] == pytest.approx(0.4671, abs=0.0001)
    spread = at_one[EuropeanBucklingCurve.A0] / at_one[EuropeanBucklingCurve.D]
    assert spread == pytest.approx(1.553, abs=0.001), "a0 keeps 55% more than d at λ̄ = 1"


def test_the_reference_slenderness_agrees_with_the_sources_93_9_epsilon():
    """λ₁ = π√(E/f_y) and 93,9ε are the same number, which is a check on both."""
    at_s235 = reference_slenderness(elastic_modulus=Q("210 GPa"), yield_strength=Q("235 MPa"))
    assert at_s235 == pytest.approx(93.91, abs=0.01)
    epsilon = sqrt(235.0 / 355.0)
    at_s355 = reference_slenderness(elastic_modulus=Q("210 GPa"), yield_strength=_S355)
    assert at_s355 == pytest.approx(93.91 * epsilon, rel=1e-4)


def test_chi_is_capped_at_one_on_the_plateau():
    """Below λ̄ = 0,2 the expression exceeds 1 and the clause's own `but` binds."""
    for slenderness in (0.0, 0.1, 0.2):
        for curve in EuropeanBucklingCurve:
            assert buckling_reduction_factor(slenderness=slenderness, curve=curve) == 1.0
    assert buckling_reduction_factor(slenderness=0.21, curve=EuropeanBucklingCurve.D) < 1.0


# --- the worked column ----------------------------------------------------------------------


def test_the_worked_heb_340_column():
    """JRC §1.3.3.2: curve c at λ̄ = 0,75 gives Φ = 0,92, χ = 0,69, N_b,Rd = 4186,2 kN."""
    chi = buckling_reduction_factor(slenderness=0.75, curve=EuropeanBucklingCurve.C)
    assert round(chi, 2) == 0.69
    # Φ, recomputed here so the intermediate the report prints is pinned too.
    phi = 0.5 * (1 + 0.49 * (0.75 - 0.2) + 0.75**2)
    assert round(phi, 2) == 0.92
    assert chi == pytest.approx(1 / (phi + sqrt(phi**2 - 0.75**2)), rel=1e-12)
    # The report's own N_b,Rd uses its rounded χ = 0,69.
    assert 0.69 * 170.9e2 * 355 / 1000 == pytest.approx(4186.2, abs=0.05)
    end_to_end = flexural_buckling_resistance(
        area=Q("170.9 cm^2"),
        yield_strength=_S355,
        partial_factor_m1=_M1,
        slenderness=0.75,
        curve=EuropeanBucklingCurve.C,
    )
    # Unrounded χ = 0,6935, so 4207,6 kN — 0,5% above the report's printed figure, and all
    # of it that rounding.
    assert _kn(end_to_end) == pytest.approx(4207.6, abs=0.1)
    assert _kn(end_to_end) / 4186.2 == pytest.approx(1.005, abs=0.001)


def test_the_slenderness_comes_from_the_existing_euler_load():
    """λ̄ = √(A f_y/N_cr), with N_cr from the library's own Euler function.

    Not reimplemented here: `column.euler_buckling_load` is already π²EI/(KL)², and a second
    copy would be a second place to be wrong.
    """
    critical = euler_buckling_load(
        elastic_modulus=Q("210 GPa"),
        second_moment=Q("9690 cm^4"),
        length=Q("4 m"),
        effective_length_factor=1.0,
    )
    slenderness = non_dimensional_slenderness(
        area=Q("170.9 cm^2"), yield_strength=_S355, critical_load=critical
    )
    # A squash load of 6067 kN against this N_cr: the ratio's root.
    assert slenderness == pytest.approx(sqrt(170.9e2 * 355 / critical.to("N").magnitude), rel=1e-12)
    assert 0.5 < slenderness < 1.5


def test_buckling_can_be_neglected_by_either_of_the_clauses_two_escapes():
    """λ̄ ≤ 0,2 OR N_Ed/N_cr ≤ 0,04, and either one is enough (clause 6.3.1.2(4))."""
    assert buckling_may_be_neglected(slenderness=0.2)
    assert not buckling_may_be_neglected(slenderness=0.3)
    # The second escape rescues a stocky-enough load even at a higher slenderness.
    assert buckling_may_be_neglected(
        slenderness=1.5, axial_force=Q("4 kN"), critical_load=Q("100 kN")
    )
    assert not buckling_may_be_neglected(
        slenderness=1.5, axial_force=Q("5 kN"), critical_load=Q("100 kN")
    )


def test_the_second_escape_needs_both_of_its_inputs():
    """One without the other would silently test only the slenderness and read False."""
    with pytest.raises(RefusalError, match="declared together or not at all"):
        buckling_may_be_neglected(slenderness=1.5, axial_force=Q("4 kN"))


# --- the worked beam, twice ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("critical_knm", "published_slenderness", "published_chi", "published_resistance"),
    [(164.7, 1.68, 0.28, 129.9), (1778.8, 0.51, 0.89, 412.9)],
)
def test_the_worked_ipe_400_beam(
    critical_knm: float,
    published_slenderness: float,
    published_chi: float,
    published_resistance: float,
):
    """JRC §1.3.4.2, both cases: curve b, λ̄_LT from M_cr, then χ_LT and M_b,Rd."""
    slenderness = lateral_torsional_slenderness(
        section_modulus=_IPE_400_MODULUS,
        yield_strength=_S355,
        critical_moment=Quantity(magnitude=critical_knm, unit="kN*m"),
    )
    assert round(slenderness, 2) == published_slenderness
    # The report's M_b,Rd follows from its own rounded χ_LT.
    assert published_chi * 1307e3 * 355 / 1e6 == pytest.approx(published_resistance, abs=0.05)
    resistance = lateral_torsional_buckling_resistance(
        section_modulus=_IPE_400_MODULUS,
        yield_strength=_S355,
        partial_factor_m1=_M1,
        reduction=buckling_reduction_factor(slenderness=slenderness, curve=EuropeanBucklingCurve.B),
    )
    assert _knm(resistance) == pytest.approx(published_resistance, rel=0.02)


def test_the_first_beam_case_matches_the_reports_chi_exactly():
    """At λ̄_LT = 1,68 the unrounded χ_LT is 0,2837, which rounds to the printed 0,28."""
    chi = buckling_reduction_factor(slenderness=1.68, curve=EuropeanBucklingCurve.B)
    assert round(chi, 2) == 0.28
    phi = 0.5 * (1 + 0.34 * (1.68 - 0.2) + 1.68**2)
    assert round(phi, 2) == 2.16


def test_the_second_beam_case_needs_the_reports_two_roundings():
    """0,89 is only reachable by rounding λ̄_LT to 0,51 AND Φ_LT to 0,68.

    From λ̄_LT = 0,51 the module computes Φ_LT = 0,68275 and χ_LT = 0,8798, which rounds to
    0,88. The report prints Φ_LT = 0,68 and, computing from that, 0,885 — which rounds to the
    0,89 it shows. The chain is rounded twice, and this is the one of the three worked
    results where that changes the printed figure. The module rounds at neither step.
    """
    phi_exact = 0.5 * (1 + 0.34 * (0.51 - 0.2) + 0.51**2)
    assert phi_exact == pytest.approx(0.68275, abs=1e-5)
    chi_module = buckling_reduction_factor(slenderness=0.51, curve=EuropeanBucklingCurve.B)
    assert chi_module == pytest.approx(0.87976, abs=1e-5)
    assert round(chi_module, 2) == 0.88
    # The report's own value, from its printed Φ_LT of 0,68.
    chi_report = 1 / (0.68 + sqrt(0.68**2 - 0.51**2))
    assert chi_report == pytest.approx(0.88513, abs=1e-5)
    assert round(chi_report, 2) == 0.89
    assert abs(chi_report - chi_module) / chi_module < 0.01


# --- the two curve-selection tables ------------------------------------------------------------


@pytest.mark.parametrize(
    ("height_mm", "width_mm", "rolled", "general", "alternative"),
    [
        (300, 300, True, "a", "b"),  # rolled, h/b = 1 <= 2
        (400, 180, True, "b", "c"),  # rolled, h/b = 2,22 > 2
        (300, 300, False, "c", "c"),  # welded, h/b <= 2
        (400, 180, False, "d", "d"),  # welded, h/b > 2
        (400, 200, True, "a", "b"),  # exactly h/b = 2 is the <= side
    ],
)
def test_both_lateral_torsional_curve_tables(
    height_mm: int, width_mm: int, rolled: bool, general: str, alternative: str
):
    """Tables 1.22 and 1.23, every row, and the boundary at h/b = 2 on the `<=` side."""
    common = {
        "height": Quantity(magnitude=height_mm, unit="mm"),
        "width": Quantity(magnitude=width_mm, unit="mm"),
        "rolled": rolled,
    }
    assert lateral_torsional_curve(**common).value == general
    assert lateral_torsional_curve(alternative_method=True, **common).value == alternative


def test_the_two_methods_choose_differently_from_the_same_geometry():
    """A rolled I with h/b <= 2 is curve a generally and curve b alternatively.

    The alternative method is not the general one rearranged, so which method a design uses
    has to be declared. Getting it wrong is a one-curve error in the unconservative
    direction under the general method's reading.
    """
    common = {"height": Q("300 mm"), "width": Q("300 mm"), "rolled": True}
    assert lateral_torsional_curve(**common) is EuropeanBucklingCurve.A
    assert lateral_torsional_curve(alternative_method=True, **common) is EuropeanBucklingCurve.B
    assert curve_imperfection_factor(EuropeanBucklingCurve.A) < curve_imperfection_factor(
        EuropeanBucklingCurve.B
    )


def test_rolled_must_be_declared_as_a_boolean():
    """A rolled and a welded section take different curves at the same h/b."""
    with pytest.raises(RefusalError, match="rolled is True"):
        lateral_torsional_curve(height=Q("300 mm"), width=Q("300 mm"), rolled=1)  # type: ignore[arg-type]


# --- the alternative method's own shape -----------------------------------------------------------


def test_the_alternative_method_carries_its_second_cap():
    """χ_LT ≤ 1/λ̄_LT² as well as ≤ 1,00, and the second binds above λ̄_LT = 1.

    Dropping it is the easy mistake, and it is what keeps the alternative method from being
    more generous than the general one at high slenderness. At λ̄_LT = 2 the cap is 0,25.
    """
    chi = lateral_torsional_reduction_rolled(
        slenderness=2.0,
        curve=EuropeanBucklingCurve.B,
        slenderness_limit=0.4,
        beta=0.75,
    )
    assert chi <= 0.25 + 1e-12
    assert chi == pytest.approx(0.25, abs=0.02)
    # And below the limit the plateau holds it at 1.
    assert (
        lateral_torsional_reduction_rolled(
            slenderness=0.3,
            curve=EuropeanBucklingCurve.B,
            slenderness_limit=0.4,
            beta=0.75,
        )
        == 1.0
    )


def test_the_alternative_method_is_more_generous_than_the_general_one_in_its_range():
    """Which is the point of it: β < 1 and a higher plateau both raise χ_LT.

    Checked over the range where the second cap does not bind, because above that the two
    methods converge by construction.
    """
    for slenderness in (0.6, 0.8, 1.0):
        general = buckling_reduction_factor(slenderness=slenderness, curve=EuropeanBucklingCurve.B)
        alternative = lateral_torsional_reduction_rolled(
            slenderness=slenderness,
            curve=EuropeanBucklingCurve.B,
            slenderness_limit=0.4,
            beta=0.75,
        )
        assert alternative > general, slenderness


def test_the_national_parameters_have_no_defaults():
    """λ̄_LT,0 and β are the National Annex's; the source only recommends bounds."""
    import inspect

    signature = inspect.signature(lateral_torsional_reduction_rolled)
    for name in ("slenderness_limit", "beta"):
        assert signature.parameters[name].default is inspect.Parameter.empty, name


@pytest.mark.parametrize("beta", [0.0, -0.75])
def test_a_beta_that_is_not_positive_is_refused(beta: float):
    with pytest.raises(RefusalError, match="beta must be positive"):
        lateral_torsional_reduction_rolled(
            slenderness=1.0,
            curve=EuropeanBucklingCurve.B,
            slenderness_limit=0.4,
            beta=beta,
        )


# --- refusals -------------------------------------------------------------------------------------


def test_a_negative_slenderness_is_refused():
    with pytest.raises(RefusalError, match="cannot be negative"):
        buckling_reduction_factor(slenderness=-0.5, curve=EuropeanBucklingCurve.B)


@pytest.mark.parametrize("poison", [float("nan"), float("inf")])
def test_a_non_finite_slenderness_cannot_reach_the_square_root(poison: float):
    """A NaN slenderness would make Φ² − λ̄² a NaN and `sqrt` would raise or return one."""
    with pytest.raises((RefusalError, ValueError)):
        buckling_reduction_factor(slenderness=poison, curve=EuropeanBucklingCurve.B)


def test_a_reduction_outside_zero_to_one_is_refused():
    with pytest.raises(RefusalError, match=r"\(0, 1\]"):
        lateral_torsional_buckling_resistance(
            section_modulus=_IPE_400_MODULUS,
            yield_strength=_S355,
            partial_factor_m1=_M1,
            reduction=1.2,
        )


def test_the_buckling_resistances_take_gamma_m1_and_refuse_a_factor_below_one():
    with pytest.raises(RefusalError, match="at least 1"):
        flexural_buckling_resistance(
            area=Q("100 cm^2"),
            yield_strength=_S355,
            partial_factor_m1=0.9,
            slenderness=0.75,
            curve=EuropeanBucklingCurve.C,
        )


def test_a_length_is_not_a_critical_moment():
    with pytest.raises(RefusalError, match=r"\[energy\]"):
        lateral_torsional_slenderness(
            section_modulus=_IPE_400_MODULUS,
            yield_strength=_S355,
            critical_moment=Q("100 mm"),
        )
