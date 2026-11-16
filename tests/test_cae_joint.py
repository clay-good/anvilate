"""CAE handoff: a fastener pattern screened case by case on loads read back from a solver.

Four bolts at (±20, ±20) mm hold a bracket. Worked by hand, away from the code:

- **side**: 1 kN sideways (+y) at the bracket's tip, 100 mm out along x. The pattern
  carries 1 kN of shear and a 100 N*m twist about its centroid; with equal bolts the
  direct share is 250 N each and the twist adds 100,000 * 28.28 / 3,200 = 883.9 N at
  right angles to each bolt's radius, so the worst bolt carries
  sqrt(625² + 875²) = 1,075.3 N.
- **pull**: 2 kN straight up through the centroid: 500 N of tension in each bolt.
- **pry**: 1 kN down at the tip. The pattern carries a 100 N*m moment about the y axis,
  which the group method does not distribute, so the case is not evaluated.
- **short**: the side case with the tip load raised to 1.1 kN and the bolts kept: its
  free body does not balance, so it is not evaluated either.
"""

from __future__ import annotations

import math

import pytest

from anvilate.analysis.fastener_group import GroupFastener, ShearPlane
from anvilate.cae import fastener_group_on_import, read_interface_forces
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

HEADER = "case,interface,point,x,y,z,fx,fy,fz,mx,my,mz\n"
BOLTS = [(20, 20), (20, -20), (-20, 20), (-20, -20)]
SHEAR_ALLOWABLE, TENSION_ALLOWABLE = 5000.0, 6000.0


def _q(v: float, unit: str) -> Quantity:
    return Quantity(magnitude=v, unit=unit)


def _pattern() -> list[GroupFastener]:
    return [GroupFastener(name=f"b{k}", x=_q(x, "mm"), y=_q(y, "mm"), diameter=_q(6, "mm"),
                          shear_allowable=_q(SHEAR_ALLOWABLE, "N"),
                          tension_allowable=_q(TENSION_ALLOWABLE, "N"),
                          shear_plane=ShearPlane.BODY)
            for k, (x, y) in enumerate(BOLTS, start=1)]  # fmt: skip


def _case(name: str, tip: tuple[float, float, float], at: tuple[float, float, float],
          bolts: list[tuple[float, float, float]]) -> str:  # fmt: skip
    rows = [f"{name},tip,9,{at[0]},{at[1]},{at[2]},{tip[0]},{tip[1]},{tip[2]},0,0,0"]
    for k, ((x, y), f) in enumerate(zip(BOLTS, bolts, strict=True), start=1):
        rows.append(f"{name},base,{k},{x},{y},0,{f[0]},{f[1]},{f[2]},0,0,0")
    return "\n".join(rows) + "\n"


def _side_bolts(load: float) -> list[tuple[float, float, float]]:
    # On the bracket: 250 N back (-y) each, and the reacting twist of -100 N*m shared
    # by radius over the polar sum 3,200 mm².
    twist = -load * 100.0
    return [(-twist * y / 3200.0, -load / 4 + twist * x / 3200.0, 0.0) for x, y in BOLTS]


@pytest.fixture
def imported(tmp_path):
    path = tmp_path / "gpforce.csv"
    path.write_text(
        HEADER
        + _case("side", (0, 1000, 0), (100, 0, 0), _side_bolts(1000))
        + _case("pull", (0, 0, 2000), (0, 0, 0), [(0, 0, -500)] * 4)
        + _case("pry", (0, 0, -1000), (100, 0, 0),
                [(0, 0, 1500), (0, 0, 1500), (0, 0, -1000), (0, 0, -1000)])
        + _case("short", (0, 1100, 0), (100, 0, 0), _side_bolts(1000))
    )  # fmt: skip
    return read_interface_forces(path, solver="a declared solver", version="2026.1",
                                 units="N-mm", coordinate_system="bracket")  # fmt: skip


def _screen(imported, **kw):
    given = {"coordinate_system": "bracket", "away": "+z"} | kw
    return fastener_group_on_import(_pattern(), imported, "base", **given)


def test_the_side_load_reaches_the_worst_bolt_as_the_hand_calculation_does(imported):
    side = _screen(imported).cases[0]
    assert side.evaluated and side.case == "side"
    assert (side.shear_x_n, side.shear_y_n) == pytest.approx((0.0, 1000.0), abs=1e-9)
    assert side.twist_nmm == pytest.approx(100_000.0)
    assert side.governing_shear_n == pytest.approx(math.hypot(625.0, 875.0))
    assert side.governing_index == pytest.approx((math.hypot(625, 875) / SHEAR_ALLOWABLE) ** 2.5)


def test_a_pull_along_the_declared_direction_is_tension_and_the_opposite_is_none(imported):
    pull = _screen(imported).cases[1]
    assert pull.tension_n == pytest.approx(2000.0)
    assert pull.governing_index == pytest.approx((500.0 / TENSION_ALLOWABLE) ** 1.5)
    pressed = _screen(imported, away="-z").cases[1]
    assert pressed.tension_n == 0.0 and pressed.governing_index == pytest.approx(0.0)


def test_the_governing_case_is_the_highest_index_and_the_skipped_are_named(imported):
    result = _screen(imported)
    assert result.governing_case == "pull"
    assert result.governing_index == pytest.approx((500.0 / TENSION_ALLOWABLE) ** 1.5)
    assert result.not_evaluated == ("pry", "short")
    pry, short = result.cases[2], result.cases[3]
    assert pry.out_of_plane_nmm == pytest.approx(100_000.0)
    assert "about an in-plane axis" in pry.note
    assert "100 N unbalanced" in short.note
    assert result.source.sha256 in {imported.source.sha256}
    text = str(result)
    assert "case pull governs" in text and imported.source.sha256[:12] in text


def test_a_pattern_in_another_coordinate_system_is_refused_naming_both(imported):
    with pytest.raises(RefusalError, match=r"pattern is in 'global' and the loads in 'bracket'"):
        _screen(imported, coordinate_system="global")
    with pytest.raises(RefusalError, match="away"):
        _screen(imported, away="up")
    with pytest.raises(RefusalError, match="holds base, tip"):
        fastener_group_on_import(_pattern(), imported, "lug", coordinate_system="bracket",
                                 away="+z")  # fmt: skip
    with pytest.raises(RefusalError, match="InterfaceImport"):
        fastener_group_on_import(_pattern(), "gpforce.csv", "base",  # type: ignore[arg-type]
                                 coordinate_system="bracket", away="+z")  # fmt: skip


def test_the_page_quotes_the_shares_this_screen_computes(imported):
    import pathlib

    page = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "cae-handoff.md").read_text()
    side = _screen(imported).cases[0]
    twist_share = side.twist_nmm * math.hypot(20, 20) / 3200.0
    said = (
        f"{twist_share:.1f} N from the twist put the worst bolt at {side.governing_shear_n:,.1f} N"
    )
    assert said == "883.9 N from the twist put the worst bolt at 1,075.3 N"
    assert said in " ".join(page.split())
