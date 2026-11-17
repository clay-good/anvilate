"""CAE handoff: a rolling bearing screened case by case on the loads a solver reports.

The bearing the machinery page already works: C = 35.1 kN, C0 = 19.3 kN, X = 0.56,
Y = 1.45, 1,450 rpm, 20,000 hours asked. A shaft along x carries 4.2 kN across it and
1.1 kN along it at the bearing, so P = 0.56 x 4.2 + 1.45 x 1.1 = 3.947 kN, and the card is
the one the machinery screen gives those two loads.
"""

from __future__ import annotations

import pytest

from anvilate.cae import bearing_on_import, read_interface_forces
from anvilate.packs.machinery import RollingBearing, screen_rolling_bearing
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

HEADER = "case,interface,point,x,y,z,fx,fy,fz,mx,my,mz\n"


def _unit(radial: str = "1 N", axial: str = "0 N") -> RollingBearing:
    return RollingBearing(
        dynamic_load_rating=Quantity.parse("35.1 kN"), static_load_rating=Quantity.parse("19.3 kN"),
        radial_load=Quantity.parse(radial), axial_load=Quantity.parse(axial),
        radial_factor=0.56, axial_factor=1.45, speed=Quantity.parse("1450 rpm"),
        required_life_hours=Quantity.parse("20000 hour"), required_static_factor=1.5,
    )  # fmt: skip


def _case(name: str, force: tuple[float, float, float], twist: float = 0.0) -> str:
    fx, fy, fz = force
    # The gear 100 mm along the shaft reacts the bearing; its moment closes the free body.
    gear = f"{-fx},{-fy},{-fz},0,{-100 * fz},{100 * fy - twist}"
    return f"{name},bearing,1,0,0,0,{fx},{fy},{fz},0,0,{twist}\n{name},gear,2,100,0,0,{gear}\n"


@pytest.fixture
def imported(tmp_path):
    path = tmp_path / "shaft.csv"
    path.write_text(HEADER + _case("run", (1100, 0, 4200)) + _case("reverse", (-1100, 4200, 0))
                    + _case("cocked", (0, 0, 4200), twist=5000))  # fmt: skip
    return read_interface_forces(path, solver="a declared solver", version="2026.1",
                                 units="N-mm", coordinate_system="shaft")  # fmt: skip


def _screen(imported, **kw):
    given = {"coordinate_system": "shaft", "axis": (1, 0, 0)} | kw
    return bearing_on_import(_unit(), imported, "bearing", **given)


def test_the_force_splits_on_the_shaft_axis_into_the_machinery_screens_loads(imported):
    run = _screen(imported).cases[0]
    assert (run.radial_n, run.axial_n) == pytest.approx((4200.0, 1100.0))
    direct = screen_rolling_bearing(_unit("4.2 kN", "1.1 kN"))
    assert [e.safety_factor for e in run.card.entries] == pytest.approx(
        [e.safety_factor for e in direct.entries])  # fmt: skip


def test_an_axial_load_either_way_is_the_same_magnitude(imported):
    reverse = _screen(imported).cases[1]
    assert (reverse.radial_n, reverse.axial_n) == pytest.approx((4200.0, 1100.0))


def test_a_moment_at_the_bearing_is_named_not_screened(imported):
    result = _screen(imported)
    assert result.not_evaluated == ("cocked",)
    assert "a single rolling bearing does not carry" in result.cases[2].note
    assert result.governing_case in {"run", "reverse"}
    text = str(result)
    assert "on 4200 N radial and 1100 N axial" in text and imported.source.sha256[:12] in text


def test_a_bearing_in_another_system_or_on_no_axis_is_refused(imported):
    with pytest.raises(RefusalError, match="bearing is in 'global'"):
        _screen(imported, coordinate_system="global")
    with pytest.raises(RefusalError, match="axis"):
        _screen(imported, axis=(0, 0))
    with pytest.raises(RefusalError, match="RollingBearing"):
        bearing_on_import("6204", imported, "bearing", coordinate_system="shaft",  # type: ignore[arg-type]
                          axis=(1, 0, 0))  # fmt: skip


def test_the_page_quotes_the_equivalent_load_of_this_split(imported):
    import pathlib

    page = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "cae-handoff.md").read_text()
    run = _screen(imported).cases[0]
    equivalent = (0.56 * run.radial_n + 1.45 * run.axial_n) / 1000
    said = f"P = {equivalent:.3f} kN"
    assert said == "P = 3.947 kN" and said in " ".join(page.split())
