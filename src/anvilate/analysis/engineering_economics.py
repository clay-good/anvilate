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

Sources: standard engineering-economy texts (Blank & Tarquin, *Engineering
Economy*; Newnan, *Engineering Economic Analysis*) for the time-value, annuity and
depreciation formulas.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log

__all__ = [
    "annuity_future_value",
    "annuity_present_value",
    "benefit_cost_ratio",
    "declining_balance_depreciation",
    "future_value",
    "loan_payment",
    "net_present_value",
    "present_value",
    "discounted_payback_period",
    "simple_payback_period",
    "straight_line_depreciation",
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


def annuity_future_value(*, payment: float, rate: float, periods: float) -> float:
    """The future value of a uniform series, FV = A·[(1+i)^n − 1]/i.

    The accumulated value after ``periods`` n of a stream of equal ``payment`` A amounts, one each
    period, growing at the per-period ``rate`` i (a decimal): FV = A·[(1+i)^n − 1]/i (and FV = A·n
    when i = 0). This is the sinking-fund result — how a regular saving grows into a target sum.
    Returns the future value as a plain float.
    """
    if rate <= -1.0:
        raise ValueError("rate must be greater than -1")
    if periods < 0:
        raise ValueError("periods must be non-negative")
    if rate == 0.0:
        return payment * periods
    return payment * ((1.0 + rate) ** periods - 1.0) / rate


def loan_payment(*, principal: float, rate: float, periods: float) -> float:
    """The level loan payment (capital recovery), A = P·i(1+i)^n/[(1+i)^n − 1].

    The equal payment that amortizes a ``principal`` P over ``periods`` n at the per-period ``rate``
    i (a decimal): A = P·i(1+i)^n/[(1+i)^n − 1] (and A = P/n when i = 0). It is the mortgage or
    equipment-loan installment, the inverse of the annuity present value. Returns the payment as a
    plain float.
    """
    if rate <= -1.0:
        raise ValueError("rate must be greater than -1")
    if periods <= 0:
        raise ValueError("periods must be positive")
    if rate == 0.0:
        return principal / periods
    factor = rate * (1.0 + rate) ** periods / ((1.0 + rate) ** periods - 1.0)
    return principal * factor


def simple_payback_period(*, initial_cost: float, annual_cash_flow: float) -> float:
    """The simple payback period, n = C/A.

    The time for a project's net ``annual_cash_flow`` A (savings or income) to recover its
    ``initial_cost`` C, ignoring the time value of money: n = C/A. A quick first screen — a shorter
    payback is more attractive, though it says nothing about cash flows past the payback point.
    Returns the payback period in the same time unit as the cash-flow period, as a plain float.
    """
    if initial_cost < 0:
        raise ValueError("initial_cost must be non-negative")
    if annual_cash_flow <= 0:
        raise ValueError("annual_cash_flow must be positive")
    return initial_cost / annual_cash_flow


def net_present_value(*, cash_flows: Sequence[float], rate: float) -> float:
    """The net present value, NPV = Σ CFₜ/(1+i)^t.

    The present value of a whole project's cash-flow stream ``cash_flows`` (period 0 first, usually
    the negative initial cost, then the returns), discounted at the per-period ``rate`` i (a
    decimal): NPV = Σ CFₜ/(1+i)^t over t = 0…n. A positive NPV means the project earns more than the
    discount rate — the standard accept/reject test. Returns the NPV as a plain float.
    """
    if len(cash_flows) == 0:
        raise ValueError("cash_flows must contain at least one period")
    if rate <= -1.0:
        raise ValueError("rate must be greater than -1")
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cash_flows))


def benefit_cost_ratio(*, present_value_benefits: float, present_value_costs: float) -> float:
    """The benefit-cost ratio, B/C = PV(benefits)/PV(costs).

    The ratio of the present value of a project's benefits ``present_value_benefits`` to the present
    value of its costs ``present_value_costs``: B/C = PV(benefits)/PV(costs). A ratio above 1 means
    the discounted benefits outweigh the costs — the go/no-go test used in public-works appraisal.
    Returns the ratio as a plain float.
    """
    if present_value_costs <= 0:
        raise ValueError("present_value_costs must be positive")
    if present_value_benefits < 0:
        raise ValueError("present_value_benefits must be non-negative")
    return present_value_benefits / present_value_costs


