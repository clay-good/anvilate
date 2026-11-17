"""CAE handoff: a lifting lug screened case by case on the pin loads a solver reports.

An 80 mm wide, 20 mm thick A36 lug with a 30 mm pin hole, pulled by its pin. Worked by
hand: 60 kN along the lug puts 60,000 / (50 x 20) = 60 MPa across the net section and
60,000 / (30 x 20) = 100 MPa on the pin, so against A36's 250 MPa yield the pin bearing
governs at a safety factor of 2.5.
"""

from __future__ import annotations

import pytest

from anvilate.cae import lug_on_import, read_interface_forces
from anvilate.packs.structural import LiftingLug, screen_lifting_lug
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

HEADER = "case,interface,point,x,y,z,fx,fy,fz,mx,my,mz\n"


def _q(v: float, unit: str) -> Quantity:
    return Quantity(magnitude=v, unit=unit)


def _lug(load: float = 1.0) -> LiftingLug:
    return LiftingLug(name="lifting lug", width=_q(80, "mm"), hole_diameter=_q(30, "mm"),
                      thickness=_q(20, "mm"), load=_q(load, "kN"), material="ASTM-A36")  # fmt: skip


def _case(name: str, at_pin: tuple[float, float, float]) -> str:
    """The pin's force on the lug at the top of the part, and its base reacting it."""
    fx, fy, fz = at_pin
    return (f"{name},pin,1,0,0,300,{fx},{fy},{fz},0,0,0\n"
            f"{name},base,2,0,0,0,{-fx},{-fy},{-fz},{fy * 300},{-fx * 300},0\n")  # fmt: skip


@pytest.fixture
def imported(tmp_path):
    path = tmp_path / "lug.csv"
    path.write_text(HEADER + _case("lift", (0, 0, 60_000)) + _case("swing", (20_000, 0, 50_000))
                    + _case("set down", (0, 0, -10_000)))  # fmt: skip
    return read_interface_forces(path, solver="a declared solver", version="2026.1",
                                 units="N-mm", coordinate_system="basic")  # fmt: skip


def _screen(imported, **kw):
    given = {"coordinate_system": "basic", "axis": (0, 0, 1), "required_safety_factor": 2.0} | kw
    return lug_on_import(_lug(), imported, "pin", **given)


def test_a_straight_pull_is_screened_as_the_hand_calculation_says(imported):
    lift = _screen(imported).cases[0]
    assert lift.evaluated and lift.axial_n == pytest.approx(60_000.0)
    by_name = {e.name: e for e in lift.card.entries}
    assert by_name["lifting lug pin bearing"].safety_factor == pytest.approx(2.5)
    assert by_name["lifting lug net tension"].safety_factor == pytest.approx(250 / 60)
    direct = screen_lifting_lug(_lug(60), required_safety_factor=2.0)
    assert [e.safety_factor for e in lift.card.entries] == pytest.approx(
        [e.safety_factor for e in direct.entries])  # fmt: skip


def test_an_oblique_pull_and_a_push_are_named_not_screened(imported):
    result = _screen(imported)
    assert result.not_evaluated == ("swing", "set down")
    swing, down = result.cases[1], result.cases[2]
    assert swing.transverse_n == pytest.approx(20_000.0) and "across the lug's axis" in swing.note
    assert "pushes the lug" in down.note and down.card is None


def test_the_governing_case_and_its_check_are_named_with_the_source(imported):
    result = _screen(imported)
    assert result.governing_case == "lift" and result.governing_factor == pytest.approx(2.5)
    text = str(result)
    assert "case lift governs, lifting lug pin bearing at a safety factor of 2.5" in text
    assert imported.source.sha256[:12] in text and "not evaluated: swing, set down" in text


def test_the_axis_is_a_direction_and_the_system_must_be_the_imports(imported):
    tilted = _screen(imported, axis=(0, 0, 2)).cases[0]
    assert tilted.axial_n == pytest.approx(60_000.0)
    with pytest.raises(RefusalError, match="lug is in 'global'"):
        _screen(imported, coordinate_system="global")
    with pytest.raises(RefusalError, match="axis"):
        _screen(imported, axis=(0, 0, 0))
    with pytest.raises(RefusalError, match="LiftingLug"):
        lug_on_import("lug", imported, "pin", coordinate_system="basic",  # type: ignore[arg-type]
                      axis=(0, 0, 1), required_safety_factor=2.0)  # fmt: skip


def test_the_page_quotes_the_factor_this_screen_computes(imported):
    import pathlib

    page = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "cae-handoff.md").read_text()
    said = f"a safety factor of {_screen(imported).governing_factor:.2g}"
    assert said == "a safety factor of 2.5"
    assert f"puts 100 MPa on the pin, {said}" in " ".join(page.split())
