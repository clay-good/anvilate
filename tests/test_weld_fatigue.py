"""The bundled welded-joint fatigue pack: CC BY 4.0 test points and the mean curve fit to them."""

from __future__ import annotations

import statistics
from math import log10
from pathlib import Path

import pytest

from anvilate._models import parse_yaml
from anvilate.standards.fatigue import CurveSurvival, LoadingMode, SpecimenGeometry
from anvilate.standards.weld_fatigue import default_weld_fatigue_records, mean_curve_from_failures

_PACK = Path(__file__).resolve().parents[1] / "src/anvilate/standards/data/weld_fatigue.yaml"


def _campaigns() -> dict:
    return parse_yaml(_PACK.read_text(encoding="utf-8"))["campaigns"]


def test_the_pack_is_the_source_release_point_for_point():
    """Counts and spot values read from the figshare release's S-N.json (md5
    55a9defc400f717147702d6c8a91f0ce), dataset_ids 1868 and 2022, every one a failure."""
    campaigns = _campaigns()
    cruciform = [tuple(p) for p in campaigns["SM50B-CRUCIFORM-R0"]["points"]]
    stir = [tuple(p) for p in campaigns["AA6082-T6-FSW-BUTT-R0.1"]["points"]]
    assert len(cruciform) == 38 and len(stir) == 19
    assert {(59, 10200000), (59, 34700000), (60, 23600000)} <= set(cruciform)
    assert {(88, 218000), (151, 9280), (152, 12100)} <= set(stir)
    assert campaigns["SM50B-CRUCIFORM-R0"]["dataset_id"] == 1868
    assert campaigns["AA6082-T6-FSW-BUTT-R0.1"]["dataset_id"] == 2022
    assert set(campaigns) == set(_POLYFIT)


def test_run_outs_are_kept_as_data_and_left_out_of_the_fit():
    """ASTM E739 fits failures; a run-out is a life the specimen exceeded, not one it had."""
    campaigns = _campaigns()
    assert [tuple(p) for p in campaigns["AA2024-T4-FSW-BUTT-R0.1"]["runouts"]] == [(84, 4309517)]
    assert len(campaigns["SCALMALLOY-FSW-BUTT-R0.1"]["runouts"]) == 3
    record = default_weld_fatigue_records()["SCALMALLOY-FSW-BUTT-R0.1"]
    assert record.provenance.specimen_count == len(campaigns["SCALMALLOY-FSW-BUTT-R0.1"]["points"])
    assert record.curve.max_cycles == max(
        n for _s, n in campaigns["SCALMALLOY-FSW-BUTT-R0.1"]["points"]
    )


_POLYFIT = {
    # numpy.polyfit(log10 Δσ, log10 N, 1) over each campaign's failures, when it was bundled.
    "SM50B-CRUCIFORM-R0": (3.698334, 246.060039),
    "AA6082-T6-FSW-BUTT-R0.1": (6.481343, 109.421898),
    "AA2024-T4-FSW-BUTT-R0.1": (5.650596, 139.519599),
    "SCALMALLOY-FSW-BUTT-R0.1": (2.939566, 77.082244),
}


@pytest.mark.parametrize("name", sorted(_POLYFIT))
def test_the_curve_is_the_e739_line_through_the_failures(name):
    """Held to a second, independent fit (the standard library's own regression), and to
    the values numpy's polyfit gave for the same points when the pack was built."""
    points = [(float(s), float(n)) for s, n in _campaigns()[name]["points"]]
    slope_b, intercept = statistics.linear_regression(
        [log10(s) for s, _n in points], [log10(n) for _s, n in points]
    )
    record = default_weld_fatigue_records()[name]
    (segment,) = record.curve.segments
    assert segment.slope == pytest.approx(-slope_b, rel=1e-12)
    expected_at_1e5 = 10 ** ((5 - intercept) / slope_b)
    got = record.allowable_stress_range(cycles=1e5, required_survival=CurveSurvival.MEAN)
    assert got.to("MPa").magnitude == pytest.approx(expected_at_1e5, rel=1e-12)

    polyfit = _POLYFIT[name]
    assert segment.slope == pytest.approx(polyfit[0], rel=1e-6)
    assert got.to("MPa").magnitude == pytest.approx(polyfit[1], rel=1e-6)


def test_a_mean_curve_answers_only_a_mean_question_inside_the_tested_range():
    record = default_weld_fatigue_records()["AA6082-T6-FSW-BUTT-R0.1"]
    assert record.curve.survival is CurveSurvival.MEAN
    assert record.allowable_stress_range(cycles=1e5, required_survival=CurveSurvival.P97_7) is None
    # Tested from 6,920 to 695,000 cycles: 2 million is past the last failure.
    assert record.curve.min_cycles == 6920 and record.curve.max_cycles == 695000
    assert record.allowable_stress_range(cycles=2e6, required_survival=CurveSurvival.MEAN) is None
    assert record.allowable_stress_range(cycles=5e3, required_survival=CurveSurvival.MEAN) is None


