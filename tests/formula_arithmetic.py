"""Substitute a declared symbolic formula and evaluate it, so a string can be checked.

A formula written beside a number the code computed is code duplicated in prose: the value
comes from the function and the expression comes from a person, and nothing holds them
together. `tests/test_beam_deflection_formulas.py` and `tests/test_plate_formulas.py` both
read their formulas back through this, so the two cannot check the same thing two ways.

The evaluator refuses what it cannot read — an undeclared symbol, an unmapped character —
rather than skipping it. A lenient one passes every formula for ever.
"""

from __future__ import annotations

import re

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
    expression = _radicals_over_groups(expression)

    unreadable = sorted(set(expression) - set("0123456789.+-*/() e"))
    assert not unreadable, f"the evaluator cannot read {unreadable} in {symbolic!r}"
    return eval(expression, {"__builtins__": {}}, {})  # noqa: S307 - a closed arithmetic string


def _radicals_over_groups(expression: str) -> str:
    """``√(...)`` rewritten as ``(...)**0.5``, matching the bracket the radical covers.

    A regex cannot do this: the group a radical covers may hold brackets of its own, and
    `√((L**2 - b**2)**3)` is the shape the three-halves powers in this module are written
    in. Scanning for the balance point is the whole of it.
    """
    while (start := expression.find("√(")) != -1:
        depth = 0
        for index in range(start + 1, len(expression)):
            if expression[index] == "(":
                depth += 1
            elif expression[index] == ")":
                depth -= 1
                if depth == 0:
                    inner = expression[start + 1 : index + 1]
                    expression = f"{expression[:start]}({inner}**0.5){expression[index + 1 :]}"
                    break
        else:  # pragma: no cover - an unbalanced formula is a typo, not a case
            raise AssertionError(f"unbalanced √( in {expression!r}")
    return expression


def _si(value) -> float:
    """A declared symbol's value as a bare number in SI base units.

    Every symbol in one formula has to be reduced by the same rule or the arithmetic is
    meaningless — a length in mm beside a modulus in GPa evaluates to a number with no
    relation to the answer. A dimensionless input passes through.
    """
    if isinstance(value, Quantity):
        return float(value.pint.to_base_units().magnitude)
    return float(value)
