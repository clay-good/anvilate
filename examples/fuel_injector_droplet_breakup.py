"""Worked example: will a fuel spray atomize? The Weber-number droplet-breakup check.

An injector or atomizer works by making the aerodynamic forces on a liquid drop overwhelm the
surface tension holding it together, and the Weber number We = ρ·V²·L/σ is the score that says
whether it succeeds. This example takes a diesel droplet — 50 µm across, surface tension 0.03 N/m —
in the combustion-chamber gas, and works its Weber number at two relative velocities. Dribbling at
2 m/s the Weber number sits below the ~12 breakup threshold, so surface tension keeps the drop
intact and it burns slowly as a fat globule. Injected at 80 m/s through the nozzle the Weber number
leaps past 12 into the hundreds, and the drop shatters into the fine mist that burns cleanly. The
lesson is that atomization is a velocity game: the same fuel and the same nozzle either dribbles or
sprays depending on whether the Weber number clears the breakup threshold.

Run it directly (``python examples/fuel_injector_droplet_breakup.py``);
:func:`droplet_weber` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import weber_number
from anvilate.units import Quantity

GAS_DENSITY = Quantity.parse("15 kg/m**3")  # dense combustion-chamber gas
DROPLET_DIAMETER = Quantity.parse("50 um")
SURFACE_TENSION = Quantity.parse("0.03 N/m")  # diesel
BREAKUP_THRESHOLD = 12.0


def droplet_weber() -> dict[str, float]:
    """Return the Weber number at a low and a high injection velocity."""
    dribble = weber_number(
        density=GAS_DENSITY,
        velocity=Quantity.parse("2 m/s"),
        characteristic_length=DROPLET_DIAMETER,
        surface_tension=SURFACE_TENSION,
    )
    spray = weber_number(
        density=GAS_DENSITY,
        velocity=Quantity.parse("80 m/s"),
        characteristic_length=DROPLET_DIAMETER,
        surface_tension=SURFACE_TENSION,
    )
    return {"weber_dribble": dribble, "weber_spray": spray}


def main() -> None:
    w = droplet_weber()
    dribble_state = "breaks up" if w["weber_dribble"] > BREAKUP_THRESHOLD else "stays intact"
    spray_state = "breaks up" if w["weber_spray"] > BREAKUP_THRESHOLD else "stays intact"
    print(f"2 m/s dribble  : We = {w['weber_dribble']:.2f} ({dribble_state})")
    print(f"80 m/s spray   : We = {w['weber_spray']:.0f} ({spray_state})")
    print("  -> atomization is a velocity game; the drop shatters only once We clears ~12")


if __name__ == "__main__":
    main()
