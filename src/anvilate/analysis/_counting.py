"""Whole counts taken from a floating-point ratio.

A count of teeth, bolts or turns is an integer answer to a division, and the division is
done in binary floating point. A design that fits *exactly* — a 6 in workpiece at a 0.5 in
tooth pitch, twelve teeth — does not always divide exactly: 152.4 / 12.7 is
11.999999999999998, and a bare ``floor`` reports eleven teeth in cut. The error is a
representation artefact of the units the caller happened to write, not a fact about the
part: the same design in millimetres and in inches came back with different counts, and in
the broaching case the smaller count *understates* the cutting force the broach carries.

So the whole-count forms snap first. A ratio within a relative 1e-9 of an integer is that
integer, and only a ratio genuinely between two integers is rounded up or down. The
tolerance is deliberately far below any engineering resolution — a real design difference of
one part in a billion does not exist — and far above the few ulps these arithmetic chains
accumulate, so snapping cannot hide a count that truly changed.
"""

from __future__ import annotations

from math import ceil, floor, isclose

__all__: list[str] = []

# Wide enough to absorb the accumulated representation error of a unit conversion and a
# division, narrow enough that no physically distinguishable ratio is snapped across it.
_WHOLE = 1e-9


def _snapped(value: float) -> float | int:
    """``value``, or the integer it is a representation error away from."""
    nearest = round(value)
    if isclose(value, nearest, rel_tol=_WHOLE, abs_tol=1e-12):
        return int(nearest)
    return value


def whole_count_ceil(value: float) -> int:
    """``⌈value⌉``, with a ratio one representation error above an integer taken as it."""
    return ceil(_snapped(value))


def whole_count_floor(value: float) -> int:
    """``⌊value⌋``, with a ratio one representation error below an integer taken as it."""
    return floor(_snapped(value))
