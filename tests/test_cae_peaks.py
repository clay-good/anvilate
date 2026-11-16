"""CAE handoff: peak values read from a solver as cited inputs, never as replacements.

The spec's scenario: a solver reports a peak bending stress 40% above the closed-form
estimate for the same section. Both are reported and the disagreement is named.
"""

from __future__ import annotations

import pathlib

import pytest

from anvilate.cae import compare_region_peak, read_region_peaks
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

TABLE = """case,region,quantity,value
limit,web root,stress,140
ultimate,web root,stress,-210
limit,tip,displacement,1.8
limit,web root,strain,0.0007
"""


def _q(v: float, unit: str) -> Quantity:
    return Quantity(magnitude=v, unit=unit)


@pytest.fixture
def peaks(tmp_path):
    path = tmp_path / "peaks.csv"
    path.write_text(TABLE)
    return read_region_peaks(path, solver="a declared solver", version="2026.1",
                             units="N-mm", coordinate_system="basic")  # fmt: skip


def test_a_peak_40_percent_above_the_hand_calc_is_named_with_both(peaks):
    found = compare_region_peak(peaks, region="web root", quantity="stress", case="limit",
                                estimate=_q(100, "MPa"), estimate_source="beam bending, Mc/I",
                                tolerance=0.15)  # fmt: skip
    assert found.imported.to("MPa").magnitude == pytest.approx(140.0)
    assert found.difference == pytest.approx(0.40)
    assert not found.agrees
    text = str(found)
    assert "is 40% above the estimate 100" in text and "DISAGREE past the 15% tolerance" in text
    assert "(beam bending, Mc/I)" in text and peaks.source.sha256[:12] in text


def test_with_no_case_the_largest_magnitude_governs_and_a_limit_gives_its_own_verdict(peaks):
    found = compare_region_peak(peaks, region="web root", quantity="stress",
                                estimate=_q(200, "MPa"), estimate_source="hand estimate",
                                tolerance=0.1, limit=_q(250, "MPa"),
                                limit_source="yield over 1.25")  # fmt: skip
    assert found.case == "ultimate" and found.difference == pytest.approx(0.05)
    assert found.agrees and found.within_limit is True
    past = compare_region_peak(peaks, region="web root", quantity="stress",
                               estimate=_q(200, "MPa"), estimate_source="hand estimate",
                               tolerance=0.1, limit=_q(200, "MPa"),
                               limit_source="a limit")  # fmt: skip
    assert past.within_limit is False and "PAST the limit" in str(past)


def test_each_quantity_comes_in_the_declared_system(tmp_path, peaks):
    tip = compare_region_peak(peaks, region="tip", quantity="displacement",
                              estimate=_q(1.8, "mm"), estimate_source="PL³/3EI",
                              tolerance=0.01)  # fmt: skip
    assert tip.agrees and tip.imported.to("mm").magnitude == pytest.approx(1.8)
    inches = tmp_path / "us.csv"
    inches.write_text("case,region,quantity,value\na,web,stress,10000\na,tip,displacement,0.1\n")
    us = read_region_peaks(inches, solver="s", version="1", units="lbf-in",
                           coordinate_system="basic")  # fmt: skip
    assert us.peaks[0].value.to("psi").magnitude == pytest.approx(10000.0)
    assert us.peaks[1].value.to("mm").magnitude == pytest.approx(2.54)


def test_what_cannot_be_compared_is_refused_by_name(tmp_path, peaks):
    with pytest.raises(RefusalError, match="declares no unit system"):
        read_region_peaks(tmp_path / "x.csv", solver="s", version="1", units=None,
                          coordinate_system="basic")  # fmt: skip
    with pytest.raises(RefusalError, match="the file holds tip displacement, web root"):
        compare_region_peak(peaks, region="flange", quantity="stress", estimate=_q(1, "MPa"),
                            estimate_source="e", tolerance=0.1)  # fmt: skip
    with pytest.raises(RefusalError, match="same kind"):
        compare_region_peak(peaks, region="tip", quantity="displacement",
                            estimate=_q(1, "MPa"), estimate_source="e", tolerance=0.1)  # fmt: skip
    with pytest.raises(RefusalError, match="nonzero"):
        compare_region_peak(peaks, region="tip", quantity="displacement",
                            estimate=_q(0, "mm"), estimate_source="e", tolerance=0.1)  # fmt: skip
    with pytest.raises(RefusalError, match="names its source"):
        compare_region_peak(peaks, region="tip", quantity="displacement", estimate=_q(1, "mm"),
                            estimate_source="e", tolerance=0.1, limit=_q(2, "mm"))  # fmt: skip
    bad = tmp_path / "bad.csv"
    bad.write_text("case,region,quantity,value\na,web,force,3\n")
    with pytest.raises(RefusalError, match="line 2: quantity 'force'"):
        read_region_peaks(bad, solver="s", version="1", units="N-mm", coordinate_system="b")


def test_the_page_states_the_spec_scenario_this_computes(peaks):
    page = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "cae-handoff.md").read_text()
    found = compare_region_peak(peaks, region="web root", quantity="stress", case="limit",
                                estimate=_q(100, "MPa"), estimate_source="Mc/I",
                                tolerance=0.15)  # fmt: skip
    assert f"{found.difference:.0%} above" == "40% above"
    assert "140 MPa against a 100 MPa hand estimate is 40% above it" in " ".join(page.split())
