"""Worked example: a bolted tension splice where block shear, not the member, governs.

A 200x10 mm A992 plate (F_y = 345, F_u = 450 MPa) is spliced with M20 bolts in
22 mm holes. The two checks an engineer reaches for first — gross-section yielding
(phi*P_n = 621 kN) and net-section rupture across the staggered holes (544 kN) —
both look comfortable. But the bolt group can also tear a block out of the plate
end, and AISC §J4.3 block shear comes in at only 450 kN. So the connection is
governed by a limit state that never appears if you check the member alone: the
end block tears out before the plate yields or ruptures.

The example composes three §B/§J closed-forms — the staggered-hole net width
(s^2/4g), the block-shear rupture strength, and gross yielding — and reports the
governing one. Design factors are LRFD phi (0.90 tension yielding, 0.75 rupture
and block shear). The plate transfers load through its full width, so the
shear-lag factor U is 1.0.

Run it directly (``python examples/bolted_tension_splice.py``);
:func:`splice_capacities` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import block_shear_strength, net_width_staggered_holes
from anvilate.units import Quantity

WIDTH = Quantity.parse("200 mm")
THICKNESS = Quantity.parse("10 mm")
HOLE = Quantity.parse("22 mm")
YIELD = Quantity.parse("345 MPa")
ULTIMATE = Quantity.parse("450 MPa")

PHI_YIELD = 0.90  # LRFD resistance factor, tension yielding (§D2)
PHI_RUPTURE = 0.75  # LRFD resistance factor, rupture / block shear (§D2, §J4.3)


def splice_capacities() -> dict[str, Quantity]:
    """Return the LRFD design strengths of the three tension limit states."""
    t = THICKNESS.to("mm").magnitude
    gross_area = WIDTH.to("mm").magnitude * t

    # §D2 gross-section yielding: phi * F_y * A_g.
    yielding = Quantity(
        magnitude=PHI_YIELD * YIELD.to("MPa").magnitude * gross_area / 1000.0, unit="kN"
    )

    # §D2 net-section rupture across the staggered path (U = 1 for a full-width plate).
    net_width = net_width_staggered_holes(
        gross_width=WIDTH,
        hole_diameter=HOLE,
        hole_count=2,
        stagger_pitch_gauge=[(Quantity.parse("40 mm"), Quantity.parse("75 mm"))],
    )
    net_area = net_width.to("mm").magnitude * t
    rupture = Quantity(
        magnitude=PHI_RUPTURE * ULTIMATE.to("MPa").magnitude * net_area / 1000.0, unit="kN"
    )

    # §J4.3 block shear: two shear planes down the bolt lines plus one tension plane
    # across the end block.
    shear_len = 100.0  # end distance along each shear plane, mm
    block = block_shear_strength(
        gross_shear_area=Quantity(magnitude=2 * shear_len * t, unit="mm**2"),
        net_shear_area=Quantity(magnitude=2 * (shear_len - 1.5 * 22.0) * t, unit="mm**2"),
        net_tension_area=Quantity(magnitude=(75.0 - 22.0) * t, unit="mm**2"),
        yield_strength=YIELD,
        ultimate_strength=ULTIMATE,
    )
    block_design = Quantity(magnitude=PHI_RUPTURE * block.to("kN").magnitude, unit="kN")

    return {"yielding": yielding, "rupture": rupture, "block_shear": block_design}


def main() -> None:
    caps = splice_capacities()
    governing = min(caps, key=lambda k: caps[k].to("kN").magnitude)
    for name, strength in caps.items():
        marker = "  <-- governs" if name == governing else ""
        print(f"{name:12s}: {strength.to('kN').magnitude:.0f} kN{marker}")


if __name__ == "__main__":
    main()
