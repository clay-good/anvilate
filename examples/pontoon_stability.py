"""Worked example: the raft that floats fine until you stack the load too high.

A floating platform can carry plenty of weight and still capsize — not because it sinks, but
because it rolls over. Whether it rights itself when it heels is set by the metacentric height
GM: positive and it snaps back upright, negative and it keeps going. GM has two competing parts.
The hull's waterplane shape gives a metacentric radius BM = I/V that resists rolling — wide is
good, which is why rafts are wide and flat. Raising the load lifts the center of gravity and eats
that margin. This example takes a 6 × 3 m pontoon and puts the same load on it at two heights: low
on the deck it is comfortably stable, but stacked high the center of gravity climbs above the
metacenter, GM goes negative, and the raft turns over. The load never changed — only where you put
it.

Run it directly (``python examples/pontoon_stability.py``);
:func:`pontoon_stability` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import buoyant_force, metacentric_height, righting_moment
from anvilate.units import Quantity

LENGTH = Quantity.parse("6 m")
BEAM = Quantity.parse("3 m")
DRAFT = Quantity.parse("0.4 m")  # depth submerged
LOW_CG_HEIGHT = Quantity.parse("1.0 m")  # center of gravity above the keel, load low
HIGH_CG_HEIGHT = Quantity.parse("2.2 m")  # load stacked high
HEEL_ANGLE = 10.0  # degrees


def pontoon_stability() -> dict[str, float]:
    """Return the metacentric height (m) and righting moment (kN·m) for a low and high load."""
    lo = LENGTH.to("m").magnitude
    b = BEAM.to("m").magnitude
    draft = DRAFT.to("m").magnitude
    waterplane_i = Quantity(magnitude=lo * b**3 / 12.0, unit="m**4")  # about the roll (long) axis
    displaced = Quantity(magnitude=lo * b * draft, unit="m**3")
    weight = buoyant_force(displaced_volume=displaced, fluid_density=Quantity.parse("1000 kg/m**3"))
    keel_to_buoyancy = draft / 2.0  # center of buoyancy of a rectangular hull

    def state(cg_height: Quantity) -> tuple[float, float]:
        bg = Quantity(magnitude=cg_height.to("m").magnitude - keel_to_buoyancy, unit="m")
        gm = metacentric_height(
            waterplane_second_moment=waterplane_i,
            displaced_volume=displaced,
            buoyancy_to_gravity_distance=bg,
        )
        gm_m = gm.to("m").magnitude
        if gm_m <= 0:
            return gm_m, 0.0  # unstable — no righting moment
        moment = righting_moment(weight=weight, metacentric_height=gm, heel_angle=HEEL_ANGLE)
        return gm_m, moment.to("kN*m").magnitude

    low_gm, low_moment = state(LOW_CG_HEIGHT)
    high_gm, _ = state(HIGH_CG_HEIGHT)
    return {
        "low_load_gm_m": low_gm,
        "low_load_righting_knm": low_moment,
        "high_load_gm_m": high_gm,
    }


def main() -> None:
    s = pontoon_stability()
    low = s["low_load_gm_m"]
    high = s["high_load_gm_m"]
    moment = s["low_load_righting_knm"]
    print(f"load low  : GM = {low:+.2f} m  (stable, rights with {moment:.0f} kN·m at 10 deg)")
    verdict = "CAPSIZES" if high < 0 else "stable"
    print(f"load high : GM = {high:+.2f} m  ({verdict})")
    print("  -> same weight; raising the center of gravity above the metacenter turns it over")


if __name__ == "__main__":
    main()
