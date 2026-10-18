"""Preloaded joints, anchored to NASA-STD-5020B Appendix A.2's own test data and hand work.

Appendix A.2 reduces 30 measured preloads (Table 6, ten bolts of 3/8 in at 450 in-lb, three
installations each) to Ppi-nom 4,721 lb, σ 1,097 lb, Γa-max 0.644, Γa-min 0.353 and
Γ90/95 0.498, and chooses 0.353 for the minimum preload of a joint that is not
separation-critical. The standard works no margin example, so the margins are hand
calculations with every intermediate stated.
"""

from __future__ import annotations

import pytest

from anvilate.analysis.preloaded_joint import (
    FayingSurface,
    TighteningMethod,
    joint_slip_margin,
    preload_bounds,
    preload_uncertainty_from_tests,
    preloaded_joint_margins,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

# NASA-STD-5020B Table 6, in lb: three tests of each of ten bolts.
_TABLE_6 = (
    7760, 4010, 3587, 4635, 4920, 3797, 4462, 4940, 6220, 4780,
    7229, 4310, 3900, 4322, 4475, 3812, 4132, 4219, 6100, 4685,
    6080, 4291, 3054, 4804, 3910, 3303, 4090, 4550, 6062, 5180,
)  # fmt: skip


def _lbf(value: float) -> Quantity:
    return Quantity(magnitude=value, unit="lbf")


def _n(value: float) -> Quantity:
    return Quantity(magnitude=value, unit="N")


def test_appendix_a2_reduces_table_6_as_printed():
    tests = preload_uncertainty_from_tests([_lbf(p) for p in _TABLE_6])
    to_lb = 1 / 4.4482216152605
    assert tests.sample_size == 30 and tests.tolerance_factor == 2.145
    assert tests.nominal * to_lb == pytest.approx(4721, abs=0.5)
    assert tests.standard_deviation * to_lb == pytest.approx(1097, abs=0.5)
    assert tests.gamma_above == pytest.approx(0.644, abs=5e-4)
    assert tests.gamma_below == pytest.approx(0.353, abs=5e-4)
    assert tests.gamma_90_95 == pytest.approx(0.498, abs=5e-4)


def test_appendix_a2_chooses_0_353_for_the_minimum_of_a_non_critical_joint():
    tests = preload_uncertainty_from_tests([_lbf(p) for p in _TABLE_6])
    bounds = preload_bounds(
        nominal_preload=_lbf(4721), method=TighteningMethod.TORQUE_DRY, torque_tolerance=0.0,
        separation_critical=False, fastener_count=1, all_metallic_clamp=True, tests=tests,
    )  # fmt: skip
    # "Γ = 0.353 (higher of Γa-min and 0.35)"; for the maximum the 90/95 alternative, 0.498
    assert bounds.gamma_for_minimum == pytest.approx(0.353, abs=5e-4)
    assert bounds.gamma_for_maximum == pytest.approx(0.498, abs=5e-4)
    critical = preload_bounds(
        nominal_preload=_lbf(4721), method=TighteningMethod.TORQUE_DRY, torque_tolerance=0.0,
        separation_critical=True, fastener_count=1, all_metallic_clamp=True, tests=tests,
    )  # fmt: skip
    # a separation-critical joint takes the envelope: max(0.498, 0.353)
    assert critical.gamma_for_minimum == pytest.approx(0.498, abs=5e-4)


def test_table_5_between_listed_sizes_uses_the_next_smaller_size():
    # 32 is not listed; 30's s = 2.145 is larger than 35's 2.094, so it is the safe one
    sample = [_n(1000 + 10 * i) for i in range(32)]
    assert preload_uncertainty_from_tests(sample).tolerance_factor == 2.145
    assert preload_uncertainty_from_tests(sample[:2]).tolerance_factor == 31.092
    big = [_n(1000 + i) for i in range(150)]
    assert preload_uncertainty_from_tests(big).tolerance_factor == 1.875


def _bounds(*, critical: bool = False):
    return preload_bounds(
        nominal_preload=_n(10_000), method=TighteningMethod.TORQUE_DRY, torque_tolerance=0.05,
        separation_critical=critical, fastener_count=4, all_metallic_clamp=True,
    )  # fmt: skip


def test_torque_controlled_dry_with_no_tests_uses_the_labelled_default():
    bounds = _bounds()
    # max = 1.05 × 1.35 × 10,000 = 14,175 N
    assert bounds.maximum == pytest.approx(14_175, rel=1e-12)
    # Eq. 4: 0.95 × 0.65 × 10,000 = 6,175; less 5% relaxation = 5,866.25 N
    assert bounds.minimum == pytest.approx(5_866.25, rel=1e-12)
    # Eq. 5: 0.95 × (1 − 0.35/√4) × 10,000 = 7,837.5; less 5% = 7,445.625 N
    assert bounds.minimum_for_slip == pytest.approx(7_445.625, rel=1e-12)
    assert "Table 3 default" in bounds.gamma_basis and "not measured" in bounds.gamma_basis
    assert "NASA-STD-5020B" in str(bounds)


def _margins(*, n: float = 0.5, phi: float = 0.2, critical: bool = False):
    return preloaded_joint_margins(
        bounds=_bounds(critical=critical), limit_tension=_n(2_000),
        ultimate_allowable=_n(40_000), yield_allowable=_n(34_000),
        load_introduction_factor=n, stiffness_factor=phi, fitting_factor=1.15,
        ultimate_factor=1.4, yield_factor=1.25, separation_factor=1.2,
    )  # fmt: skip


def test_separation_before_rupture_uses_the_allowable_alone():
    m = _margins()
    # nφ = 0.1: P′sep = 14,175/0.9 = 15,750 N; P′tu = (40,000 − 14,175)/0.1 = 258,250 N
    assert m.separation_load == pytest.approx(15_750, rel=1e-12)
    assert m.rupture_load == pytest.approx(258_250, rel=1e-12)
    assert not m.rupture_before_separation and m.ultimate_equation.startswith("Eq. 6")
    # Eq. 6: 40,000/(1.15 × 1.4 × 2,000) − 1 = 40,000/3,220 − 1 = 11.4224
    assert m.ultimate_margin == pytest.approx(40_000 / 3_220 - 1, rel=1e-12)
    # Eq. 15: 34,000/(1.15 × 1.25 × 2,000) − 1 = 10.8261
    assert m.yield_margin == pytest.approx(34_000 / 2_875 - 1, rel=1e-12)
    # Eq. 19 with the slip minimum, the joint not separation-critical: 7,445.625/2,760 − 1
    assert m.separation_margin == pytest.approx(7_445.625 / 2_760 - 1, rel=1e-12)


def test_a_separation_critical_joint_has_no_default_and_uses_the_eq_4_minimum():
    with pytest.raises(RefusalError, match="no default preload uncertainty"):
        _bounds(critical=True)
    tests = preload_uncertainty_from_tests([_n(p) for p in (9_800, 10_000, 10_200)])
    # mean 10,000, σ 200, s(3) = 8.306: Γ90/95 = 0.16612; measured below 0.02 -> 0.16612
    bounds = preload_bounds(
        nominal_preload=_n(10_000), method=TighteningMethod.TORQUE_DRY, torque_tolerance=0.05,
        separation_critical=True, fastener_count=4, all_metallic_clamp=True, tests=tests,
    )  # fmt: skip
    assert bounds.gamma_for_minimum == pytest.approx(8.306 * 200 / 10_000, rel=1e-9)
    m = preloaded_joint_margins(
        bounds=bounds, limit_tension=_n(2_000), ultimate_allowable=_n(40_000),
        yield_allowable=_n(34_000), load_introduction_factor=0.5, stiffness_factor=0.2,
        fitting_factor=1.15, ultimate_factor=1.4, yield_factor=1.25, separation_factor=1.2,
    )  # fmt: skip
    # Eq. 4: 0.95 × (1 − 0.16612) × 10,000 × 0.95 (relaxation) = 7,525.76 N
    expected_min = 0.95 * (1 - 0.16612) * 10_000 * 0.95
    assert bounds.minimum == pytest.approx(expected_min, rel=1e-9)
    assert m.separation_margin == pytest.approx(expected_min / 2_760 - 1, rel=1e-9)


def test_rupture_before_separation_keeps_preload_and_names_both_loads():
    m = _margins(n=1.0, phi=0.9)
    # nφ = 0.9: P′sep = 14,175/0.1 = 141,750 N; P′tu = 25,825/0.9 = 28,694.4 N
    assert m.rupture_before_separation and m.ultimate_equation.startswith("Eq. 7")
    assert m.ultimate_margin == pytest.approx((25_825 / 0.9) / 3_220 - 1, rel=1e-12)
    # Eq. 16: P′ty = (34,000 − 14,175)/0.9 = 22,027.8 N, below P′sep, so yield first
    assert m.yield_margin == pytest.approx((19_825 / 0.9) / 2_875 - 1, rel=1e-12)
    text = str(m)
    assert "ruptures at 2.869e+04 N before the joint opens at 1.418e+05 N" in text


def test_slip_at_the_default_friction_ceiling():
    margin = joint_slip_margin(
        bounds=_bounds(), limit_shear=_n(500), limit_tension=_n(2_000),
        surface=FayingSurface.OTHER, factor_of_safety=1.0, fitting_factor=1.0,
    )  # fmt: skip
    # μ = 0.10: 0.1 × 7,445.625/(500 + 0.1 × 2,000) − 1 = 744.5625/700 − 1 = 0.063661
    assert margin == pytest.approx(744.5625 / 700 - 1, rel=1e-12)


def test_friction_above_the_untested_ceiling_is_refused():
    with pytest.raises(RefusalError, match="friction"):
        joint_slip_margin(
            bounds=_bounds(), limit_shear=_n(500), limit_tension=_n(0),
            surface=FayingSurface.CLEANED_UNCOATED_METAL, factor_of_safety=1.0,
            fitting_factor=1.0, friction=0.3,
        )  # fmt: skip


def test_a_non_metallic_clamp_needs_its_relaxation_declared():
    with pytest.raises(RefusalError, match="relaxation"):
        preload_bounds(
            nominal_preload=_n(10_000), method=TighteningMethod.TORQUE_LUBRICATED,
            torque_tolerance=0.05, separation_critical=False, fastener_count=4,
            all_metallic_clamp=False,
        )  # fmt: skip
    declared = preload_bounds(
        nominal_preload=_n(10_000), method=TighteningMethod.TORQUE_LUBRICATED,
        torque_tolerance=0.05, separation_critical=False, fastener_count=4,
        all_metallic_clamp=False, relaxation=_n(800),
    )  # fmt: skip
    # Eq. 4 with Γ 0.25: 0.95 × 0.75 × 10,000 − 800 = 6,325 N
    assert declared.minimum == pytest.approx(6_325, rel=1e-12)


@pytest.mark.parametrize(
    ("method", "gamma"),
    [(TighteningMethod.TORQUE_LUBRICATED, 0.25), (TighteningMethod.TORQUE_DRY, 0.35),
     (TighteningMethod.TURN_OF_NUT, 0.25), (TighteningMethod.BOLT_STRETCH, 0.10)],
)  # fmt: skip
def test_table_3_defaults(method, gamma):
    bounds = preload_bounds(
        nominal_preload=_n(1_000), method=method, torque_tolerance=0.0,
        separation_critical=False, fastener_count=1, all_metallic_clamp=True,
    )  # fmt: skip
    assert bounds.gamma_for_maximum == bounds.gamma_for_minimum == gamma


@pytest.mark.parametrize(
    ("field", "value"),
    [("load_introduction_factor", 0.0), ("load_introduction_factor", 1.2),
     ("stiffness_factor", float("nan")), ("fitting_factor", 0.9), ("separation_factor", 0.5)],
)  # fmt: skip
def test_margin_inputs_out_of_range_are_refused(field, value):
    args = {
        "bounds": _bounds(), "limit_tension": _n(2_000), "ultimate_allowable": _n(40_000),
        "yield_allowable": _n(34_000), "load_introduction_factor": 0.5, "stiffness_factor": 0.2,
        "fitting_factor": 1.15, "ultimate_factor": 1.4, "yield_factor": 1.25,
        "separation_factor": 1.2,
    } | {field: value}  # fmt: skip
    with pytest.raises(ValueError, match=field):
        preloaded_joint_margins(**args)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -5.0])
