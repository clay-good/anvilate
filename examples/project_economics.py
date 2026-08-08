"""Worked example: the time value of money for a capital project.

Comparing a design's costs and savings that fall in different years needs the time value of money:
future amounts are discounted to today, present amounts grow into the future, and a stream of equal
payments collapses to a single equivalent lump sum. These three relations screen whether a project
pays off.

At an 8% discount rate, $10,000 received five years out is worth about $6,806 today — the higher the
rate or the longer the wait, the less it is worth now. The other way, $6,806 invested today grows
back to $10,000 in five years. And a stream of $1,000 saved each year for ten years is worth about
$6,710 as a lump sum today. This example reports the present value of the future amount, its future
value, and the present value of the annuity.

Run it directly (``python examples/project_economics.py``);
:func:`project_economics` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    annuity_present_value,
    future_value,
    present_value,
)

DISCOUNT_RATE = 0.08  # 8% per year
YEARS = 5
ANNUITY_YEARS = 10


def project_economics() -> dict[str, float]:
    """Return the present value, future value, and annuity present value."""
    pv = present_value(future_value=10000.0, rate=DISCOUNT_RATE, periods=YEARS)
    fv = future_value(present_value=pv, rate=DISCOUNT_RATE, periods=YEARS)
    annuity = annuity_present_value(payment=1000.0, rate=DISCOUNT_RATE, periods=ANNUITY_YEARS)
    return {
        "present_value_usd": pv,
        "future_value_usd": fv,
        "annuity_present_value_usd": annuity,
    }


def main() -> None:
    d = project_economics()
    print(f"present value of $10,000 in 5 yr: ${d['present_value_usd']:,.2f}")
    print(f"future value of that today: ${d['future_value_usd']:,.2f}")
    print(f"present value of $1,000/yr for 10 yr: ${d['annuity_present_value_usd']:,.2f}")


if __name__ == "__main__":
    main()
