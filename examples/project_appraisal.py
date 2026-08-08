"""Worked example: appraising a capital project three standard ways.

Deciding whether a project is worth funding uses three headline metrics: net present value tests
whether the discounted returns beat the initial outlay, the benefit-cost ratio expresses the same
thing as a ratio, and straight-line depreciation tracks how the asset's book value falls.

A project costing $50,000 up front that returns $15,000 a year for five years, discounted at 10%,
has a net present value of about $6,862 — positive, so it clears the 10% hurdle. Its discounted
benefits of about $56,862 against the $50,000 cost give a benefit-cost ratio of about 1.14, above
1. A $60,000 machine with a $10,000 salvage value over a 10-year life depreciates $5,000 a year on a
straight-line basis. This example reports the net present value, the benefit-cost ratio, and the
annual depreciation.

Run it directly (``python examples/project_appraisal.py``);
:func:`project_appraisal` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    annuity_present_value,
    benefit_cost_ratio,
    net_present_value,
    straight_line_depreciation,
)

RATE = 0.10  # 10% per year


def project_appraisal() -> dict[str, float]:
    """Return the net present value, the benefit-cost ratio, and the annual depreciation."""
    cash_flows = [-50000.0] + [15000.0] * 5
    npv = net_present_value(cash_flows=cash_flows, rate=RATE)
    pv_benefits = annuity_present_value(payment=15000.0, rate=RATE, periods=5)
    bcr = benefit_cost_ratio(present_value_benefits=pv_benefits, present_value_costs=50000.0)
    depreciation = straight_line_depreciation(
        initial_cost=60000.0, salvage_value=10000.0, useful_life=10
    )
    return {
        "net_present_value_usd": npv,
        "benefit_cost_ratio": bcr,
        "annual_depreciation_usd": depreciation,
    }


def main() -> None:
    d = project_appraisal()
    print(f"net present value: ${d['net_present_value_usd']:,.2f}")
    print(f"benefit-cost ratio: {d['benefit_cost_ratio']:.3f}")
    print(f"annual straight-line depreciation: ${d['annual_depreciation_usd']:,.0f}")


if __name__ == "__main__":
    main()
