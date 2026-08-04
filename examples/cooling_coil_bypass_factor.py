"""Worked example: why a shallow cooling coil can't reach a low supply temperature.

A cooling coil never brings all the air to its cold fin surface — some of the stream slips through
almost untouched, as if it bypassed the coil. How much slips through is the bypass factor, measured
against the coil's apparent dew point (the effective fin temperature the leaving air approaches):
BF = (t_leaving − t_ADP)/(t_entering − t_ADP). A deep, many-row coil grabs nearly all the air and
leaves close to its dew point; a shallow, fast coil lets more bypass and leaves warmer.

This example runs the same 27 °C entering air over two coils with the same 11 °C apparent dew point.
The deep six-row coil leaves the air at 12.5 °C — a bypass factor of 0.09, so 91% of the air made
real contact with the fins and the supply is nearly as cold as the coil. The shallow two-row coil at
the same face condition leaves the air at 17 °C — a bypass factor of 0.375, a full 37% of the air
bypassing, and a supply temperature four and a half degrees warmer. Same air, same dew point; the
only difference is how many rows the air has to cross. The lesson is that the bypass factor, set by
the coil's depth and face velocity, is what fixes how close the supply air can get to the coil — and
a shallow coil simply cannot deliver a cold supply, however cold its dew point.

Run it directly (``python examples/cooling_coil_bypass_factor.py``);
:func:`coil_factors` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import coil_bypass_factor
from anvilate.units import Quantity

ENTERING = Quantity(magnitude=27.0, unit="degC")
APPARENT_DEW_POINT = Quantity(magnitude=11.0, unit="degC")
DEEP_COIL_LEAVING = Quantity(magnitude=12.5, unit="degC")
SHALLOW_COIL_LEAVING = Quantity(magnitude=17.0, unit="degC")


def coil_factors() -> dict[str, float]:
    """Return the bypass factor of a deep and a shallow coil at the same face condition."""
    deep = coil_bypass_factor(
        entering_temperature=ENTERING,
        leaving_temperature=DEEP_COIL_LEAVING,
        apparent_dew_point=APPARENT_DEW_POINT,
    )
    shallow = coil_bypass_factor(
        entering_temperature=ENTERING,
        leaving_temperature=SHALLOW_COIL_LEAVING,
        apparent_dew_point=APPARENT_DEW_POINT,
    )
    return {"deep_bf": deep, "shallow_bf": shallow}


def main() -> None:
    c = coil_factors()
    deep_c = 1 - c["deep_bf"]
    shallow_c = 1 - c["shallow_bf"]
    print(f"deep coil    : leaves 12.5 C -> BF {c['deep_bf']:.2f} (contact {deep_c:.0%})")
    print(f"shallow coil : leaves 17.0 C -> BF {c['shallow_bf']:.2f} (contact {shallow_c:.0%})")
    print(
        "  -> the shallow coil's high bypass factor keeps its supply air warm at the same dew point"
    )


if __name__ == "__main__":
    main()