def test_each_record_carries_its_test_conditions_and_its_credit():
    records = default_weld_fatigue_records()
    cruciform = records["SM50B-CRUCIFORM-R0"]
    assert cruciform.specimen.geometry is SpecimenGeometry.WELDED_JOINT
    assert cruciform.specimen.loading_mode is LoadingMode.AXIAL
    assert cruciform.specimen.stress_ratio == 0.0
    assert cruciform.specimen.temperature.to("degC").magnitude == pytest.approx(23.0)
    assert cruciform.specimen.environment == "air"
    assert cruciform.specimen.thickness.to("mm").magnitude == pytest.approx(20.0)
    assert cruciform.specimen.stress_concentration_factor == pytest.approx(3.47)
    for record in records.values():
        provenance = record.provenance
        assert provenance.license.startswith("CC-BY-4.0")
        assert provenance.doi == "10.6084/m9.figshare.29254265.v2"
        assert provenance.publication and "doi:10." in provenance.publication
        points = _campaigns()[record.name]["points"]
        assert provenance.specimen_count == len(points)


def test_the_fit_needs_more_than_one_stress_level():
    """Every point at one stress range has no slope to fit."""
    with pytest.raises(ValueError, match="two or more stress ranges"):
        mean_curve_from_failures(((100.0, 1e5), (100.0, 2e5)))


def _check(stress: float, cycles: float, survival=CurveSurvival.MEAN):  # type: ignore[no-untyped-def]
    from anvilate.units import Quantity

    record = default_weld_fatigue_records()["SM50B-CRUCIFORM-R0"]
    return record.check(
        stress_range=Quantity(magnitude=stress, unit="MPa"),
        cycles=cycles,
        required_survival=survival,
        required_safety_factor=1.0,
    )


def test_a_check_against_a_record_cites_the_dataset_and_says_it_is_test_backed():
    """standards-data: a check consuming ingested data cites the dataset and distinguishes a
    test-data-backed curve from an estimated one."""
    from anvilate.scorecard import CheckStatus

    record = default_weld_fatigue_records()["SM50B-CRUCIFORM-R0"]
    allowable = record.allowable_stress_range(cycles=2e6, required_survival=CurveSurvival.MEAN)
    passing = _check(80.0, 2e6)
    assert passing.status is CheckStatus.PASS
    assert passing.safety_factor == pytest.approx(allowable.to("MPa").magnitude / 80.0)
    assert "test-data-backed mean curve through 38 specimens (SM50B steel, air, R = 0)" in (
        passing.detail
    )
    assert passing.reference == (
        "A Dataset of Fatigue Properties for Welded Joints (Deng et al., figshare, 2025), "
        "version 2, doi:10.6084/m9.figshare.29254265.v2; first reported in "
        + record.provenance.publication
    )
    assert "estimated" not in passing.detail
    # The worked line reproduces the factor from its own symbols.
    values = {item.symbol: item.value for item in passing.derivation.inputs}
    reread = (
        values["Δσ_ref"].to("MPa").magnitude
        * (values["N_ref"] / values["N"]) ** (1 / values["m"])
        / values["Δσ"].to("MPa").magnitude
    )
    assert passing.derivation.result.value == pytest.approx(reread, rel=1e-12)
    assert passing.derivation.result.value == pytest.approx(passing.safety_factor, rel=1e-12)
    assert _check(150.0, 2e6).status is CheckStatus.FAIL


def test_a_check_the_record_cannot_answer_says_which_way_it_declined():
    from anvilate.scorecard import CheckStatus

    design = _check(80.0, 2e6, CurveSurvival.P97_7)
    assert design.status is CheckStatus.NOT_EVALUATED
    assert "requires 97.7% survival" in design.detail and "mean curve answers no design" in (
        design.detail
    )
    beyond = _check(80.0, 1e9)
    assert beyond.status is CheckStatus.NOT_EVALUATED
    assert "outside the 44600 to 3.79e+07 cycles the specimens cover" in beyond.detail
    # Each decline names what to declare next, for the needs report to rank.
    for entry, wanted in ((design, "97.7% survival"), (beyond, "cover 1e+09 cycles")):
        (need,) = entry.needs
        assert need.declaration == "fatigue_record" and wanted in need.takes
    assert _check(80.0, 2e6).needs == ()


@pytest.mark.parametrize(
    ("stress", "cycles", "reason"),
    [
        (float("nan"), 2e6, "stress_range must be positive and finite"),
        (-80.0, 2e6, "stress_range must be positive and finite"),
        (80.0, float("nan"), "cycles must be positive and finite"),
        (80.0, 0.0, "cycles must be positive and finite"),
    ],
)
def test_a_check_refuses_an_applied_range_or_life_that_is_not_one(stress, cycles, reason):
    with pytest.raises(ValueError, match=reason):
        _check(stress, cycles)
