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


@pytest.mark.parametrize("name", ["SM50B-CRUCIFORM-R0", "AA6082-T6-FSW-BUTT-R0.1"])
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

    polyfit = {
        "SM50B-CRUCIFORM-R0": (3.698334, 246.060039),
        "AA6082-T6-FSW-BUTT-R0.1": (6.481343, 109.421898),
    }[name]
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
