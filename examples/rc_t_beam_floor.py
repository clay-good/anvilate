"""Worked example: a reinforced-concrete floor beam — why the slab flange matters.

A floor beam cast monolithically with its slab is a T-beam, not a rectangle: the slab
acts as a wide compression flange. That flange does two things a designer wants. It
adds strength, and — because the wide flange only needs a shallow compression zone to
balance the steel — it keeps the neutral axis high, so the tension steel strains far
past yield and the section fails ductilely with plenty of warning.

This beam has a 1000 mm effective flange (120 mm slab), a 300 mm web, 540 mm to the
steel, and 3000 mm² of reinforcement (Grade 420, 30 MPa concrete):

  * As a T-beam its nominal moment is 649 kN·m, and the net tensile strain is 0.024 —
    almost five times the 0.005 tension-controlled limit, so it is comfortably ductile
    (phi = 0.90).
  * Ignore the flange and check the 300 mm web alone and it reads only 577 kN·m at a
    net tensile strain of 0.005 — right at the ductility limit.

So the flange adds ~12% strength and transforms the ductility. The example composes the
ACI 318 T-beam moment, the Whitney stress-block depth, and the net-tensile-strain
ductility check.

Run it directly (``python examples/rc_t_beam_floor.py``);
:func:`floor_beam_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    rc_beam_nominal_moment,
    rc_net_tensile_strain,
    rc_stress_block_depth,
    rc_t_beam_moment,
)
from anvilate.units import Quantity

STEEL_AREA = Quantity.parse("3000 mm**2")
YIELD = Quantity.parse("420 MPa")
CONCRETE = Quantity.parse("30 MPa")
FLANGE_WIDTH = Quantity.parse("1000 mm")
WEB_WIDTH = Quantity.parse("300 mm")
FLANGE_THICKNESS = Quantity.parse("120 mm")
EFFECTIVE_DEPTH = Quantity.parse("540 mm")

MATERIAL = {"steel_yield": YIELD, "concrete_strength": CONCRETE}


def floor_beam_capacity() -> dict[str, float]:
    """Return the T-beam and web-only moments and their net tensile strains."""
    t_moment = rc_t_beam_moment(
        tension_steel_area=STEEL_AREA,
        flange_width=FLANGE_WIDTH,
        web_width=WEB_WIDTH,
        flange_thickness=FLANGE_THICKNESS,
        effective_depth=EFFECTIVE_DEPTH,
        **MATERIAL,
    )
    # The stress block sits in the flange, so the ductility check uses the flange width.
    t_block = rc_stress_block_depth(steel_area=STEEL_AREA, beam_width=FLANGE_WIDTH, **MATERIAL)
    t_strain = rc_net_tensile_strain(
        stress_block_depth=t_block, effective_depth=EFFECTIVE_DEPTH, concrete_strength=CONCRETE
    )

    web_moment = rc_beam_nominal_moment(
        steel_area=STEEL_AREA, beam_width=WEB_WIDTH, effective_depth=EFFECTIVE_DEPTH, **MATERIAL
    )
    web_block = rc_stress_block_depth(steel_area=STEEL_AREA, beam_width=WEB_WIDTH, **MATERIAL)
    web_strain = rc_net_tensile_strain(
        stress_block_depth=web_block, effective_depth=EFFECTIVE_DEPTH, concrete_strength=CONCRETE
    )
    return {
        "t_beam_moment_kn_m": t_moment.to("kN*m").magnitude,
        "t_beam_strain": t_strain,
        "web_only_moment_kn_m": web_moment.to("kN*m").magnitude,
        "web_only_strain": web_strain,
    }


def main() -> None:
    r = floor_beam_capacity()
    tm, ts = r["t_beam_moment_kn_m"], r["t_beam_strain"]
    wm, ws = r["web_only_moment_kn_m"], r["web_only_strain"]
    print(f"T-beam   : M_n = {tm:.0f} kN*m, net tensile strain {ts:.3f}")
    print(f"web only : M_n = {wm:.0f} kN*m, net tensile strain {ws:.3f}")
    print("the slab flange adds strength and keeps the section ductile (eps_t >> 0.005)")


if __name__ == "__main__":
    main()
