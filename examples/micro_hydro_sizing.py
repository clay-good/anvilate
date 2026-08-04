"""Worked example: a mountain stream's micro-hydro output, and what the penstock loss costs it.

Micro-hydro is the plainest of the renewables: the power is simply how much water falls times how
far it drops, P = ρ·g·Q·H·η — linear in both, so unlike a wind turbine's cube law there is no
threshold to clear, only water to pass. The one subtlety is the head. The map shows a *gross* drop
from intake to turbine, but the penstock that carries the water there has friction, and every metre
of head that friction eats is a metre the turbine never sees.

This example takes a small run-of-river site: a steady 60 L/s (0.06 m³/s) stream and a 40 m gross
drop to the powerhouse, through a penstock whose friction (from a pipe-flow calc) costs 4 m of head.
The turbine-plus-generator runs at 0.70 overall efficiency. On the gross head the site looks like a
16.5 kW machine, but the turbine only ever sees the *net* 36 m, and on that it delivers about
14.8 kW. The example computes both so the gap is explicit: sizing on gross head overstates the plant
by the loss fraction — here a tenth of the head, and so a tenth of the power.

Finally it runs the sizing inverse: if the goal were a round 12 kW instead, how much flow would the
intake and penstock have to carry at that same net head? The answer, about 49 L/s, is well under the
60 L/s the stream carries — but that margin is only real if the dry-season flow still clears it,
which is the check that decides whether the rating holds year-round.

Run it directly (``python examples/micro_hydro_sizing.py``);
:func:`hydro_sizing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import hydro_flow_for_power, hydro_net_head, hydro_turbine_power
from anvilate.units import Quantity

FLOW = Quantity.parse("0.06 m**3/s")
GROSS_HEAD = Quantity.parse("40 m")
HEAD_LOSS = Quantity.parse("4 m")
EFFICIENCY = 0.70
WATER = Quantity.parse("1000 kg/m**3")
TARGET_POWER = Quantity.parse("12 kW")


def hydro_sizing() -> dict[str, float]:
    """Return the gross- vs net-head power of the site and the flow a 12 kW target would need."""
    net_head = hydro_net_head(gross_head=GROSS_HEAD, head_loss=HEAD_LOSS)

    gross_power = hydro_turbine_power(
        flow_rate=FLOW,
        net_head=GROSS_HEAD,  # optimistic: ignores the penstock loss
        overall_efficiency=EFFICIENCY,
        fluid_density=WATER,
    )
    net_power = hydro_turbine_power(
        flow_rate=FLOW,
        net_head=net_head,
        overall_efficiency=EFFICIENCY,
        fluid_density=WATER,
    )
    flow_for_target = hydro_flow_for_power(
        target_power=TARGET_POWER,
        net_head=net_head,
        overall_efficiency=EFFICIENCY,
        fluid_density=WATER,
    )
    return {
        "net_head_m": net_head.to("m").magnitude,
        "gross_power_kw": gross_power.to("kW").magnitude,
        "net_power_kw": net_power.to("kW").magnitude,
        "flow_for_target_lps": flow_for_target.to("m**3/s").magnitude * 1000.0,
    }


def main() -> None:
    s = hydro_sizing()
    print(
        f"on gross head (40 m): {s['gross_power_kw']:.1f} kW  (optimistic — ignores the penstock)"
    )
    print(
        f"on net head ({s['net_head_m']:.0f} m) : {s['net_power_kw']:.1f} kW  "
        f"(the honest rating the turbine sees)"
    )
    print(
        f"to hit 12 kW you would need {s['flow_for_target_lps']:.0f} L/s "
        "-> check it against the dry-season flow"
    )


if __name__ == "__main__":
    main()
