"""T1 rainflow cycle counting of a load history, open or repeating (ASTM E1049 practice).

Fatigue damage is summed over cycles, and a measured history is not made of cycles: it is
a sequence of reversals of every size, nested inside each other. Rainflow counting pairs
them into closed hysteresis loops — the cycles a material actually experiences — with the
three-point rule of ASTM E1049-85 §5.4.4: with X the range being read and Y the range
before it, a cycle is counted when X ≥ Y, and Y is removed.

Two forms, because a history is used two ways:

- **Repeating** (a block applied again and again — a flight, a lap, a duty cycle). The
  history is re-ordered to start and end at its most extreme point, and every count is a
  full cycle. This is the procedure of NASA CR-181942 (Khosrovaneh and Dowling, 1989,
  Appendix A, "consistent with the ASTM Standard E1049"), and its worked example — the
  E1049 history −2, 1, −3, 5, −1, 3, −4, 4, −2 — is what the tests reproduce: ranges 4, 3,
  7 and 9, one cycle each.
- **Open** (a history applied once). Counting starts at the first point; a range that
  contains it is counted as a half cycle and the starting point discarded, and whatever
  remains unpaired at the end — the residual — is counted as half cycles. No public
  primary document works this form numerically; the tests hold it to its invariants and to
  the published reference implementations' result for the same history.

The input is reduced to its reversals first: a point that continues the direction of the
one before it is not a peak or a valley, and neither is a repeat. Means are (peak +
valley)/2. Damage over counted cycles is :func:`~anvilate.analysis.fatigue.miner_cumulative_damage`.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from .._models import each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "RainflowCycle",
    "RainflowCount",
    "rainflow_count",
]

_HISTORY_SOURCE = "the measured or declared load, stress or strain history"


class _RainflowInputError(RefusalError, ValueError):
    """A rainflow input that cannot be used without correction."""


def _refusal(message: str, *, subject: str) -> _RainflowInputError:
    return _RainflowInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=_HISTORY_SOURCE),)
    )


class RainflowCycle(BaseModel):
    """One counted cycle (count 1.0) or half cycle (0.5), in the history's unit (ASTM E1049)."""

    model_config = ConfigDict(frozen=True)

    range: float
    mean: float
    count: float


class RainflowCount(BaseModel):
    """The cycles of a history by rainflow (ASTM E1049 §5.4.4), and what was left unpaired.

    ``residual`` is the reversal sequence left at the end of an open count, whose ranges
    are the half cycles at the end of ``cycles``; a repeating count closes on itself and
    leaves only its starting extreme. ``unit`` is the unit every value is in, and
    ``reversals`` how many peaks and valleys the history reduced to.
    """

    model_config = ConfigDict(frozen=True)

    cycles: tuple[RainflowCycle, ...]
    residual: tuple[float, ...]
    repeating: bool
    unit: str
    reversals: int

    @property
    def total_cycles(self) -> float:
        """Full cycles plus half the half cycles."""
        return sum(c.count for c in self.cycles)

    def histogram(self) -> tuple[tuple[float, float], ...]:
        """(range, cycles) pairs, merged by range, largest range first."""
        merged: dict[float, float] = {}
        for c in self.cycles:
            merged[c.range] = merged.get(c.range, 0.0) + c.count
        return tuple(sorted(merged.items(), key=lambda pair: -pair[0]))

    def __str__(self) -> str:
        kind = "repeating" if self.repeating else "open"
        rows = ", ".join(f"{r:g} {self.unit} × {n:g}" for r, n in self.histogram())
        tail = "" if self.repeating else f"; residual {list(self.residual)}"
        return f"rainflow ({kind}, ASTM E1049): {self.total_cycles:g} cycles — {rows}{tail}"


def _reversals(points: list[float]) -> list[float]:
    out: list[float] = []
    for x in points:
        if out and x == out[-1]:
            continue
        if len(out) >= 2 and (out[-1] - out[-2]) * (x - out[-1]) > 0:
            out[-1] = x
            continue
        out.append(x)
    return out


def _count(points: list[float], *, open_history: bool) -> tuple[list[RainflowCycle], list[float]]:
    stack: list[float] = []
    cycles: list[RainflowCycle] = []
    for p in points:
        stack.append(p)
        while len(stack) >= 3:
            x = abs(stack[-1] - stack[-2])
            y = abs(stack[-2] - stack[-3])
            if x < y:
                break
            if open_history and len(stack) == 3:
                # Y contains the starting point S: a half cycle, and S is discarded.
                cycles.append(RainflowCycle(range=y, mean=(stack[0] + stack[1]) / 2, count=0.5))
                stack.pop(0)
            else:
                a, b = stack[-3], stack[-2]
                cycles.append(RainflowCycle(range=y, mean=(a + b) / 2, count=1.0))
                del stack[-3:-1]
    if open_history:
        cycles += [
            RainflowCycle(range=abs(b - a), mean=(a + b) / 2, count=0.5)
            for a, b in zip(stack, stack[1:], strict=False)
        ]
    return cycles, stack


def rainflow_count(history: Sequence[Quantity], *, repeating: bool) -> RainflowCount:
    """Count a history's cycles by rainflow (ASTM E1049 §5.4.4; NASA CR-181942 App. A).

    ``history`` is a sequence of loads, stresses or strains, all of one dimension, read in
    the first value's unit. ``repeating`` declares whether the history is a block applied
    again and again (counted from its most extreme point, full cycles only) or applied
    once (counted from its start, with half cycles and a residual). A history of fewer
    than two reversals has nothing to count and is refused.
    """
    values = each_one(history, Quantity, named="history")
    if not isinstance(repeating, bool):
        raise _refusal("repeating is True for a block applied again and again, False for "
                       "a history applied once", subject="repeating")  # fmt: skip
    if not values:
        raise _refusal("history is empty", subject="history")
    unit = str(values[0].unit)
    points = []
    for i, v in enumerate(values):
        try:
            converted = v.to(unit).magnitude
        except Exception as error:
            raise _refusal(f"history[{i}] is {v}, which is not in the dimension of {values[0]}",
                           subject="history") from error  # fmt: skip
        points.append(require_finite(converted, name=f"history[{i}]"))
    reversals = _reversals(points)
    if len(reversals) < 2:
        raise _refusal("history has fewer than two reversals, so it has no range to count",
                       subject="history")  # fmt: skip
    if repeating:
        # A history that ends where it began is closed already: drop the repeat, then
        # start the block at its most extreme point and close it there (CR-181942 Fig. A.1).
        body = reversals[:-1] if reversals[0] == reversals[-1] else reversals
        start = max(range(len(body)), key=lambda k: abs(body[k]))
        rotated = body[start:] + body[:start] + [body[start]]
        cycles, residual = _count(_reversals(rotated), open_history=False)
    else:
        cycles, residual = _count(reversals, open_history=True)
    return RainflowCount(cycles=tuple(cycles), residual=tuple(residual), repeating=repeating,
                         unit=unit, reversals=len(reversals))  # fmt: skip
