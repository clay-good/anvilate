"""Temperature *differences*, which the dimension check cannot tell from temperatures.

A temperature difference and a point on a temperature scale share a dimensionality, so
``[temperature]`` accepts both and no amount of dimension checking separates them. The
conversion is where they part company: ``5 K`` is a 5 K difference, but ``5 degC`` converts
to 278.15 K, because the Celsius scale carries an offset. Writing a 5 K rise the natural
way — ``Quantity(5, "degC")`` — therefore multiplies it by fifty-five.

The direction is unconservative wherever the difference is an *allowance*. A junction
screened against ``Quantity(85, "degC")`` of allowable rise compares its 120 K rise against
358 K and returns PASS on a genuine overheat; a heat sink sized to the same budget comes out
six times too small. Both read as ordinary engineering input.

:func:`temperature_difference_kelvin` refuses an offset unit outright rather than guessing.
It tests the conversion itself — doubling the magnitude must double the kelvin value — so it
catches every spelling of every offset scale, including ones nobody has thought of yet. A
blacklist of unit names is only ever as complete as the last name someone remembered to add,
which is exactly how ``degree_Fahrenheit`` slipped through an earlier version of this guard.
"""

from __future__ import annotations

from .quantity import Quantity, UnitError

__all__ = [
    "OffsetTemperatureError",
    "temperature_difference_kelvin",
]


class OffsetTemperatureError(UnitError):
    """A temperature *difference* was given on an offset scale such as degC or degF."""


def temperature_difference_kelvin(value: Quantity, *, name: str) -> float:
    """A temperature difference in kelvin, refusing an offset-scale unit.

    Accepts the units that genuinely express a difference — ``K``, ``delta_degC``,
    ``delta_degF``, ``degR`` — and refuses ``degC``/``degF``, whose conversion adds an offset
    and would turn a 5 K rise into 278.15 K. ``name`` is the caller's parameter name, echoed
    in the error so the fix is obvious.
    """
    one = Quantity(magnitude=1.0, unit=value.unit).to("K").magnitude
    two = Quantity(magnitude=2.0, unit=value.unit).to("K").magnitude
    if abs(two - 2.0 * one) > 1.0e-9 * abs(one):
        raise OffsetTemperatureError(
            f"{name} is a temperature DIFFERENCE, not a point on a scale; got {value}, which "
            f"converts to {value.to('K')} because that scale carries an offset. Use 'K', "
            f"'delta_degC', or 'delta_degF'."
        )
    return value.to("K").magnitude
