"""Worked example: financing and justifying a piece of equipment.

Deciding whether to buy a machine mixes three economic questions: what the loan to buy it costs each
year, what a savings plan would grow to, and how quickly the machine pays for itself. The
capital-recovery, sinking-fund, and payback relations answer them.

Financing a $10,000 machine over 10 years at 8% takes level payments of about $1,490 a year. Setting
aside $1,000 a year instead, at the same 8%, would grow into about $14,487 after 10 years. And a
$50,000 upgrade that saves $8,000 a year pays for itself in a simple payback of 6.25 years. This
example reports the annual loan payment, the future value of the savings plan, and the payback
period.

Run it directly (``python examples/equipment_financing.py``);
:func:`equipment_financing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    annuity_future_value,
    loan_payment,
    simple_payback_period,
)

RATE = 0.08  # 8% per year
YEARS = 10


def equipment_financing() -> dict[str, float]:
    """Return the annual loan payment, the savings future value, and the payback period."""
    payment = loan_payment(principal=10000.0, rate=RATE, periods=YEARS)
    savings = annuity_future_value(payment=1000.0, rate=RATE, periods=YEARS)
    payback = simple_payback_period(initial_cost=50000.0, annual_cash_flow=8000.0)
    return {
        "annual_loan_payment_usd": payment,
        "savings_future_value_usd": savings,
        "payback_period_years": payback,
    }


def main() -> None:
    d = equipment_financing()
    print(f"annual loan payment (10 yr, 8%): ${d['annual_loan_payment_usd']:,.2f}")
    print(f"savings future value (10 yr, 8%): ${d['savings_future_value_usd']:,.2f}")
    print(f"simple payback: {d['payback_period_years']:.2f} years")


if __name__ == "__main__":
    main()
