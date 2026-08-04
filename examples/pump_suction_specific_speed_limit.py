"""Worked example: the faster pump is smaller and cheaper — and quietly unreliable.

Two pumps can move the same 45 L/s and still not be equally safe to buy. Run a pump faster and it
makes the same head from a smaller, cheaper casing — but it also works its inlet harder, and past a
point the flow at the impelling eye starts to recirculate at part-load, chewing the impeller and
shaking the machine. The single number that flags this is the suction specific speed
N_ss = ω·√Q / (g·NPSHr)^(3/4): the Hydraulic Institute's reliability guidance keeps it below about
3.5 in this SI dimensionless form (~9000-11000 in US rpm/gpm/ft units).

This example puts a slow 1450 rpm pump (NPSHr 2.5 m) next to a fast 2900 rpm one (NPSHr 3.5 m) on
the same 45 L/s duty. The slow pump lands at N_ss ≈ 2.9, comfortably inside the limit. The fast
pump is tempting because it is physically smaller, but it lands at N_ss ≈ 4.5, past the reliability
cap, so it is the one prone to suction recirculation and a short bearing life. The lesson is that
suction specific speed, not price or size, tells you which pump will still be running in five years.

Run it directly (``python examples/pump_suction_specific_speed_limit.py``);
:func:`suction_speeds` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import pump_suction_specific_speed
from anvilate.units import Quantity

DUTY_FLOW = Quantity.parse("45 L/s")
RELIABILITY_LIMIT = 3.5  # SI dimensionless N_ss cap (Hydraulic Institute guidance)


def suction_speeds() -> dict[str, float]:
    """Return the suction specific speed of a slow and a fast pump on the same duty."""
    slow = pump_suction_specific_speed(
        rotational_speed=Quantity.parse("1450 rpm"),
        flow_rate=DUTY_FLOW,
        npsh_required=Quantity.parse("2.5 m"),
    )
    fast = pump_suction_specific_speed(
        rotational_speed=Quantity.parse("2900 rpm"),
        flow_rate=DUTY_FLOW,
        npsh_required=Quantity.parse("3.5 m"),
    )
    return {"slow_nss": slow, "fast_nss": fast}


def main() -> None:
    s = suction_speeds()
    slow_ok = "OK" if s["slow_nss"] <= RELIABILITY_LIMIT else "over limit"
    fast_ok = "OK" if s["fast_nss"] <= RELIABILITY_LIMIT else "over limit"
    print(f"reliability cap : N_ss <= {RELIABILITY_LIMIT}")
    print(f"slow 1450 rpm pump : N_ss = {s['slow_nss']:.2f} ({slow_ok})")
    print(f"fast 2900 rpm pump : N_ss = {s['fast_nss']:.2f} ({fast_ok})")
    print("  -> the smaller, faster pump is the one that courts suction recirculation")


if __name__ == "__main__":
    main()
