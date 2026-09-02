"""Substitute a declared symbolic formula and evaluate it, so a string can be checked.

A formula written beside a number the code computed is code duplicated in prose: the value
comes from the function and the expression comes from a person, and nothing holds them
together. `tests/test_beam_deflection_formulas.py` and `tests/test_plate_formulas.py` both
read their formulas back through this, so the two cannot check the same thing two ways.

The evaluator refuses what it cannot read — an undeclared symbol, an unmapped character —
rather than skipping it. A lenient one passes every formula for ever.
"""

from __future__ import annotations

import math
import re

from anvilate.derivation import _CONSTANTS, _OPERATORS, _scan
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
    # Constants and word-operators are excused for exactly the reasons
    # `Derivation.unresolved_symbols` excuses them, and by reading its own sets rather than
    # a second copy: an evaluator that excused more than the renderer does would pass a
    # formula the report refuses to show as worked.
    missing = sorted(set(leftover) - _CONSTANTS - _OPERATORS)
    assert not missing, f"{symbolic!r} names symbols nothing declared: {missing}"

    expression = substituted
    for glyph, digit in _SUPERSCRIPT_DIGITS.items():
        expression = expression.replace(glyph, f"@{digit}")
    # "(4.0)@3" -> "(4.0)**3"; consecutive superscript digits are one exponent.
    expression = re.sub(r"(?:@(\d))+", lambda m: "**" + m.group(0).replace("@", ""), expression)
    expression = expression.replace("·", "*").replace("−", "-").replace("–", "-")
    # A caret exponent, which is how the AISI and Marin fits are written: an exponent that
    # is not a whole number cannot be a superscript glyph.
    expression = expression.replace("^", "**")
    expression = re.sub(r"√(\d+)", r"(\1**0.5)", expression)
    expression = _radicals_over_groups(expression)
    # π is a constant a formula may name without declaring, exactly as
    # `Derivation.unresolved_symbols` treats it — so the evaluator has to know its value
    # or it would report the one symbol the renderer deliberately leaves standing.
    expression = expression.replace("π", repr(math.pi))

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


def rendered_value(text: str) -> object | None:
    """A rendered value parsed back into something arithmetic, or ``None``.

    The round trip is the point: what the reader sees has to be readable *as* a quantity,
    or the line in front of them is not arithmetic they can follow.
    """
    from anvilate.units import Quantity

    cleaned = text.replace("·", "*").replace("²", "**2").replace("³", "**3").replace("⁴", "**4")
    try:
        return Quantity.parse(cleaned).pint
    except Exception:
        try:
            return float(cleaned)
        except ValueError:
            return None


def evaluates_as_rendered(derivation, system=None) -> tuple[str | None, object, object]:
    """Evaluate a derivation's substituted line *as the reader sees it*.

    `_arithmetic` above reduces every symbol to SI base units, which answers "is the
    formula right". This answers the different question a reviewer asks: does the line
    printed in this document, in the units printed beside each symbol, come to the number
    printed as the result. A unit the report converts for one symbol and not another is
    invisible to the first check and is the whole of the second.

    Returns ``(why_it_could_not_be_checked, got, want)``.
    """
    import math

    _, separator, rhs = derivation.symbolic.partition("=")
    rhs = rhs if separator else derivation.symbolic
    values: dict[str, object] = {}
    by_symbol: dict[str, str] = {}
    for index, item in enumerate(derivation.inputs):
        value = rendered_value(item.rendered(system=system))
        if value is None:
            return f"{item.symbol!r} renders as something no parser reads", None, None
        name = f"_v{index}"
        values[name] = value
        by_symbol[item.symbol] = f"({name})"
    substituted, leftover = _scan(rhs, by_symbol)
    if set(leftover) - _CONSTANTS - _OPERATORS:
        return "the formula names an undeclared symbol", None, None

    expression = substituted
    for glyph, digit in _SUPERSCRIPT_DIGITS.items():
        expression = expression.replace(glyph, f"@{digit}")
    expression = re.sub(r"(?:@(\d))+", lambda m: "**" + m.group(0).replace("@", ""), expression)
    expression = expression.replace("·", "*").replace("−", "-").replace("^", "**")
    expression = re.sub(r"√(\d+)", r"(\1**0.5)", expression)
    expression = _radicals_over_groups(expression)
    expression = expression.replace("π", repr(math.pi))
    try:
        got = eval(  # noqa: S307 - a closed arithmetic string over parsed quantities
            expression, {"__builtins__": {"min": min, "max": max}}, values
        )
    except Exception as exc:  # pragma: no cover - a shape the corpus does not contain
        return f"the line does not evaluate: {type(exc).__name__}", None, None
    want = rendered_value(derivation.result.rendered(system=system))
    if want is None:
        return "the result renders as something no parser reads", None, None
    return None, got, want
