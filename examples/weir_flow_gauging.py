"""Worked example: gauging a stream with a weir, and why the V-notch wins at low flow.

To measure the flow in an open channel you dam it with a weir and read the head of water backed up
over the crest — the channel's version of an orifice plate. The shape of the weir sets how well it
resolves the flow. A rectangular weir spans the whole width, so at low flows a small change in
discharge barely moves the head and the reading is coarse. A V-notch weir funnels the flow through
a narrowing triangular slot, so even a trickle produces a readable head — its discharge climbs as
the 5/2 power of head against the rectangular weir's 3/2. This example puts the same low flow over
both weirs at the same head and shows the V-notch is the sensitive instrument for small streams,
while the rectangular weir is for bigger channels. Same water, two ways to read it.

Run it directly (``python examples/weir_flow_gauging.py``);
:func:`weir_discharges` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rectangular_weir_flow, triangular_weir_flow
from anvilate.units import Quantity

HEAD = Quantity.parse("0.3 m")  # water surface above the crest / notch
RECTANGULAR_CD = 0.62
CREST_LENGTH = Quantity.parse("1 m")
VNOTCH_CD = 0.58
NOTCH_ANGLE = 90.0  # degrees


def weir_discharges() -> dict[str, float]:
    """Return the rectangular- and V-notch-weir discharges (L/s) at the same head."""
    rect = (
        rectangular_weir_flow(
            discharge_coefficient=RECTANGULAR_CD, crest_length=CREST_LENGTH, head=HEAD
        )
        .to("m**3/s")
        .magnitude
    )
    vnotch = (
        triangular_weir_flow(discharge_coefficient=VNOTCH_CD, notch_angle=NOTCH_ANGLE, head=HEAD)
        .to("m**3/s")
        .magnitude
    )
    return {
        "rectangular_lps": rect * 1000.0,
        "vnotch_lps": vnotch * 1000.0,
    }


def main() -> None:
    w = weir_discharges()
    print(f"rectangular weir (1 m crest) : {w['rectangular_lps']:.0f} L/s at 0.30 m head")
    print(f"90 deg V-notch weir          : {w['vnotch_lps']:.0f} L/s at 0.30 m head")
    print("  -> the V-notch passes far less at the same head — its fine low-flow resolution")


if __name__ == "__main__":
    main()
