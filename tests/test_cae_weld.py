"""CAE handoff: a fillet-weld group screened case by case on loads from a solver.

Two vertical welds, 100 mm long at x = ±50 mm, 5 mm legs. Worked by hand, away from the
code, for 1 kN sideways at 100 mm from the weld centroid: L = 200 mm and
J = 2(100³/12 + 100·50²) = 666,667 mm³, so a corner carries 5 N/mm direct and
100,000 x 70.71 / 666,667 = 10.61 N/mm torsional at right angles to its radius, which sum to
sqrt(7.5² + 12.5²) = 14.58 N/mm, and 14.58 / (0.707 x 5) = 4.124 MPa on the throat.
"""

from __future__ import annotations

import math

import pytest

from anvilate.analysis.weld import eccentric_weld_group_peak_stress
from anvilate.cae import read_interface_forces, weld_group_on_import
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

HEADER = "case,interface,point,x,y,z,fx,fy,fz,mx,my,mz\n"
HAND_MPA = math.hypot(7.5, 12.5) / (0.707 * 5)


def _q(v: float, unit: str) -> Quantity:
    return Quantity(magnitude=v, unit=unit)


def _lines(points=((50, -50, 50, 50), (-50, -50, -50, 50))):
    return [((_q(a, "mm"), _q(b, "mm")), (_q(c, "mm"), _q(d, "mm"))) for a, b, c, d in points]


def _row(case: str, where: str, x: float, y: float, f: tuple, m: tuple = (0, 0, 0)) -> str:
    return f"{case},{where},1,{x},{y},0,{f[0]},{f[1]},{f[2]},{m[0]},{m[1]},{m[2]}\n"


@pytest.fixture
def imported(tmp_path):
    # Each case: the load on the bracket's tip, and the weld's reaction at its centroid.
    text = (HEADER
            + _row("side", "tip", 100, 0, (0, 1000, 0))
            + _row("side", "weld", 0, 0, (0, -1000, 0), (0, 0, -100_000))
            + _row("along", "tip", 0, 100, (1000, 0, 0))
            + _row("along", "weld", 0, 0, (-1000, 0, 0), (0, 0, 100_000))
            + _row("peel", "tip", 0, 0, (0, 0, 1000))
            + _row("peel", "weld", 0, 0, (0, 0, -1000))
            + _row("spin", "tip", 0, 0, (0, 0, 0), (0, 0, 5000))
            + _row("spin", "weld", 0, 0, (0, 0, 0), (0, 0, -5000)))  # fmt: skip
    path = tmp_path / "weld.csv"
    path.write_text(text)
    return read_interface_forces(path, solver="a declared solver", version="2026.1",
                                 units="N-mm", coordinate_system="basic")  # fmt: skip


def _screen(imported, **kw):
    given = {"coordinate_system": "basic", "leg_size": _q(5, "mm"), "allowable": _q(4.0, "MPa"),
             "allowable_source": "a declared allowable"} | kw  # fmt: skip
    return weld_group_on_import(_lines(), imported, "weld", **given)


def test_a_side_load_reaches_the_peak_the_hand_calculation_does(imported):
    side = _screen(imported).cases[0]
    assert side.evaluated and side.eccentricity_mm == pytest.approx(100.0)
    assert side.peak_stress_mpa == pytest.approx(HAND_MPA, rel=1e-9)
    assert side.peak_stress_mpa == pytest.approx(4.124, abs=5e-4)


def test_a_load_along_x_is_the_same_method_with_the_welds_turned(imported):
    along = _screen(imported).cases[1]
    # The same load turned a quarter: the welds, turned with it, lie along y = ±50.
    turned = eccentric_weld_group_peak_stress(
        segments=_lines(((50, 50, -50, 50), (50, -50, -50, -50))), load=_q(1000, "N"),
        eccentricity=_q(-100, "mm"), leg_size=_q(5, "mm"),
    )  # fmt: skip
    assert along.peak_stress_mpa == pytest.approx(turned.to("MPa").magnitude, rel=1e-9)
    assert along.eccentricity_mm == pytest.approx(-100.0)


def test_the_verdict_is_against_the_declared_allowable_and_names_its_source(imported):
    result = _screen(imported)
    assert result.governing_ratio == pytest.approx(
        max(HAND_MPA, result.cases[1].peak_stress_mpa) / 4.0
    )
    assert result.passes is False
    assert "PAST the 4 MPa allowable (a declared allowable)" in str(result)
    assert _screen(imported, allowable=_q(10, "MPa")).passes is True


def test_what_the_in_plane_method_cannot_take_is_named_not_dropped(imported):
    result = _screen(imported)
    assert result.not_evaluated == ("peel", "spin")
    peel, spin = result.cases[2], result.cases[3]
    assert "out of the weld's plane" in peel.note and peel.out_of_plane_n == pytest.approx(1000)
    assert "no shear to set the load's direction" in spin.note


def test_a_weld_group_in_another_system_or_without_an_allowable_is_refused(imported):
    with pytest.raises(RefusalError, match="weld group is in 'global'"):
        _screen(imported, coordinate_system="global")
    with pytest.raises(RefusalError, match="positive stress"):
        _screen(imported, allowable=_q(4, "mm"))
    with pytest.raises(RefusalError, match="allowable_source"):
        _screen(imported, allowable_source=" ")
    with pytest.raises(RefusalError, match="segments"):
        weld_group_on_import("welds", imported, "weld", coordinate_system="basic",  # type: ignore[arg-type]
                             leg_size=_q(5, "mm"), allowable=_q(4, "MPa"),
                             allowable_source="a")  # fmt: skip


def test_the_page_quotes_the_throat_stress_this_screen_computes(imported):
    import pathlib

    page = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "cae-handoff.md").read_text()
    side = _screen(imported).cases[0]
    said = f"{side.peak_stress_mpa:.3f} MPa on a 5 mm leg's throat"
    assert said == "4.124 MPa on a 5 mm leg's throat" and said in " ".join(page.split())
