"""Every declared beam deflection formula evaluates to the deflection it ships with.

`BeamBendingResult.deflection_formula` is a string. The structural pack renders it into a
calculation report, into the evidence bundle and into `anvilate check --show-work`, cited
as AISC 360-16 §L3 — and nothing checked that the expression is the one the function
evaluated. A transposed coefficient (185 for 184, L³ for L⁴) would have shipped a worked
calculation that disagrees with its own answer, in a document somebody signs, and every
test in the suite would still have passed: the deflection is computed from the code, not
from the string.

So this reads the formula back. Each case below is called with real quantities, the
declared symbols are substituted into the symbolic form, the result is evaluated as
arithmetic, and it has to come out at the `max_deflection` the same call returned. It is
the one assertion that can catch a formula which is merely plausible.

The evaluator is deliberately small and refuses what it does not understand — an
unsubstituted symbol, a character it cannot map — because a lenient one would pass a
formula it silently failed to read.
"""

from __future__ import annotations

import re

import pytest

from anvilate.analysis import beam
from anvilate.derivation import _scan
from anvilate.units import Quantity

_SUPERSCRIPT_DIGITS = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
}


def _arithmetic(symbolic: str, values: dict[str, float]) -> float:
    """The right-hand side of ``symbolic`` evaluated with ``values``, in SI base units.

    Substitution runs through `anvilate.derivation._scan`, the same left-to-right pass the
    rendered document uses, so this cannot read a formula the report would read
    differently — including the bracketing a superscript needs, which is where a naive
    replacement turns `L³` with L = 4 into `4**3` and `(4)³` into something else.
    """
    _, _, rhs = symbolic.partition("=")
    assert rhs, f"{symbolic!r} has no right-hand side"
    substituted, leftover = _scan(rhs, {name: f"({value!r})" for name, value in values.items()})
    assert not leftover, f"{symbolic!r} names symbols nothing declared: {leftover}"

    expression = substituted
    for glyph, digit in _SUPERSCRIPT_DIGITS.items():
        expression = expression.replace(glyph, f"@{digit}")
    # "(4.0)@3" -> "(4.0)**3"; consecutive superscript digits are one exponent.
    expression = re.sub(r"(?:@(\d))+", lambda m: "**" + m.group(0).replace("@", ""), expression)
    expression = expression.replace("·", "*").replace("−", "-").replace("–", "-")
    expression = re.sub(r"√(\d+)", r"(\1**0.5)", expression)

    unreadable = sorted(set(expression) - set("0123456789.+-*/() e"))
    assert not unreadable, f"the evaluator cannot read {unreadable} in {symbolic!r}"
    return eval(expression, {"__builtins__": {}}, {})  # noqa: S307 - a closed arithmetic string


def _si(value) -> float:
    """A declared symbol's value as a bare number in SI base units.

    Every symbol in one formula has to be reduced by the same rule or the arithmetic is
    meaningless — a length in mm beside a modulus in GPa evaluates to a number with no
    relation to the answer. A dimensionless input passes through.
    """
    if isinstance(value, Quantity):
        return float(value.pint.to_base_units().magnitude)
    return float(value)


# Every load case in `anvilate.analysis.beam` that returns a BeamBendingResult, with
# arguments that put it well inside its own domain. Deliberately asymmetric numbers: a
# 2 m offset on a 4 m span makes half the formulas below agree with a wrong one.
_SECTION = {
    "second_moment": Quantity.parse("2.4e7 mm^4"),
    "extreme_fibre": Quantity.parse("75 mm"),
    "elastic_modulus": Quantity.parse("200 GPa"),
}
_SPAN = {"length": Quantity.parse("4 m")}
_FORCE = {"force": Quantity.parse("12 kN")}
_UDL = {"distributed_load": Quantity.parse("5 kN/m")}
_TRIANGLE = {"peak_distributed_load": Quantity.parse("5 kN/m")}
_COUPLE = {"moment": Quantity.parse("8 kN*m")}
_OFFSET = {"load_position": Quantity.parse("1.5 m")}
_PATCH = {"loaded_length": Quantity.parse("1.5 m")}

