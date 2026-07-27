"""Capstone: one lead-line tension flows through a whole hoisting system.

A 20 kN workshop hoist chains four subsystems built in this library: a four-part block
and tackle, a head sheave, a 10 mm wire rope, and a winch drum. The naive arithmetic
sizes all of them from W/n = 5 kN. But on plain-bushing sheaves (η = 0.94, one lead
sheave to the winch) the tackle's actual mechanical advantage is 3.43, not 4, and the
lead line carries 5.82 kN -- and *that* number, not 5 kN, is what every downstream
element sees.

Screened against it, most of the chain holds. The rope over the generous 400 mm head
sheave takes 5.81 kN of equivalent bending load on top of the tension and still clears
its design factor of 5 against the 63 kN breaking strength (SF 5.42); the sheave groove
pressure is comfortable (1.37); the drum stores the 20 m of travel with margin (1.07).
Even the 500 N·m winch looks adequate at the bare drum, pulling 5.88 kN (1.01). But the
lift ends with three layers wound on: at a 105 mm working radius the same torque
delivers only 4.76 kN against the 5.82 kN lead line (0.82), and the hoist stalls at the
top -- the one check the W/n arithmetic and the bare-drum rating both missed. A 700 N·m
winch clears it (1.14, bare drum 1.41).

The capstone lesson: in a reeved hoisting system the friction-amplified lead-line
tension is the single number the sheave, the rope, and the winch are all really sized
by -- compute it first, and judge the winch at its fullest drum, because that is where
the lift finishes.

Run it directly (``python examples/workshop_hoist_system.py``);
:func:`screen_hoist_system` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    drum_line_pull,
    drum_rope_capacity,
    tackle_lead_line_tension,
    wire_rope_equivalent_bending_load,
    wire_rope_sheave_pressure,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LOAD = Quantity.parse("20 kN")

# The tackle: four parts on plain-bushing sheaves, one lead sheave to the winch.
SUPPORTING_PARTS = 4
SHEAVE_EFFICIENCY = 0.94
LEAD_SHEAVES = 1

# The rope's datasheet: 10 mm six-strand rope on a 400 mm head sheave.
ROPE_DIAMETER = Quantity.parse("10 mm")
OUTER_WIRE_DIAMETER = Quantity.parse("0.7 mm")
METAL_AREA = Quantity.parse("40 mm**2")
ROPE_MODULUS = Quantity.parse("83 GPa")
BREAKING_STRENGTH = Quantity.parse("63 kN")
ROPE_DESIGN_FACTOR = 5.0
HEAD_SHEAVE_DIAMETER = Quantity.parse("400 mm")
ALLOWABLE_SHEAVE_PRESSURE = Quantity.parse("4 MPa")

# The winch drum: 160 mm core, 12 wraps x 3 layers, 20 m of rope travel.
DRUM_CORE_DIAMETER = Quantity.parse("160 mm")
WRAPS_PER_LAYER = 12
LAYERS = 3
REQUIRED_ROPE = Quantity.parse("20 m")

NAIVE_WINCH_TORQUE = Quantity.parse("500 N*m")  # sized for the W/n = 5 kN estimate
UPGRADED_WINCH_TORQUE = Quantity.parse("700 N*m")


def lead_line_tension() -> Quantity:
    """The friction-amplified lead-line tension the whole chain is sized by."""
    return tackle_lead_line_tension(
        load=LOAD,
        supporting_parts=SUPPORTING_PARTS,
        sheave_efficiency=SHEAVE_EFFICIENCY,
        lead_sheaves=LEAD_SHEAVES,
    )


def _screen(winch_torque: Quantity) -> Scorecard:
    lead = lead_line_tension()
    lead_n = lead.to("N").magnitude
    bending = wire_rope_equivalent_bending_load(
        wire_diameter=OUTER_WIRE_DIAMETER,
        sheave_diameter=HEAD_SHEAVE_DIAMETER,
        rope_modulus=ROPE_MODULUS,
        metal_area=METAL_AREA,
    )
    pressure = wire_rope_sheave_pressure(
        tension=lead,
        rope_diameter=ROPE_DIAMETER,
        sheave_diameter=HEAD_SHEAVE_DIAMETER,
    )
    capacity = drum_rope_capacity(
        core_diameter=DRUM_CORE_DIAMETER,
        rope_diameter=ROPE_DIAMETER,
        wraps_per_layer=WRAPS_PER_LAYER,
        layers=LAYERS,
    )
    pulls = {
        layer: drum_line_pull(
            torque=winch_torque,
            core_diameter=DRUM_CORE_DIAMETER,
            rope_diameter=ROPE_DIAMETER,
            layer=layer,
        )
        for layer in (1, LAYERS)
    }
    breaking_n = BREAKING_STRENGTH.to("N").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "lead line plus sheave bending vs rope strength",
                computed=breaking_n / (lead_n + bending.to("N").magnitude),
                required=ROPE_DESIGN_FACTOR,
            ),
            ScorecardEntry.from_safety_factor(
                "head-sheave groove pressure vs allowable",
                computed=ALLOWABLE_SHEAVE_PRESSURE.to("MPa").magnitude
                / pressure.to("MPa").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "drum rope capacity vs travel",
                computed=capacity.to("m").magnitude / REQUIRED_ROPE.to("m").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "bare-drum line pull vs lead line",
                computed=pulls[1].to("N").magnitude / lead_n,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "full-drum line pull vs lead line",
                computed=pulls[LAYERS].to("N").magnitude / lead_n,
                required=1.0,
            ),
        )
    )


def screen_hoist_system() -> Scorecard:
    """Screen the chain with the winch the W/n arithmetic bought: it stalls full."""
    return _screen(NAIVE_WINCH_TORQUE)


def screen_upgraded_winch() -> Scorecard:
    """Screen the same chain with a 700 N·m winch: the last check clears."""
    return _screen(UPGRADED_WINCH_TORQUE)


def main() -> None:
    lead = lead_line_tension()
    naive = LOAD.to("kN").magnitude / SUPPORTING_PARTS
    print(f"naive lead line W/n: {naive:.2f} kN")
    print(f"actual lead line:    {lead.to('kN').magnitude:.2f} kN")
    print("\nnaive 500 N*m winch:")
    print(screen_hoist_system())
    print("\nupgraded 700 N*m winch:")
    print(screen_upgraded_winch())


if __name__ == "__main__":
    main()
