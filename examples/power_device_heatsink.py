"""Worked example: the junction a fan saves and still air cooks.

A power MOSFET dissipating 30 W has to get that heat from its silicon junction out
to the air, and every step of the path resists the flow. Datasheet junction-to-case
resistance, a thermal-interface pad, and the heat sink's convection to air sit in
series like resistors, and the junction-to-ambient temperature rise is the heat flow
times the total resistance — ΔT = Q·R. Add the rise to the ambient and compare
against the junction's rated limit.

With the sink in still air (natural convection, h ≈ 8 W/m²·K) the sink resistance
dominates the chain and the rise runs past 140 K — the junction blows through its
85 K allowable (125 °C rated over a 40 °C ambient) and the part cooks. Nothing about
the silicon changed; the exit path is the bottleneck. Put a fan on it (forced
convection, h ≈ 40 W/m²·K) and the sink resistance drops five-fold, the rise falls to
about 45 K, and the junction sits comfortably inside its limit.

The lesson is that a thermal design is a resistance network, and the governing
resistance is usually the last one — the convection to air. Anvilate does the network
algebra and the rise; the convection coefficient is the engineer's input, from a
correlation or the fan curve, not something a screen invents. Run it directly
(``python examples/power_device_heatsink.py``); :func:`screen_cooling` is exercised
in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    conduction_thermal_resistance,
    convection_thermal_resistance,
    series_thermal_resistance,
    temperature_rise,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

DISSIPATION = Quantity.parse("30 W")
# The allowable junction-to-ambient rise: 125 °C rated junction over a 40 °C ambient.
ALLOWABLE_RISE_K = 85.0
REQUIRED_SF = 1.25

# The fixed part of the path (datasheet + interface), independent of the cooling.
R_JUNCTION_TO_CASE = Quantity(magnitude=0.5, unit="K/W")  # from the MOSFET datasheet
SINK_AREA = Quantity.parse("0.03 m**2")

NATURAL_CONVECTION = Quantity.parse("8 W/(m**2*K)")  # still air
FORCED_CONVECTION = Quantity.parse("40 W/(m**2*K)")  # a fan over the sink


def _junction_rise(sink_coefficient: Quantity) -> Quantity:
    r_pad = conduction_thermal_resistance(
        thickness=Quantity.parse("0.3 mm"),
        area=Quantity.parse("400 mm**2"),
        conductivity=Quantity.parse("5 W/(m*K)"),  # a filled thermal pad
    )
    r_sink = convection_thermal_resistance(
        area=SINK_AREA, heat_transfer_coefficient=sink_coefficient
    )
    total = series_thermal_resistance(R_JUNCTION_TO_CASE, r_pad, r_sink)
    return temperature_rise(power=DISSIPATION, thermal_resistance=total)


def screen_cooling(sink_coefficient: Quantity) -> Scorecard:
    """Screen the junction rise against the allowable, for a cooling condition.

    The safety factor is the allowable rise over the computed rise.
    """
    rise = _junction_rise(sink_coefficient).to("K").magnitude
    safety = float("inf") if rise == 0 else ALLOWABLE_RISE_K / rise
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "junction temperature rise", computed=safety, required=REQUIRED_SF
            ),
        )
    )


def screen_natural_convection() -> Scorecard:
    """Still air: the junction cooks."""
    return screen_cooling(NATURAL_CONVECTION)


def screen_forced_convection() -> Scorecard:
    """A fan over the sink: the junction sits inside its limit."""
    return screen_cooling(FORCED_CONVECTION)


def main() -> None:
    for label, h in (("still air", NATURAL_CONVECTION), ("forced air (fan)", FORCED_CONVECTION)):
        rise = _junction_rise(h).to("K").magnitude
        print(f"{label}: junction rise {rise:.0f} K (allowable {ALLOWABLE_RISE_K:.0f} K)")
        print(f"  {screen_cooling(h).entries[0]}")


if __name__ == "__main__":
    main()
