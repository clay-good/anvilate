"""Worked example: the pressure and flow at the most remote fire sprinkler.

A light-hazard wet system uses standard-response heads with a K-factor of 5.6 gpm/psi^½. The
hazard's design density and the head spacing require each sprinkler to deliver at least 18 gpm. The
hydraulic calculation starts at the most remote head: what pressure does it need, and once that
pressure is set, how much does the head actually flow?

To push 18 gpm through a K=5.6 head the residual pressure must be P = (18/5.6)^2 = 10.3 psi — above
the 7 psi NFPA minimum, so the head governs on flow, not on the pressure floor. Feeding that
10.3 psi back into the discharge relation returns the 18 gpm, confirming the balance; the
branch-line calculation then accumulates friction loss from this head back toward the riser.

Run it directly (``python examples/sprinkler_remote_head_demand.py``);
:func:`remote_head_demand` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import sprinkler_discharge, sprinkler_pressure_for_flow
from anvilate.units import Quantity

K_FACTOR = Quantity.parse("5.6 gallon/minute/psi**0.5")
REQUIRED_FLOW = Quantity.parse("18 gallon/minute")


def remote_head_demand() -> dict[str, float]:
    """Return the pressure (psi) the remote head needs and the flow (gpm) it then delivers."""
    pressure = sprinkler_pressure_for_flow(k_factor=K_FACTOR, flow_rate=REQUIRED_FLOW)
    flow = sprinkler_discharge(k_factor=K_FACTOR, pressure=pressure)
    return {
        "required_pressure_psi": pressure.to("psi").magnitude,
        "delivered_flow_gpm": flow.to("gallon/minute").magnitude,
    }


def main() -> None:
    d = remote_head_demand()
    print("Most remote sprinkler, K=5.6, 18 gpm design flow:")
    print(f"  required residual pressure : {d['required_pressure_psi']:.1f} psi")
    print(f"  delivered flow at that P   : {d['delivered_flow_gpm']:.1f} gpm")


if __name__ == "__main__":
    main()
