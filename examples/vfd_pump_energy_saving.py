"""Worked example: why slowing a pump 20% with a VFD cuts its power almost in half.

When a pump delivers more flow than a process needs, there are two ways to cut it back: throttle
a valve, which just burns the excess as heat, or slow the pump down with a variable-frequency
drive. The affinity laws say why the second wins by so much. Flow falls in step with speed, but
power falls with the *cube* of it — so trimming the speed to 80% drops the flow to 80% while the
power collapses to 0.8³ = 51% of its full-speed value. This example takes a pump running at
14 kW and 0.05 m³/s and shows the new operating point after a VFD backs it off to 80% speed: a
fifth less flow for nearly half the energy. That gap, repeated over a year of running, is the
whole economic case for the drive.

Run it directly (``python examples/vfd_pump_energy_saving.py``);
:func:`vfd_operating_point` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import affinity_flow_rate, affinity_head, affinity_power
from anvilate.units import Quantity

RATED_FLOW = Quantity.parse("0.05 m**3/s")
RATED_HEAD = Quantity.parse("20 m")
RATED_POWER = Quantity.parse("14 kW")
SPEED_RATIO = 0.80  # VFD backs the pump to 80% of rated speed


def vfd_operating_point() -> dict[str, float]:
    """Return the flow (L/s), head (m), power (kW), and power fraction at the reduced speed."""
    flow = affinity_flow_rate(flow_rate=RATED_FLOW, speed_ratio=SPEED_RATIO).to("m**3/s").magnitude
    head = affinity_head(head=RATED_HEAD, speed_ratio=SPEED_RATIO).to("m").magnitude
    power = affinity_power(power=RATED_POWER, speed_ratio=SPEED_RATIO).to("kW").magnitude
    return {
        "flow_lps": flow * 1000.0,
        "head_m": head,
        "power_kw": power,
        "power_fraction": power / RATED_POWER.to("kW").magnitude,
    }


def main() -> None:
    op = vfd_operating_point()
    print(f"at 80% speed : flow {op['flow_lps']:.0f} L/s, head {op['head_m']:.1f} m")
    print(f"             : power {op['power_kw']:.1f} kW ({op['power_fraction']:.0%} of rated)")
    saved = (1 - op["power_fraction"]) * 100
    print(f"  -> 20% less flow for {saved:.0f}% less power (the cube law)")


if __name__ == "__main__":
    main()
