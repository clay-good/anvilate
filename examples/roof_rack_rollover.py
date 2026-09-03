"""Worked example: the roof rack that tips an SUV on the off-ramp.

A mid-size SUV has a 1.6 m track and a 0.65 m centre-of-gravity height empty, giving a static
stability factor SSF = t/(2h) = 1.23 -- it will not roll until cornering pushes past 1.23 g, well
above what tyres can generate on dry tarmac, so empty it slides long before it tips. Loaded for a
trip, a heavy roof box lifts the whole vehicle's CG to 0.90 m, dropping the SSF to 0.89. Now the
rollover threshold is only 0.89 g. On a 40 m-radius freeway off-ramp taken at 21 m/s (76 km/h) the
lateral acceleration is v^2/R = 1.12 g -- above the loaded threshold. The flat-curve rollover speed
v = sqrt(SSF*g*R) is just 18.7 m/s (67 km/h), so 21 m/s tips it: the inside wheels lift and the
vehicle rolls. The margin is 0.89 -- under one, meaning the manoeuvre is past the tipping point.

The same ramp at the same speed is safe with the roof box removed. Back at h = 0.65 m the SSF is
1.23, the rollover speed climbs to 22.0 m/s (79 km/h), and 21 m/s now sits under it with a 1.05
margin. Nothing about the tyres, the road, or the driver changed -- only the height of the load.

The lesson is that roof loads trade stability, not just fuel economy: raising the centre of gravity
lowers the rollover threshold directly, and a tall vehicle that was grip-limited empty can become
tip-limited loaded. Put the heavy weight low, and keep ramp speeds honest when it has to go high.

Run it directly (``python examples/roof_rack_rollover.py``);
:func:`screen_roof_loaded` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rollover_threshold_speed, static_stability_factor
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

TRACK_WIDTH = Quantity.parse("1.6 m")
EMPTY_CG_HEIGHT = Quantity.parse("0.65 m")
ROOF_LOADED_CG_HEIGHT = Quantity.parse("0.90 m")  # heavy roof box raises the CG
RAMP_RADIUS = Quantity.parse("40 m")
RAMP_SPEED = Quantity.parse("21 m/s")


def _screen(cg_height: Quantity) -> Scorecard:
    ssf = static_stability_factor(track_width=TRACK_WIDTH, center_of_gravity_height=cg_height)
    rollover_speed = rollover_threshold_speed(static_stability_factor=ssf, curve_radius=RAMP_RADIUS)
    margin = rollover_speed.to("m/s").magnitude / RAMP_SPEED.to("m/s").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "rollover speed vs ramp speed",
                computed=margin,
                required=1.0,
            ),
        )
    )


def screen_roof_loaded() -> Scorecard:
    """Screen the roof-loaded SUV: the raised CG drops the rollover speed below ramp speed."""
    return _screen(ROOF_LOADED_CG_HEIGHT)


def screen_empty() -> Scorecard:
    """Screen the empty SUV: the low CG clears the same ramp at the same speed."""
    return _screen(EMPTY_CG_HEIGHT)


def main() -> None:
    print("roof box loaded (CG 0.90 m):")
    print(screen_roof_loaded().report())
    print("\nempty (CG 0.65 m):")
    print(screen_empty().report())


if __name__ == "__main__":
    main()