def test_a_measured_preload_that_is_no_positive_number_is_refused(value):
    with pytest.raises(ValueError, match="preloads"):
        preload_uncertainty_from_tests([_n(1000), _n(value)])


def test_one_measurement_is_no_sample():
    with pytest.raises(RefusalError, match="no sample"):
        preload_uncertainty_from_tests([_n(1000)])


def test_a_yield_allowable_above_ultimate_is_refused():
    with pytest.raises(RefusalError, match="yield_allowable"):
        preloaded_joint_margins(
            bounds=_bounds(), limit_tension=_n(2_000), ultimate_allowable=_n(30_000),
            yield_allowable=_n(34_000), load_introduction_factor=0.5, stiffness_factor=0.2,
            fitting_factor=1.15, ultimate_factor=1.4, yield_factor=1.25, separation_factor=1.2,
        )  # fmt: skip


def test_the_hand_methods_page_quotes_the_appendix_a2_figures():
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "structural-hand-methods.md").read_text()
    assert "4,721 lb nominal, 1,097 lb σ and Γ90/95 0.498" in page
    assert "chooses Γ 0.353" in page


def _embedding(per_um: float = 3.0, interfaces: int = 4):
    from anvilate.analysis.preloaded_joint import embedding_preload_loss

    return embedding_preload_loss(
        interfaces=interfaces,
        embedding_per_interface=Quantity(magnitude=per_um, unit="um"),
        source="the user's cited embedding table, machined surfaces",
        bolt_stiffness=Quantity(magnitude=200_000, unit="N/mm"),
        clamp_stiffness=Quantity(magnitude=800_000, unit="N/mm"),
    )


