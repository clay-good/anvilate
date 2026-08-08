"""T1 analytical engineering-economics (time value of money) checks (closed-form).

Choosing between designs is rarely just a physics question — the cheaper option over the life of the
project usually wins, and comparing money that arrives at different times needs the time value of
money. A dollar today is worth more than a dollar next year because it can earn interest, so future
cash flows are discounted back to a common date before they can be compared. These relations screen
the economic side of a design, alongside the physical screens of the rest of the library.

A single future amount F, n periods away at an interest rate i per period, is worth
PV = F/(1+i)^n today; run forward instead and a present amount P grows to FV = P·(1+i)^n. A uniform
series of equal payments A each period — a loan, a lease, an annual saving — has a present value
PV = A·[1 − (1+i)^−n]/i, the lump sum equivalent to the whole stream. Money amounts are plain
numbers (dimensionless), the rate is a per-period decimal fraction (0.08 for 8%), and the number of
periods is a count.
"""

from __future__ import annotations

__all__ = [
    "annuity_present_value",
    "future_value",
    "present_value",
]


def present_value(*, future_value: float, rate: float, periods: float) -> float:
    """The present value of a future amount, PV = F/(1+i)^n.

    The value today of a single ``future_value`` F received ``periods`` n from now, discounted at
    the per-period ``rate`` i (a decimal, 0.08 for 8%): PV = F/(1+i)^n. It shrinks the further off
    and the higher the rate. Returns the present value as a plain float.
    """
    if rate <= -1.0:
        raise ValueError("rate must be greater than -1")
    if periods < 0:
        raise ValueError("periods must be non-negative")
    return future_value / (1.0 + rate) ** periods


def future_value(*, present_value: float, rate: float, periods: float) -> float:
    """The future value of a present amount, FV = P·(1+i)^n.

    The value ``periods`` n in the future of a ``present_value`` P invested at the per-period
    ``rate`` i (a decimal): FV = P·(1+i)^n — compound growth. Returns the future value as a float.
    """
    if rate <= -1.0:
        raise ValueError("rate must be greater than -1")
    if periods < 0:
        raise ValueError("periods must be non-negative")
    return present_value * (1.0 + rate) ** periods


def annuity_present_value(*, payment: float, rate: float, periods: float) -> float:
    """The present value of a uniform series, PV = A·[1 − (1+i)^−n]/i.

    The lump sum today equivalent to a stream of equal ``payment`` A amounts, one each period for
    ``periods`` n, at the per-period ``rate`` i (a decimal): PV = A·[1 − (1+i)^−n]/i (and PV = A·n
    when i = 0). This is what values a loan, a lease, or a stream of savings. Returns the present
    value as a plain float.
    """
    if rate <= -1.0:
        raise ValueError("rate must be greater than -1")
    if periods < 0:
        raise ValueError("periods must be non-negative")
    if rate == 0.0:
        return payment * periods
    return payment * (1.0 - (1.0 + rate) ** (-periods)) / rate
