"""Every branch of every DSM curve evaluates to the strength it ships with.

`DSMStrength` renders the *governing* mode's curve, and each of the three curves is
piecewise — six branches for compression, seven for flexure, and the one that runs is
whichever the section's slenderness selects. A branch is only checked by a case that
reaches it, so the table below is written from the branch inward: for each one, elastic
buckling loads chosen to make that mode govern on that side of its limit.

The same evaluator the beam and plate formulas use. What it catches here is a curve
declared for the mode that lost, or the reduced expression rendered where the check took
the unreduced branch — both of which show a reviewer arithmetic nobody performed.
"""

from __future__ import annotations

import pytest

from anvilate.analysis.cold_formed_steel import (
    DSMLimitState,
    ElasticBuckling,
    dsm_compression_strength,
    dsm_flexural_strength,
)
from anvilate.units import Quantity
from formula_arithmetic import _arithmetic, _si

_SOURCE = "CUFSM finite-strip analysis, run 2026-09-02"


def _buckling(local: float, distortional: float, global_: float, unit: str) -> ElasticBuckling:
    return ElasticBuckling(
        local=Quantity(magnitude=local, unit=unit),
        distortional=Quantity(magnitude=distortional, unit=unit),
        global_=Quantity(magnitude=global_, unit=unit),
        source=_SOURCE,
    )


# (label, yield value, (P_crl, P_crd, P_cre), expected governing mode, expected formula)
_COMPRESSION = [
    # A stocky column with a very weak local mode: local governs, on the reduced branch.
    ("local reduced", 300.0, (60.0, 900.0, 3000.0), DSMLimitState.LOCAL, "(1 − 0.15·"),
    # Weak distortional mode, everything else strong.
    (
        "distortional reduced",
        300.0,
        (2000.0, 90.0, 3000.0),
        DSMLimitState.DISTORTIONAL,
        "(1 − 0.25·",
    ),
    # A slender column: the global curve governs on its elastic branch, λ_c > 1.5.
    ("global elastic branch", 300.0, (4000.0, 4000.0, 60.0), DSMLimitState.GLOBAL, "0.877/λ_c²"),
    # A stocky column, λ_c ≤ 1.5, and nothing else weaker: the inelastic column branch.
    ("global inelastic branch", 300.0, (4000.0, 4000.0, 400.0), DSMLimitState.GLOBAL, "0.658^"),
]

_FLEXURE = [
    ("local reduced", 30.0, (6.0, 90.0, 300.0), DSMLimitState.LOCAL, "(1 − 0.15·"),
    ("distortional reduced", 30.0, (200.0, 9.0, 300.0), DSMLimitState.DISTORTIONAL, "(1 − 0.22·"),
    # M_cre < 0.56·M_y: fully elastic lateral-torsional buckling, M_ne = M_cre.
    ("global elastic branch", 30.0, (400.0, 400.0, 12.0), DSMLimitState.GLOBAL, "M_ne = M_cre"),
    # Between the branch points: the inelastic transition.
    ("global transition", 30.0, (400.0, 400.0, 40.0), DSMLimitState.GLOBAL, "(10/9)"),
]


@pytest.mark.parametrize(
    ("label", "yield_value", "buckling", "mode", "fragment"),
    [pytest.param(*case, id=f"compression-{case[0]}") for case in _COMPRESSION],
)
def test_a_governing_compression_curve_evaluates_to_its_strength(
    label, yield_value, buckling, mode, fragment
):
    strength = dsm_compression_strength(
        yield_load=Quantity(magnitude=yield_value, unit="kN"),
        elastic_buckling=_buckling(*buckling, "kN"),
    )
    _assert_curve(strength, mode, fragment, "kN")


@pytest.mark.parametrize(
    ("label", "yield_value", "buckling", "mode", "fragment"),
    [pytest.param(*case, id=f"flexure-{case[0]}") for case in _FLEXURE],
)
def test_a_governing_flexural_curve_evaluates_to_its_strength(
    label, yield_value, buckling, mode, fragment
):
    strength = dsm_flexural_strength(
        yield_moment=Quantity(magnitude=yield_value, unit="kN*m"),
        elastic_buckling=_buckling(*buckling, "kN*m"),
    )
    _assert_curve(strength, mode, fragment, "kN*m")


def _assert_curve(strength, mode, fragment, unit):
    assert strength.governing is mode, (
        f"the case was chosen to make {mode.value} govern; {strength.governing.value} did"
    )
    assert fragment in strength.governing_formula, (
        f"expected the {fragment!r} branch; got {strength.governing_formula!r}"
    )
    work = strength.derivation("AISI S100 Appendix 1 (Direct Strength Method)")
    assert work.unresolved_symbols() == ()
    values = {item.symbol: _si(item.value) for item in work.inputs}
    computed = _arithmetic(work.symbolic, values)
    expected = strength.nominal.pint.to_base_units().magnitude
    assert computed == pytest.approx(expected, rel=1e-9), (
        f"{strength.governing_formula!r} evaluates to {computed:.6g}; the check returned "
        f"{expected:.6g} (SI base units)"
    )


def test_a_governing_reduction_curve_is_never_the_unreduced_branch():
    """`_reduction_work` has an unreduced branch, and no input can make it the one rendered.

    Not an oversight — an argument. Below its slenderness limit the local curve returns its
    anchor P_ne exactly, so it ties with the global mode and `_governing` (a `min` over a
    dict whose first key is GLOBAL) keeps the global one. The distortional curve returns
    P_y, and P_ne ≤ P_y for every λ_c, so it can never be the smallest. This sweeps the
    space rather than restating the argument: whenever local or distortional governs, the
    rendered line is a reduction.

    If this ever fails, the unreduced branch has become reachable and the gloss it writes
    ("takes nothing off") is a sentence a reviewer will now read — check it says the truth
    for whatever made it reachable.
    """
    seen = set()
    for elastic in (5.0, 30.0, 60.0, 150.0, 300.0, 900.0, 3000.0, 20000.0):
        for other in (60.0, 400.0, 5000.0):
            strength = dsm_compression_strength(
                yield_load=Quantity.parse("300 kN"),
                elastic_buckling=_buckling(elastic, other, 3000.0, "kN"),
            )
            seen.add(strength.governing)
            if strength.governing in (DSMLimitState.LOCAL, DSMLimitState.DISTORTIONAL):
                assert "(1 − " in strength.governing_formula, strength.governing_formula
    assert {DSMLimitState.LOCAL, DSMLimitState.DISTORTIONAL} <= seen, (
        f"the sweep never reached a reduction-governed case, so it proved nothing: {seen}"
    )


def test_the_rendered_curve_is_the_mode_that_governed():
    """Three curves are computed and one decides; rendering a fixed one would sometimes
    render the mode that lost.
    """
    weak_local = dsm_compression_strength(
        yield_load=Quantity.parse("300 kN"),
        elastic_buckling=_buckling(60.0, 900.0, 3000.0, "kN"),
    )
    weak_distortional = dsm_compression_strength(
        yield_load=Quantity.parse("300 kN"),
        elastic_buckling=_buckling(2000.0, 90.0, 3000.0, "kN"),
    )
    assert weak_local.governing_formula.startswith("P_nl =")
    assert weak_distortional.governing_formula.startswith("P_nd =")
