"""Worked example: sizing a rocket nozzle's expansion by its area ratio, and the two-Mach trap.

A converging-diverging nozzle accelerates gas past the speed of sound only if its bell opens by the
right amount past the sonic throat. The isentropic area ratio A/A* ties the local area to the Mach
number it produces, and this example works it for combustion gas (γ = 1.2). To reach Mach 2 at the
exit the nozzle must open to about 1.9 times the throat area; pushing on to Mach 3 needs a far
larger 6.7 times. The catch the example makes explicit is that each area ratio is shared by *two*
Mach numbers, one subsonic and one supersonic: the same ~1.9 area ratio that gives Mach 2 in the
diverging supersonic branch would instead hold a subsonic flow near Mach 0.33. Which branch a nozzle
runs on is set by its back-pressure, not its geometry — the reason a nozzle can be perfectly shaped
and still not go supersonic if the pressure ratio is wrong.

Run it directly (``python examples/rocket_nozzle_area_ratio.py``);
:func:`nozzle_area_ratios` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import isentropic_area_ratio

HEAT_CAPACITY_RATIO = 1.2  # hot combustion gas


def _ratio(mach: float) -> float:
    return isentropic_area_ratio(mach_number=mach, heat_capacity_ratio=HEAT_CAPACITY_RATIO)


def nozzle_area_ratios() -> dict[str, float]:
    """Return the area ratios for several Mach numbers (combustion gas, γ = 1.2)."""
    return {
        "throat_m1": _ratio(1.0),
        "exit_m2": _ratio(2.0),
        "exit_m3": _ratio(3.0),
        "subsonic_m033": _ratio(0.33),
    }


def main() -> None:
    r = nozzle_area_ratios()
    print(f"throat (M=1)     : A/A* = {r['throat_m1']:.2f}")
    print(f"exit for Mach 2  : A/A* = {r['exit_m2']:.2f}")
    print(f"exit for Mach 3  : A/A* = {r['exit_m3']:.2f} (far larger bell for one more Mach)")
    print(f"subsonic M~0.33  : A/A* = {r['subsonic_m033']:.2f} (about the same ratio as Mach 2)")
    print(
        "  -> the bell sets the area ratio; back-pressure picks the subsonic or supersonic branch"
    )


if __name__ == "__main__":
    main()
