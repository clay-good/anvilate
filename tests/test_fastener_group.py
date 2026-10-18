"""Fastener groups: shared by stiffness or area, checked by NASA-STD-5020B Eqs. 20 and 22.

The sharing rule is NASA TM X-73305 §B1.1.1(2); the eccentric part is the rigid-plate
elastic method, checked here by statics: the shares must sum to the applied shear and
their moments about the centroid to the applied moment. The numbers are hand
calculations with their intermediates stated.
"""

from __future__ import annotations

from math import hypot

import pytest

from anvilate.analysis.fastener_group import GroupFastener, ShearPlane, fastener_group_loads
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def _mm(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="mm")


def _n(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="N")


def _f(name: str, x: float, y: float, d: float = 6.0, **extra: object) -> GroupFastener:
    fields: dict[str, object] = {
        "name": name, "x": _mm(x), "y": _mm(y), "diameter": _mm(d),
        "shear_allowable": _n(20_000), "tension_allowable": _n(25_000),
        "shear_plane": ShearPlane.BODY,
    } | extra  # fmt: skip
    return GroupFastener(**fields)  # type: ignore[arg-type]


def _square(**extra: object) -> list[GroupFastener]:
    return [_f(n, x, y, **extra) for n, x, y in (("a", 0, 0), ("b", 50, 0), ("c", 50, 50),
                                                  ("d", 0, 50))]  # fmt: skip


_ZERO = {"shear_x": _n(0), "shear_y": _n(0), "moment": Quantity(magnitude=0, unit="N*mm"),
         "load_x": _mm(0), "load_y": _mm(0), "tension": _n(0)}  # fmt: skip


def test_a_concentric_load_is_shared_equally_by_equal_fasteners():
    result = fastener_group_loads(_square(), **_ZERO | {"shear_y": _n(8_000),
                                  "load_x": _mm(25), "load_y": _mm(25)})  # fmt: skip
    assert result.centroid == pytest.approx((25, 25))
    assert [f.shear for f in result.fasteners] == pytest.approx([2_000] * 4)
    assert result.weighted_by == "shank area"


def test_an_eccentric_load_adds_the_torsional_share():
    # 8 kN down... at x = 125, 100 mm right of the centroid: M = 100 × 8,000 = 800,000 N·mm.
    # J = 4 × A × (25² + 25²) (equal areas cancel): torsional share per bolt
    # = M × r / Σr² = 800,000 × 35.355/(4 × 1,250) = 5,656.9 N, perpendicular to its radius.
    result = fastener_group_loads(_square(), **_ZERO | {"shear_y": _n(8_000),
                                  "load_x": _mm(125), "load_y": _mm(25)})  # fmt: skip
    b, c = (next(f for f in result.fasteners if f.name == n) for n in "bc")
    # bolt b at (+25, −25): torsion (+4,000, +4,000) plus direct (0, 2,000)
    assert (b.shear_x, b.shear_y) == pytest.approx((4_000, 6_000))
    assert c.shear == pytest.approx(hypot(-4_000, 6_000))
    assert result.governing in {"b", "c"}
    # statics: shares sum to the load, and their moment about the centroid to M
    assert sum(f.shear_y for f in result.fasteners) == pytest.approx(8_000)
    assert sum(f.shear_x for f in result.fasteners) == pytest.approx(0, abs=1e-9)
    arms = {"a": (-25, -25), "b": (25, -25), "c": (25, 25), "d": (-25, 25)}
    moment = sum(arms[f.name][0] * f.shear_y - arms[f.name][1] * f.shear_x
                 for f in result.fasteners)  # fmt: skip
    assert moment == pytest.approx(800_000)


