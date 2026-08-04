"""Worked example: a spread footing declared once, screened into a bearing scorecard.

This is the geotechnical pack's version of the whole-vertical checks the structural and industrial
packs do: declare a footing and its soil once, and get back a scorecard — not a raw number — with
the bearing-capacity check named, cited, and either PASS or FAIL with no silent green. Under the
hood it builds the full shape- and depth-corrected Terzaghi capacity for the real embedded square
footing and screens it against the applied pressure at the usual factor of safety of 3. This
example takes a 2.5 m square footing 1.5 m deep on a c-φ soil and screens it at two service loads:
5000 kN passes comfortably, while 7000 kN pushes the safety factor below 3 and the scorecard
reports FAIL. The point is the same as everywhere else in the library — the answer arrives as a
reviewable, cited pass/fail, not a bare margin the reader has to judge for themselves.

Run it directly (``python examples/spread_footing_scorecard.py``);
:func:`footing_scorecards` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.geotechnical import ShallowFooting, screen_shallow_footing
from anvilate.units import Quantity


def _footing(load: Quantity) -> ShallowFooting:
    return ShallowFooting(
        width=Quantity.parse("2.5 m"),
        length=Quantity.parse("2.5 m"),
        embedment_depth=Quantity.parse("1.5 m"),
        applied_load=load,
        friction_angle=30.0,
        cohesion=Quantity.parse("25 kPa"),
        unit_weight=Quantity.parse("18 kN/m**3"),
    )


def footing_scorecards() -> dict[str, str]:
    """Return the scorecard status string for a service and an overloaded footing."""
    service = screen_shallow_footing(_footing(Quantity.parse("5000 kN")))
    overloaded = screen_shallow_footing(_footing(Quantity.parse("7000 kN")))
    return {
        "service_status": service.status.value,
        "service_detail": service.entries[0].detail,
        "overloaded_status": overloaded.status.value,
        "overloaded_detail": overloaded.entries[0].detail,
    }


def main() -> None:
    s = footing_scorecards()
    print(f"5000 kN : {s['service_status'].upper()} — {s['service_detail']}")
    print(f"7000 kN : {s['overloaded_status'].upper()} — {s['overloaded_detail']}")
    print("  -> declare the footing once; the bearing check comes back cited and pass/fail")


if __name__ == "__main__":
    main()