def test_four_interfaces_in_a_stack():
    """The spec's scenario: a bracket, a spacer and a plate, four interfaces."""
    loss = _embedding()
    # 4 × 3 µm = 0.012 mm over k = 200,000 × 800,000/1,000,000 = 160,000 N/mm: 1,920 N
    assert loss.embedding == pytest.approx(0.012, rel=1e-12)
    assert loss.loss == pytest.approx(1_920, rel=1e-12)
    bounds = preload_bounds(
        nominal_preload=_n(12_000), method=TighteningMethod.TORQUE_DRY, torque_tolerance=0.05,
        separation_critical=False, fastener_count=1, all_metallic_clamp=True, embedding=loss,
    )  # fmt: skip
    # Eq. 4: 0.95 × 0.65 × 12,000 = 7,410; embedding 1,920 beats the 5% default (370.5)
    assert bounds.relaxation == pytest.approx(1_920, rel=1e-12)
    assert bounds.minimum == pytest.approx(7_410 - 1_920, rel=1e-12)
    assert bounds.relaxation_basis == "embedding over 4 interfaces"
    assert "1920 N of preload" in str(loss)


def test_a_small_embedding_does_not_double_count_the_default():
    small = _embedding(per_um=0.1)  # 0.4 µm × 160,000 = 64 N, below the 5% default
    bounds = preload_bounds(
        nominal_preload=_n(12_000), method=TighteningMethod.TORQUE_DRY, torque_tolerance=0.05,
        separation_critical=False, fastener_count=1, all_metallic_clamp=True, embedding=small,
    )  # fmt: skip
    assert bounds.relaxation == pytest.approx(0.05 * 7_410, rel=1e-12)
    assert bounds.relaxation_basis == "Table 1 default, 5%"


def test_embedding_refusals():
    with pytest.raises(RefusalError, match="interfaces"):
        _embedding(interfaces=0)
    with pytest.raises(ValueError, match="embedding_per_interface"):
        _embedding(per_um=float("nan"))
    with pytest.raises(RefusalError, match="embedding_per_interface"):
        _embedding(per_um=-1)
