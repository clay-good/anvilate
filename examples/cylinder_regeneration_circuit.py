"""Worked example: the regeneration circuit that makes a press rush in, then lean on the work.

A hydraulic press wants two different things from one cylinder: get to the workpiece fast, then push
through it hard. A regeneration (differential) circuit gives the first by plumbing the rod-side oil
back to join the pump flow on the cap side, so the pump only fills the rod's own cross-section — the
piston rushes out at roughly (bore/rod)² times its normal speed. The catch is that supply pressure
now acts on both faces of the piston, so the net thrust collapses to pressure times the rod area:
fast but weak.

This example runs a 100 mm bore / 70 mm rod cylinder at 200 bar on 40 L/min. In regeneration the rod
extends at ~173 mm/s but musters only ~77 kN; switched to a normal extend it slows to ~85 mm/s but
delivers the full ~157 kN. A press that must overcome, say, a 120 kN forming load simply cannot do
it in regeneration — the circuit is for the free-travel approach, and the valve must shift to a full
cap feed before the tool touches the work. The lesson is that regeneration buys stroke *speed* by
spending stroke *force*, and the two modes are sized for different halves of the same cycle.

Run it directly (``python examples/cylinder_regeneration_circuit.py``);
:func:`extend_modes` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    cylinder_extend_force,
    cylinder_extend_speed,
    cylinder_regen_extend_force,
    cylinder_regen_extend_speed,
)
from anvilate.units import Quantity

PRESSURE = Quantity.parse("200 bar")
BORE = Quantity.parse("100 mm")
ROD = Quantity.parse("70 mm")
FLOW = Quantity.parse("40 L/min")
FORMING_LOAD = Quantity.parse("120 kN")


def extend_modes() -> dict[str, float]:
    """Return the force (kN) and speed (mm/s) of the normal and regenerative extend strokes."""
    normal_f = cylinder_extend_force(pressure=PRESSURE, bore_diameter=BORE).to("kN").magnitude
    normal_v = cylinder_extend_speed(flow_rate=FLOW, bore_diameter=BORE).to("mm/s").magnitude
    regen_f = (
        cylinder_regen_extend_force(pressure=PRESSURE, rod_diameter=ROD, bore_diameter=BORE)
        .to("kN")
        .magnitude
    )
    regen_v = (
        cylinder_regen_extend_speed(flow_rate=FLOW, rod_diameter=ROD, bore_diameter=BORE)
        .to("mm/s")
        .magnitude
    )
    return {
        "normal_force_kn": normal_f,
        "normal_speed_mms": normal_v,
        "regen_force_kn": regen_f,
        "regen_speed_mms": regen_v,
    }


def main() -> None:
    m = extend_modes()
    load = FORMING_LOAD.to("kN").magnitude
    print(f"normal extend : {m['normal_force_kn']:.0f} kN at {m['normal_speed_mms']:.0f} mm/s")
    print(f"regeneration  : {m['regen_force_kn']:.0f} kN at {m['regen_speed_mms']:.0f} mm/s")
    print(f"forming load  : {load:.0f} kN")
    regen_ok = "can push it" if m["regen_force_kn"] >= load else "cannot push it"
    normal_ok = "can push it" if m["normal_force_kn"] >= load else "cannot push it"
    print(f"  -> regeneration {regen_ok}; normal extend {normal_ok}")
    print("  -> rush in on regeneration, then shift to a full cap feed to press")


if __name__ == "__main__":
    main()
