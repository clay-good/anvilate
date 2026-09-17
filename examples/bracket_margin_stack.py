"""Worked example: the same bracket plate at code minimum and as delivered.

A cantilevered A36 bracket plate, 100 mm wide, carries 4 kN at 150 mm. Its bending stress is
6·F·L / (b·t²), judged against the AISC 360-22 ASD allowable Fy/Ω with Ω = 1.67.

At code minimum the plate needs to be 15.5 mm thick, and the next stock plate is 16 mm.

The delivered design is sized with four more factors, each defensible alone: a project factor
of 1.25 the lead engineer elected, a 1.15 load-growth contingency the spec declares, a 1.1
dynamic allowance the rigging plan adds, and the snap up to stock. Together the demand
multipliers ask for 19.5 mm, delivered as 20 mm: 1.25 times the thickness and the mass of the
code-minimum plate.

The ledger states what no single factor does. The cumulative factor on the bending stress is
2.71. The two contingencies come from two origins and are named as a possible double count
(x1.265 combined), not resolved. And the delivered 20 mm plate, judged at code minimum, runs
at a utilization of 0.60 against the 0.95 it reports with every factor applied.

Nothing here says any factor is wrong. The ledger makes the total visible so an engineer can.
Run it directly (``python examples/bracket_margin_stack.py``).
"""

from __future__ import annotations

from math import sqrt

from anvilate.margin import MarginAction, MarginEntry, MarginKind, MarginLedger

FORCE_N = 4_000.0
ARM_MM = 150.0
WIDTH_MM = 100.0
YIELD_MPA = 250.0  # ASTM A36
OMEGA = 1.67  # AISC 360-22 ASD flexure
STOCK_MM = (6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 25.0)
QUANTITY = "bracket bending stress"

_ELECTED = (
    ("project factor", MarginKind.USER_ELECTED, 1.25, MarginAction.LOWERS_CAPACITY,
     "spec: design review DR-12", "user election: lead engineer"),
    ("load growth", MarginKind.CONTINGENCY, 1.15, MarginAction.RAISES_DEMAND,
     "spec: loads.growth", "company practice DP-104"),
    ("dynamic allowance", MarginKind.CONTINGENCY, 1.1, MarginAction.RAISES_DEMAND,
     "rigging plan RP-3", "company practice DP-104"),
)  # fmt: skip


def _required_thickness(factor: float) -> float:
    """t such that 6·F·L·factor / (b·t²) = Fy/Ω, in mm."""
    return sqrt(6.0 * FORCE_N * ARM_MM * factor * OMEGA / (WIDTH_MM * YIELD_MPA))


def _stock(thickness: float) -> float:
    return next(size for size in STOCK_MM if size >= thickness)


def _utilization(thickness: float, factor: float) -> float:
    stress = 6.0 * FORCE_N * ARM_MM * factor / (WIDTH_MM * thickness**2)
    return stress / (YIELD_MPA / OMEGA)


def margin_stack() -> dict[str, object]:
    """Both designs, and the ledger that multiplies out the difference."""
    code_nominal = _required_thickness(1.0)
    code_stock = _stock(code_nominal)
    multipliers = 1.0
    for _label, _kind, value, *_rest in _ELECTED:
        multipliers *= value
    delivered_nominal = _required_thickness(multipliers)
    delivered_stock = _stock(delivered_nominal)

    entries = [
        MarginEntry(
            label="ASD flexure factor",
            kind=MarginKind.CODE_REQUIRED,
            value=OMEGA,
            quantity=QUANTITY,
            action=MarginAction.LOWERS_CAPACITY,
            origin="check: bracket bending",
            authority="AISC 360-22 §F1, ASD",
        )
    ]
    for label, kind, value, action, origin, authority in _ELECTED:
        entries.append(
            MarginEntry(
                label=label,
                kind=kind,
                value=value,
                quantity=QUANTITY,
                action=action,
                origin=origin,
                authority=authority,
            )
        )
    entries.append(
        MarginEntry.rounding(
            label="plate thickness",
            nominal=delivered_nominal,
            delivered=delivered_stock,
            quantity=QUANTITY,
            origin="stock snap",
            authority="ASTM A6 plate stock list",
        )
    )
    ledger = MarginLedger(entries=tuple(entries))
    stack = ledger.stack(QUANTITY)
    (double,) = ledger.double_counts()
    delivered_utilization = _utilization(delivered_stock, multipliers)
    return {
        "ledger": ledger,
        "code_nominal_mm": code_nominal,
        "code_stock_mm": code_stock,
        "delivered_nominal_mm": delivered_nominal,
        "delivered_stock_mm": delivered_stock,
        "thickness_ratio": delivered_stock / code_stock,
        "cumulative": stack.cumulative,
        "double_count": double.combined,
        "delivered_utilization": delivered_utilization,
        "code_minimum_utilization": stack.physics_limited_utilization(delivered_utilization),
    }


def main() -> None:
    result = margin_stack()
    print(
        f"code minimum: {result['code_nominal_mm']:.1f} mm required, "
        f"{result['code_stock_mm']:g} mm stock"
    )
    print(
        f"as delivered: {result['delivered_nominal_mm']:.1f} mm required, "
        f"{result['delivered_stock_mm']:g} mm stock "
        f"({result['thickness_ratio']:.2f}x the thickness and mass)"
    )
    print(
        f"utilization of the delivered plate: {result['delivered_utilization']:.2f} with "
        f"every factor, {result['code_minimum_utilization']:.2f} at code minimum"
    )
    print(result["ledger"])


if __name__ == "__main__":
    main()