def straight_line_depreciation(
    *, initial_cost: float, salvage_value: float, useful_life: float
) -> float:
    """The straight-line depreciation, D = (C − S)/n.

    The constant amount an asset loses in value each period under straight-line accounting, from the
    ``initial_cost`` C, the ``salvage_value`` S at end of life, and the ``useful_life`` n periods:
    D = (C − S)/n. It writes the depreciable base off evenly over the life. Returns the per-period
    depreciation as a plain float.
    """
    if useful_life <= 0:
        raise ValueError("useful_life must be positive")
    if initial_cost < 0 or salvage_value < 0:
        raise ValueError("costs must be non-negative")
    if salvage_value > initial_cost:
        raise ValueError("salvage_value must not exceed initial_cost")
    return (initial_cost - salvage_value) / useful_life


def discounted_payback_period(
    *, initial_cost: float, annual_cash_flow: float, rate: float
) -> float:
    """The payback period with the time value of money, n = −ln(1 − C·i/A)/ln(1 + i).

    :func:`simple_payback_period` divides cost by cash flow and its own docstring concedes it
    ignores the time value of money. This is the honest version: set the present value of an
    ``annual_cash_flow`` A over n periods, discounted at ``rate`` i, equal to the ``initial_cost``
    C, and solve. Inverting the annuity relation A·[1 − (1+i)^−n]/i = C gives
    n = −ln(1 − C·i/A)/ln(1+i).

    It is always longer than the simple figure and the gap widens fast with the discount rate — a
    $250,000 project returning $60,000 a year pays back in 4.17 years undiscounted but 5.27 at 8%.
    The logarithm also surfaces a failure the simple form hides: if C·i ≥ A the annual flow never
    covers the interest on the capital and the project never pays back at any horizon, which
    raises here rather than returning a plausible number. Cost, cash flow, and rate are plain
    floats in consistent units, the rate as a decimal per period. Returns the number of periods as
    a plain float.
    """
    if initial_cost <= 0:
        raise ValueError("initial_cost must be positive")
    if annual_cash_flow <= 0:
        raise ValueError("annual_cash_flow must be positive")
    if rate <= -1.0:
        raise ValueError("rate must exceed -1 (a decimal per period, not a percent)")
    if rate == 0.0:
        return initial_cost / annual_cash_flow
    if initial_cost * rate >= annual_cash_flow:
        raise ValueError(
            f"the project never pays back: the annual cash flow {annual_cash_flow} does not cover "
            f"the interest {initial_cost * rate} on the initial cost at a rate of {rate}"
        )
    return -log(1.0 - initial_cost * rate / annual_cash_flow) / log(1.0 + rate)


def declining_balance_depreciation(
    *,
    initial_cost: float,
    salvage_value: float,
    useful_life: float,
    period: int,
    factor: float = 2.0,
) -> float:
    """The declining-balance charge, D_k = C·r·(1−r)^(k−1) with r = f/n, floored at salvage.

    :func:`straight_line_depreciation` writes an asset off evenly; this writes it off fast. Each
    period takes a fixed fraction r = ``factor`` f divided by the ``useful_life`` n of whatever
    book value is left, so the book value after k−1 periods is C·(1−r)^(k−1) from the
    ``initial_cost`` C and the charge in ``period`` k is r times that. The default f = 2 is the
    double-declining-balance method used for most equipment.

    The point is the front-loading: a $50,000 machine over 5 years charges $20,000 in year 1
    against straight-line's $9,000, which pulls the tax shield forward and changes which of two
    designs wins on present value even when their lifetime costs match. The charge is floored so
    the book value never falls below the ``salvage_value`` S — that clamp bites in the last
    period or two, and once book value has reached salvage the charge is zero, which is why the
    raw geometric series alone is wrong late in life. Periods are 1-indexed. Money amounts are
    plain floats in consistent units. Returns the depreciation charged in that period as a plain
    float.
    """
    if useful_life <= 0:
        raise ValueError("useful_life must be positive")
    if initial_cost < 0 or salvage_value < 0:
        raise ValueError("costs must be non-negative")
    if salvage_value > initial_cost:
        raise ValueError("salvage_value must not exceed initial_cost")
    if period < 1:
        raise ValueError("period must be a positive 1-indexed period")
    if factor <= 0:
        raise ValueError("factor must be positive")
    rate = factor / useful_life
    if rate >= 1.0:
        raise ValueError(
            f"factor/useful_life must be below 1: a rate of {rate} writes the asset off entirely "
            "in the first period"
        )
    opening_book_value = initial_cost * (1.0 - rate) ** (period - 1)
    return min(opening_book_value * rate, max(0.0, opening_book_value - salvage_value))