def test_mixed_sizes_share_in_proportion_to_stiffness():
    """The spec's scenario: two larger and two smaller fasteners in a splice."""
    big, small = Quantity(magnitude=60_000, unit="N/mm"), Quantity(magnitude=30_000, unit="N/mm")
    pattern = [_f("A", 0, 0, 8, stiffness=big), _f("B", 30, 0, 8, stiffness=big),
               _f("C", 60, 0, 5, stiffness=small), _f("D", 90, 0, 5, stiffness=small)]  # fmt: skip
    # Σk = 180,000; the centroid at (60k×0 + 60k×30 + 30k×60 + 30k×90)/180k = 35 mm
    result = fastener_group_loads(pattern, **_ZERO | {"shear_x": _n(9_000),
                                  "load_x": _mm(35)})  # fmt: skip
    shares = {f.name: f.shear for f in result.fasteners}
    assert result.centroid[0] == pytest.approx(35)
    assert shares == pytest.approx({"A": 3_000, "B": 3_000, "C": 1_500, "D": 1_500})
    assert result.weighted_by == "stiffness"
    assert all(f.interaction > 0 for f in result.fasteners)


def test_without_stiffness_mixed_sizes_share_by_area():
    pattern = [_f("A", 0, 0, 8), _f("B", 40, 0, 4)]
    result = fastener_group_loads(pattern, **_ZERO | {"shear_x": _n(5_000),
                                  "load_x": _mm(32)})  # fmt: skip
    # areas in ratio 64:16; centroid at 40 × 16/80 = 8 mm; the load at 32 mm is off it,
    # but it acts along x through y = 0, the line of the bolts, so there is no moment
    shares = {f.name: f.shear for f in result.fasteners}
    assert result.centroid[0] == pytest.approx(8)
    assert shares == pytest.approx({"A": 4_000, "B": 1_000})


@pytest.mark.parametrize(
    ("plane", "a", "b", "eq"),
    [(ShearPlane.BODY, 2.5, 1.5, "Eq. 20"), (ShearPlane.THREADS, 1.2, 2.0, "Eq. 22")],
)
def test_the_interaction_uses_the_shear_planes_exponents(plane, a, b, eq):
    loads = _ZERO | {"shear_x": _n(10_000), "tension": _n(12_500)}
    result = fastener_group_loads([_f("x", 0, 0, shear_plane=plane)], **loads)
    (load,) = result.fasteners
    assert load.interaction == pytest.approx(0.5**a + 0.5**b, rel=1e-12)
    assert load.equation == eq
    assert "without the bending term" in str(result)


def test_pull_through_is_held_to_its_declared_allowable():
    pattern = _square(pull_through_allowable=_n(4_000))
    result = fastener_group_loads(pattern, **_ZERO | {"tension": _n(20_000)})
    assert all(f.pull_through_ratio == pytest.approx(1.25) for f in result.fasteners)
    assert all(
        f.pull_through_ratio is None for f in fastener_group_loads(_square(), **_ZERO).fasteners
    )


def test_mixing_declared_and_undeclared_stiffness_is_refused():
    pattern = [_f("A", 0, 0, stiffness=Quantity(magnitude=1e4, unit="N/mm")), _f("B", 10, 0)]
    with pytest.raises(RefusalError, match="stiffness"):
        fastener_group_loads(pattern, **_ZERO)


def test_a_moment_on_a_single_point_pattern_is_refused():
    with pytest.raises(RefusalError, match="lever arm"):
        fastener_group_loads(
            [_f("A", 0, 0)], **_ZERO | {"moment": Quantity(magnitude=1, unit="N*mm")}
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("diameter", _mm(0)), ("shear_allowable", _n(float("nan"))), ("x", _n(1)), ("name", " ")],
)
def test_bad_fastener_fields_are_refused(field, value):
    fields = {
        "name": "a", "x": _mm(0), "y": _mm(0), "diameter": _mm(6),
        "shear_allowable": _n(20_000), "tension_allowable": _n(25_000),
        "shear_plane": ShearPlane.BODY,
    } | {field: value}  # fmt: skip
    with pytest.raises(ValueError, match=field):
        GroupFastener(**fields)


def test_a_compressive_tension_and_a_repeated_name_are_refused():
    with pytest.raises(RefusalError, match="tension"):
        fastener_group_loads(_square(), **_ZERO | {"tension": _n(-1)})
    with pytest.raises(RefusalError, match="repeat"):
        fastener_group_loads([_f("a", 0, 0), _f("a", 10, 0)], **_ZERO)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_a_load_that_is_no_number_is_refused(value):
    with pytest.raises(ValueError, match="shear_x"):
        fastener_group_loads(_square(), **_ZERO | {"shear_x": _n(value)})