_CASES = [
    (beam.cantilever_end_load, {**_FORCE, **_SPAN, **_SECTION}),
    (beam.cantilever_offset_load, {**_FORCE, **_OFFSET, **_SPAN, **_SECTION}),
    (beam.cantilever_uniform_load, {**_UDL, **_SPAN, **_SECTION}),
    (beam.cantilever_partial_uniform_load, {**_UDL, **_PATCH, **_SPAN, **_SECTION}),
    (beam.cantilever_center_patch_load, {**_UDL, **_PATCH, **_SPAN, **_SECTION}),
    (beam.cantilever_triangular_load, {**_TRIANGLE, **_SPAN, **_SECTION}),
    (beam.cantilever_triangular_load_peak_at_tip, {**_TRIANGLE, **_SPAN, **_SECTION}),
    (beam.cantilever_end_moment, {**_COUPLE, **_SPAN, **_SECTION}),
    (beam.cantilever_offset_moment, {**_COUPLE, **_OFFSET, **_SPAN, **_SECTION}),
    (beam.simply_supported_center_load, {**_FORCE, **_SPAN, **_SECTION}),
    (beam.simply_supported_offset_load, {**_FORCE, **_OFFSET, **_SPAN, **_SECTION}),
    (
        beam.simply_supported_symmetric_point_loads,
        {**_FORCE, "load_offset": Quantity.parse("1.5 m"), **_SPAN, **_SECTION},
    ),
    (beam.simply_supported_uniform_load, {**_UDL, **_SPAN, **_SECTION}),
    (beam.simply_supported_partial_uniform_load, {**_UDL, **_PATCH, **_SPAN, **_SECTION}),
    (beam.simply_supported_center_patch_load, {**_UDL, **_PATCH, **_SPAN, **_SECTION}),
    (beam.simply_supported_triangular_load, {**_TRIANGLE, **_SPAN, **_SECTION}),
    (beam.simply_supported_end_moment, {**_COUPLE, **_SPAN, **_SECTION}),
    (beam.simply_supported_offset_moment, {**_COUPLE, **_OFFSET, **_SPAN, **_SECTION}),
    (beam.fixed_pinned_center_load, {**_FORCE, **_SPAN, **_SECTION}),
    (beam.fixed_pinned_offset_load, {**_FORCE, **_OFFSET, **_SPAN, **_SECTION}),
    (beam.fixed_pinned_uniform_load, {**_UDL, **_SPAN, **_SECTION}),
    (beam.fixed_pinned_partial_uniform_load, {**_UDL, **_PATCH, **_SPAN, **_SECTION}),
    (beam.fixed_pinned_center_patch_load, {**_UDL, **_PATCH, **_SPAN, **_SECTION}),
    (beam.fixed_pinned_triangular_load, {**_TRIANGLE, **_SPAN, **_SECTION}),
    (beam.fixed_pinned_triangular_load_peak_at_prop, {**_TRIANGLE, **_SPAN, **_SECTION}),
    (beam.fixed_pinned_end_moment, {**_COUPLE, **_SPAN, **_SECTION}),
    (
        beam.overhang_tip_load,
        {
            **_FORCE,
            "back_span": Quantity.parse("4 m"),
            "overhang": Quantity.parse("1.5 m"),
            **_SECTION,
        },
    ),
    (
        beam.overhang_uniform_load,
        {
            **_UDL,
            "back_span": Quantity.parse("4 m"),
            "overhang": Quantity.parse("1.5 m"),
            **_SECTION,
        },
    ),
    (beam.fixed_fixed_center_load, {**_FORCE, **_SPAN, **_SECTION}),
    (beam.fixed_fixed_offset_load, {**_FORCE, **_OFFSET, **_SPAN, **_SECTION}),
    (beam.fixed_fixed_uniform_load, {**_UDL, **_SPAN, **_SECTION}),
    (beam.fixed_fixed_partial_uniform_load, {**_UDL, **_PATCH, **_SPAN, **_SECTION}),
    (beam.fixed_fixed_center_patch_load, {**_UDL, **_PATCH, **_SPAN, **_SECTION}),
    (beam.fixed_fixed_triangular_load, {**_TRIANGLE, **_SPAN, **_SECTION}),
]


def test_the_case_table_covers_every_load_case_in_the_module():
    """Without this the file proves whatever the table happens to list.

    A new load case added to `beam` with a wrong formula string is exactly the failure this
    file exists to catch, and it would be caught by nothing if the table were allowed to
    fall behind the module.
    """
    import inspect

    returns_a_result = {
        name
        for name, function in vars(beam).items()
        if inspect.isfunction(function)
        and not name.startswith("_")
        and inspect.signature(function).return_annotation == "BeamBendingResult"
    }
    listed = {function.__name__ for function, _ in _CASES}
    assert returns_a_result - listed == set(), (
        "these load cases return a BeamBendingResult and are not in the table: "
        f"{sorted(returns_a_result - listed)}"
    )
    assert len(listed) == len(_CASES), "a load case is listed twice"


@pytest.mark.parametrize(
    ("function", "arguments"),
    [pytest.param(f, a, id=f.__name__) for f, a in _CASES],
)
def test_a_declared_formula_evaluates_to_the_deflection_it_ships_with(function, arguments):
    result = function(**arguments)
    if result.deflection_formula is None:
        pytest.skip("declares no closed form")
    values = {item.symbol: _si(item.value) for item in result.deflection_inputs}
    computed = _arithmetic(result.deflection_formula, values)
    expected = result.max_deflection.pint.to_base_units().magnitude
    assert computed == pytest.approx(expected, rel=1e-9), (
        f"{function.__name__} declares {result.deflection_formula!r}, which evaluates to "
        f"{computed * 1000:.6g} mm; it returned {expected * 1000:.6g} mm"
    )


def test_the_evaluator_notices_a_formula_that_is_merely_plausible():
    """The gate's own gate. An evaluator that returned the answer it was checking, or that
    swallowed what it could not parse, would pass every case above for ever.
    """
    values = {"F": 12000.0, "L": 4.0, "E": 2e11, "I": 2.4e-5}
    right = _arithmetic("δ = F·L³/(3·E·I)", values)
    assert right == pytest.approx(12000.0 * 4.0**3 / (3 * 2e11 * 2.4e-5))
    # The transposition this file exists to catch: one character in the exponent.
    assert _arithmetic("δ = F·L⁴/(3·E·I)", values) != pytest.approx(right)
    # And a coefficient off by one.
    assert _arithmetic("δ = F·L³/(4·E·I)", values) != pytest.approx(right)

    with pytest.raises(AssertionError, match="names symbols nothing declared"):
        _arithmetic("δ = F·a·L³/(3·E·I)", values)
    with pytest.raises(AssertionError, match="cannot read"):
        _arithmetic("δ = F·L³/(3·E·I) ± 0", values)
