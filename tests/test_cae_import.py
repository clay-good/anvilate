"""CAE handoff: interface loads read back from the user's solver, checked for balance.

A bracket's free body: a 1 kN load down at its tip, 100 mm out, reacted by four bolts at
(±20, ±20) mm. Worked by hand away from the code: the bolts carry 1 kN up between them
and a 100 N*m couple, so the pair at x = +20 pulls 1,500 N each way up and the pair at
x = -20 pushes 1,000 N down. The tip case balances. A second case raises the tip load to
1.1 kN and keeps the bolts, so its free body is 100 N short.
"""

from __future__ import annotations

import hashlib

import pytest

from anvilate.cae import read_interface_forces
from anvilate.refusal import RefusalError

HEADER = "case,interface,point,x,y,z,fx,fy,fz,mx,my,mz\n"
BOLTS = [(20, 20, 1500), (20, -20, 1500), (-20, 20, -1000), (-20, -20, -1000)]


def _rows(case: str, tip: float, scale_force: float = 1.0, scale_length: float = 1.0) -> str:
    out = []
    for k, (x, y, fz) in enumerate(BOLTS, start=1):
        out.append(f"{case},base,{k},{x * scale_length},{y * scale_length},0,0,0,"
                   f"{fz * scale_force},0,0,0")  # fmt: skip
    out.append(f"{case},tip,9,{100 * scale_length},0,0,0,0,{-tip * scale_force},0,0,0")
    return "\n".join(out) + "\n"


@pytest.fixture
def table(tmp_path):
    path = tmp_path / "gpforce.csv"
    path.write_text(HEADER + _rows("limit", 1000) + _rows("overload", 1100))
    return path


def _read(path, **kw):
    given = {"solver": "a declared solver", "version": "2026.1", "units": "N-mm",
             "coordinate_system": "basic"} | kw  # fmt: skip
    return read_interface_forces(path, **given)


def test_each_interface_is_its_resultant_about_its_own_centroid(table):
    imported = _read(table)
    base = imported.at("base")[0]
    assert base.case == "limit" and base.points == 4
    assert base.force_n == pytest.approx((0.0, 0.0, 1000.0))
    assert base.moment_nmm == pytest.approx((0.0, -100_000.0, 0.0))
    assert base.about_mm == pytest.approx((0.0, 0.0, 0.0))
    tip = imported.at("tip")[0]
    assert tip.force_n == pytest.approx((0.0, 0.0, -1000.0))
    assert tip.moment_nmm == pytest.approx((0.0, 0.0, 0.0))
    assert tip.about_mm == pytest.approx((100.0, 0.0, 0.0))


def test_a_free_body_that_balances_passes_and_one_that_does_not_is_named_with_its_residual(table):
    imported = _read(table)
    assert imported.cases == ("limit", "overload")
    limit, overload = imported.balance
    assert limit.balanced and limit.residual_force_n == pytest.approx(0.0, abs=1e-9)
    assert not overload.balanced
    assert overload.residual_force_n == pytest.approx(100.0)
    # The extra 100 N acts 100 mm from the centroid of the five points, at x = 20 mm.
    assert overload.residual_moment_nmm == pytest.approx(100.0 * 80.0)
    assert imported.unbalanced == ("overload",)
    assert "overload DOES NOT BALANCE: residual 100 N" in str(overload)


def test_the_tolerance_is_the_callers_and_is_stated(table):
    loose = _read(table, tolerance=0.1)
    assert loose.unbalanced == ()
    assert loose.balance[1].tolerance == 0.1


def test_the_import_carries_the_files_hash_and_what_was_declared(table):
    source = _read(table).source
    assert source.sha256 == hashlib.sha256(table.read_bytes()).hexdigest()
    assert (source.file, source.solver, source.version) == ("gpforce.csv", "a declared solver",
                                                            "2026.1")  # fmt: skip
    assert (source.units, source.coordinate_system) == ("N-mm", "basic")


def test_the_same_loads_in_kilonewtons_and_metres_read_the_same(tmp_path):
    path = tmp_path / "si.csv"
    path.write_text(HEADER + _rows("limit", 1000, scale_force=1e-3, scale_length=1e-3))
    base = _read(path, units="kN-m").at("base")[0]
    assert base.force_n == pytest.approx((0.0, 0.0, 1000.0))
    assert base.moment_nmm == pytest.approx((0.0, -100_000.0, 0.0))
    inches = tmp_path / "us.csv"
    inches.write_text(HEADER + "a,tip,1,1,0,0,0,0,-1,0,0,0\na,base,2,0,0,0,0,0,1,0,1,0\n")
    tip = _read(inches, units="lbf-in").at("base")[0]
    assert tip.moment_nmm[1] == pytest.approx(4.4482216152605 * 25.4)


def test_a_file_without_its_unit_system_is_refused_naming_it_and_the_systems(table):
    with pytest.raises(RefusalError, match=r"gpforce\.csv declares no unit system.*N-mm.*kip-ft"):
        _read(table, units=None)
    with pytest.raises(RefusalError, match="is not one of"):
        _read(table, units="psi")


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("case,interface,point,x,y,z,fx,fy,fz\n", "no mx, my, mz column"),
        (HEADER + "a,tip,1,0,0,0,0,0,heavy,0,0,0\n", "line 2: fz 'heavy' is not a number"),
        (HEADER + "a,tip,1,0,0,0,0,0,inf,0,0,0\n", "line 2: fz is inf"),
        (HEADER + ",tip,1,0,0,0,0,0,1,0,0,0\n", "names no case"),
        (HEADER, "no rows"),
    ],
)
def test_a_malformed_table_is_refused_where_it_is_wrong(tmp_path, text, said):
    path = tmp_path / "bad.csv"
    path.write_text(text)
    with pytest.raises(RefusalError, match=said):
        _read(path)


def test_an_interface_the_file_does_not_hold_is_refused_naming_those_it_does(table):
    with pytest.raises(RefusalError, match="holds base, tip"):
        _read(table).at("lug")
    with pytest.raises(RefusalError, match="tolerance"):
        _read(table, tolerance=0)


def test_the_page_quotes_the_residual_this_import_computes(table):
    import pathlib

    page = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "cae-handoff.md").read_text()
    overload = _read(table).balance[1]
    said = (f"{overload.residual_force_n:,.0f} N, and {overload.residual_moment_nmm:,.0f} "
            "N·mm about")  # fmt: skip
    assert said == "100 N, and 8,000 N·mm about" and said in " ".join(page.split())
    assert "pull 1,500 N each" in page and "push 1,000 N" in page


def test_an_import_and_each_load_read_as_what_they_hold(table):
    imported = _read(table)
    assert str(imported) == (
        f"2 case(s) at 2 interface(s) from gpforce.csv (sha256 {imported.source.sha256[:12]}) "
        "from a declared solver 2026.1, N-mm, in basic; unbalanced: overload"
    )
    assert str(imported.at("base")[0]) == "limit at base: F (0, 0, 1000) N, M (0, -1e+05, 0) N*mm"
