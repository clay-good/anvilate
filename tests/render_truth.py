"""Evaluate a `Derivation`'s substituted line and compare it with the result printed under it.

A formula written beside a number the code computed is code duplicated in prose. The check
that holds the two together lived inside `tests/test_contract.py`, where it ran over a
hand-written sample of cards — and a gate whose subject is a list somebody maintains is
narrower than the library it audits by exactly however much the list has fallen behind.

So the mechanism is here, where both readers can have it: the sample-based test in
`test_contract.py`, which is what an author runs while writing one screen, and the
session-wide sweep in `conftest.py`, which reads the same collector the derivation-coverage
and effectivity ratchets read and therefore covers every entry the whole suite produced.

The evaluator refuses what it cannot read rather than skipping it. Both refusals are
findings and neither is silent: a line that will not PARSE and a line that parses into a
different DIMENSION than the result printed under it are the two ways a substituted formula
can be wrong without being visibly wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_UNIT_TOKEN = r"[A-Za-zµΩ%][A-Za-z0-9_]*(?:\*\*\d+(?:\.\d+)?)?"
# A compound unit is one token, not the first of several: "20.83 kN*m" and "5.2 kg/m**3"
# have to be captured whole, or the tail migrates out of the parentheses and lands in
# whatever operator follows.
VALUE_UNIT = re.compile(
    r"(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s+(" + _UNIT_TOKEN + r"(?:\s*[*/]\s*" + _UNIT_TOKEN + r")*)"
)

_LEADING_NUMBER = re.compile(r"(-?\d+\.?\d*(?:[eE][-+]?\d+)?)")

_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⋅", "0123456789.")


def superscript_exponents(expression: str) -> str:
    """``MPa⁰⋅⁵`` as ``MPa**0.5``, so a fractional-power unit survives the parse.

    The three whole-number superscripts were replaced one glyph at a time, which reads a
    unit's exponent and a symbol's identically and is right for both. A FRACTIONAL exponent
    is not one glyph: ``⁰⋅⁵`` is three, and the value-unit pattern captured
    ``190.27 MPa`` and left the exponent standing outside the parentheses. The line then
    parsed cleanly into the wrong dimension and was dropped by the conversion, which used to
    be silent — an elastic coefficient in √MPa went unchecked in both unit systems while
    the gate cleared its floor.
    """
    return re.sub(
        r"([A-Za-zµΩ])([⁰¹²³⁴-⁹⋅]+)",
        lambda found: found.group(1) + "**" + found.group(2).translate(_SUPERSCRIPT),
        expression,
    )


_BARE_RADICAL = re.compile(r"√(\d+(?:\.\d+)?)")
# `min` and `max` are word operators in a formula and UNITS to pint — it reads `min(1, x)`
# as one minute times a group — so a line using one came back in [time] and the conversion
# to the printed dimensionless result failed. `anvilate.derivation` declares them as
# operators for exactly this reason; the evaluator has to know the same thing.
_WORD_CALL = re.compile(r"\b(min|max)\s*\(")


def _word_operators(expression: str) -> str:
    """``min(1, x)`` evaluated, so a line that uses one is not read as a minute.

    Only the two the renderer declares, and only in call position: a bare `min` is still a
    unit, and this must not start rewriting a symbol that merely contains those letters.
    """
    while (found := _WORD_CALL.search(expression)) is not None:
        depth = 0
        for i in range(found.end() - 1, len(expression)):
            if expression[i] == "(":
                depth += 1
            elif expression[i] == ")":
                depth -= 1
                if depth == 0:
                    parts = _split_top_level(expression[found.end() : i])
                    if len(parts) < 2:
                        return expression
                    rebuilt = parts[0]
                    for part in parts[1:]:
                        # pint has no min/max, so the choice is made arithmetically: the
                        # smaller of a and b is (a + b - |a - b|)/2.
                        sign = "-" if found.group(1) == "min" else "+"
                        rebuilt = (
                            f"(({rebuilt}) + ({part}) {sign} ((({rebuilt}) - ({part}))**2)**0.5)/2"
                        )
                    expression = expression[: found.start()] + f"({rebuilt})" + expression[i + 1 :]
                    break
        else:  # pragma: no cover - an unbalanced call is not a line we build
            return expression
    return expression


def _split_top_level(text: str) -> list[str]:
    """``text`` split on commas that are not inside parentheses."""
    parts, depth, start = [], 0, 0
    for i, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def expand_roots(expression: str) -> str:
    """Rewrite every √(...) in a substituted line as (...)**0.5, matching parentheses.

    Without this, pint parses "√(A₂/A₁)" by quietly discarding the radical and
    using the ratio itself — so a line with a square root in it evaluated to the wrong number
    and the gate compared that wrong number against the printed result. It happened to agree
    often enough to look fine, which is the worst way for a checker to be broken.
    """
    # A radical over a bare number — `9·√3` in the three-point-bending deflection — is not
    # a group, so the parenthesis walk below never sees it. pint then DROPPED the glyph and
    # used the 3, which is a denominator of 27 where 15.59 belongs: every deflection line in
    # this library evaluated 1.73x low, and the sample-based gate never held one.
    expression = _BARE_RADICAL.sub(r"((\1)**0.5)", expression)
    while (start := expression.find("√(")) != -1:
        depth = 0
        for i in range(start + 1, len(expression)):
            if expression[i] == "(":
                depth += 1
            elif expression[i] == ")":
                depth -= 1
                if depth == 0:
                    inner = expression[start + 2 : i]
                    expression = f"{expression[:start]}(({inner})**0.5){expression[i + 1 :]}"
                    break
        else:  # pragma: no cover - an unbalanced radical is not a derivation we build
            return expression.replace("√", "", 1)
    return expression


@dataclass(frozen=True)
class Reading:
    """One substituted line, read.

    ``problem`` is set when the line could not be read at all — it did not parse, or it
    parsed into a dimension the printed result cannot be expressed in. ``value`` and
    ``expected`` are set when it could, and the caller compares them.
    """

    substituted: str
    problem: str | None = None
    value: float | None = None
    expected: float | None = None


def read_line(derivation: object, system: object) -> Reading | None:
    """``derivation``'s substituted line under ``system``, evaluated, or ``None`` to skip.

    ``None`` — and only ``None`` — is a legitimate skip: a derivation that names a symbol it
    never declares renders as unworked and has no substituted arithmetic to check, and a
    result printed without a leading number is not a quantity to compare against.
    """
    from anvilate.units.registry import UREG

    if derivation.unresolved_symbols():
        return None
    substituted = derivation.substituted(system=system)
    _, _, rhs = substituted.partition(" = ")
    expression = rhs.replace("·", "*").replace("−", "-")
    # A unit's fractional exponent first, while its glyphs are still adjacent.
    expression = superscript_exponents(expression)
    expression = expression.replace("²", "**2").replace("³", "**3")
    expression = expression.replace("⁴", "**4")
    expression = expand_roots(expression)
    expression = _word_operators(expression)
    # Pint binds a bare "/ 4166666.67 mm**4" as a division by the NUMBER times the unit, so
    # each value-unit pair has to be parenthesised before parsing.
    expression = VALUE_UNIT.sub(r"(\1 \2)", expression)
    try:
        value = UREG.parse_expression(expression)
    except Exception as exc:  # noqa: BLE001 - any refusal is the finding
        return Reading(substituted, problem=f"does not parse ({exc})")
    printed = derivation.result.rendered(system=system)
    match = _LEADING_NUMBER.match(printed)
    if match is None:
        return None
    unit = printed[match.end() :].strip().replace("·", "*")
    try:
        actual = value.to(UREG.Unit(unit)).magnitude
    except Exception as exc:  # noqa: BLE001 - a wrong dimension is the finding
        return Reading(
            substituted,
            problem=f"printed in {unit}, line is {value.units} ({exc})",
        )
    return Reading(substituted, value=float(actual), expected=float(match.group(1)))


_NUMBER = re.compile(r"-?\d+\.\d+")
# A parenthesised quantity carrying an exponent: `(0.157 in)³`, `(40.00 mm)**3`, `(2.5)^2`.
# Matching the number and its unit separately is what this must NOT do — a greedy unit run
# walks straight past the next factor and attaches the exponent to the wrong number.
_POWERED = re.compile(r"\((-?\d+\.\d+)[^()]*\)\s*(?:\*\*|\^)?\s*([⁰¹²³⁴-⁹]+|\d+(?:\.\d+)?)")

_SUPERSCRIPT_ONLY = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def _relative_half_place(number: str) -> float:
    """Half the last printed place of ``number``, relative to the number itself."""
    value = abs(float(number))
    if value == 0.0:
        return 0.0
    return 0.5 * 10.0 ** -len(number.partition(".")[2]) / value


def _rounding_slack(substituted: str) -> float:
    """How far the line's own printed inputs can move the answer, as a fraction.

    The tolerance used to be a flat 1%, described as "the result's last place plus slack for
    the inputs' own rounding" — and it was not that, it was a guess that happened to cover
    the corpus. A line that CUBES a printed length does not stay inside it: a 4 mm wire
    prints as `0.157 in`, three significant figures, and cubed that is a 1% error on its own
    before anything else in the line rounds. A gate whose tolerance ignores the exponents in
    the line it is reading either misses a real defect on a linear line or reports one on a
    cubed line, and this repository met the second the day a spring shipped.

    So the slack is read off the line: every printed decimal contributes half its last place
    relative to itself, and a parenthesised quantity under an exponent contributes that many
    times over. A whole number is a coefficient — the 8 in `8·F·D` — and has no last place.
    """
    slack = sum(_relative_half_place(number) for number in _NUMBER.findall(substituted))
    for number, exponent in _POWERED.findall(substituted):
        power = float(exponent.translate(_SUPERSCRIPT_ONLY))
        slack += (power - 1.0) * _relative_half_place(number)
    return slack


def disagrees(reading: Reading) -> bool:
    """Whether the line and the number printed under it are further apart than rounding.

    The printed result carries its own precision and each printed input carries its own, and
    an exponent multiplies the second. The floor of 1% is kept because it covers the result
    itself and every line whose inputs are printed generously.
    """
    if reading.value is None or reading.expected is None:
        return False
    tolerance = max(abs(reading.expected) * max(0.01, _rounding_slack(reading.substituted)), 5e-4)
    return abs(reading.value - reading.expected) > tolerance
